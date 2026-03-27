from __future__ import annotations

import gc
import json
import os
import pathlib
import re
import subprocess
import sys
import uuid
from datetime import datetime
from typing import Any

import fitz  # PyMuPDF
import pdfplumber
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.services.text_normalization import (
    apply_common_ocr_fixes,
    clean_ocr_text,
    fold_text_for_search,
    normalize_metadata_strings,
    normalize_unicode,
    normalize_whitespace,
)


DEFAULT_METADATA: dict[str, Any] = {
    "doc_type": "Khác",
    "issuer": "Không xác định",
    "doc_number": "Không xác định",
    "date": None,
    "title": "Không xác định",
    "section": "khac",
    "topic": "khac",
}

ROWS_PER_TABLE_CHUNK = 20
TABLE_MAX_CHARS = 1200
SCAN_RENDER_DPI = 300


def _safe_log(message: str) -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        print(message.encode("ascii", "replace").decode("ascii"))


def _safe_unlink(path: str | None) -> None:
    if not path:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _sanitize_date(value: Any) -> str | None:
    if value is None:
        return None
    text = normalize_whitespace(normalize_unicode(str(value)))
    if not text:
        return None
    lowered = text.lower()
    folded = fold_text_for_search(text)
    if lowered in {"không xác định", "khong xac dinh", "none", "null"}:
        return None

    m2 = re.search(
        r"ngay\s*(\d{1,2})\s*thang\s*(\d{1,2})\s*nam\s*(20\d{2})",
        folded,
        flags=re.IGNORECASE,
    )
    if m2:
        day, month, year = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    date_patterns = [
        r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b",
        r"\b(\d{1,2})[-/](\d{1,2})[-/](20\d{2})\b",
    ]
    for pattern in date_patterns:
        m = re.search(pattern, text)
        if not m:
            continue
        if pattern.startswith(r"\b(20"):
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def _extract_metadata_from_text(page_text: str) -> dict[str, Any]:
    text = normalize_whitespace(normalize_unicode(page_text))
    lowered = text.lower()

    data = dict(DEFAULT_METADATA)

    doc_type_rules = [
        ("Thông_báo", ["thông báo"]),
        ("Quyết_định", ["quyết định"]),
        ("Công_văn", ["công văn"]),
        ("Kế_hoạch", ["kế hoạch"]),
        ("Báo_cáo", ["báo cáo"]),
        ("Danh_sách", ["danh sách"]),
    ]
    for doc_type, keywords in doc_type_rules:
        if any(k in lowered for k in keywords):
            data["doc_type"] = doc_type
            break

    title_patterns = [
        r"(THÔNG\s+BÁO[^\n]{0,200})",
        r"(QUYẾT\s+ĐỊNH[^\n]{0,200})",
        r"(CÔNG\s+VĂN[^\n]{0,200})",
    ]
    for pattern in title_patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            data["title"] = normalize_whitespace(m.group(1))
            break

    number_patterns = [
        r"Số\s*[:.]?\s*([0-9A-Za-z/\-\.]+)",
        r"số\s*[:.]?\s*([0-9A-Za-z/\-\.]+)",
    ]
    for pattern in number_patterns:
        m = re.search(pattern, text)
        if m:
            candidate = normalize_whitespace(m.group(1))
            candidate = candidate.strip(".,;:")
            if candidate:
                data["doc_number"] = candidate
                break

    data["date"] = _sanitize_date(text)

    issuer_patterns = [
        r"(Trường\s+Đại\s+học\s+[^\n]{3,120})",
        r"(Bộ\s+[^\n]{3,120})",
    ]
    for pattern in issuer_patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            data["issuer"] = normalize_whitespace(m.group(1))
            break

    return data


def _extract_metadata_from_filename(filename: str | None) -> dict[str, Any]:
    if not filename:
        return dict(DEFAULT_METADATA)

    stem = normalize_unicode(pathlib.Path(filename).stem)
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    stem = re.sub(r"^\d{8,14}\s+", "", stem)
    stem = re.sub(r"(?:[_\-\s]0{0,3}\d{1,4})$", "", stem).strip(" ._-")
    if not stem:
        return dict(DEFAULT_METADATA)

    data = _extract_metadata_from_text(stem)
    folded = fold_text_for_search(stem)

    doc_type_aliases = [
        ("Quyết_định", ["quyet dinh", "qd"]),
        ("Thông_báo", ["thong bao", "tb"]),
        ("Công_văn", ["cong van", "cv"]),
        ("Danh_sách", ["danh sach"]),
        ("Kế_hoạch", ["ke hoach"]),
        ("Báo_cáo", ["bao cao"]),
    ]
    for doc_type, aliases in doc_type_aliases:
        if any(alias in folded for alias in aliases):
            data["doc_type"] = doc_type
            break

    number_patterns = [
        r"(?:QĐ|QD|Quyết\s*định)\s*(?:số|so)?\s*[:.]?\s*([0-9A-Za-z/\-\.]+)",
        r"(?:Số|So)\s*[:.]?\s*([0-9A-Za-z/\-\.]+)",
    ]
    for pattern in number_patterns:
        m = re.search(pattern, stem, flags=re.IGNORECASE)
        if not m:
            continue
        candidate = normalize_whitespace(m.group(1)).strip(".,;:")
        if candidate:
            data["doc_number"] = candidate
            break

    title = stem
    title = re.sub(
        r"^(?:QĐ|QD|QUYẾT\s*ĐỊNH|THÔNG\s*BÁO|TB|CÔNG\s*VĂN|CV)\s*",
        "",
        title,
        flags=re.IGNORECASE,
    )
    title = re.sub(r"^(?:Số|So)\s*[:.]?\s*[0-9A-Za-z/\-\.]+\s*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^(?:V\/?\s*v|VV)\s*", "", title, flags=re.IGNORECASE)
    title = title.strip(" ._-")
    if title:
        data["title"] = normalize_whitespace(title)

    return data


def _merge_metadata(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged = dict(DEFAULT_METADATA)
    merged.update(fallback or {})

    for key, value in (primary or {}).items():
        if value is None:
            continue
        if isinstance(value, str):
            cleaned = normalize_whitespace(normalize_unicode(value))
            default_value = DEFAULT_METADATA.get(key)
            default_cleaned = (
                normalize_whitespace(normalize_unicode(default_value))
                if isinstance(default_value, str)
                else default_value
            )
            if cleaned and cleaned.lower() not in {"không xác định", "khong xac dinh", "null"} and cleaned != default_cleaned:
                merged[key] = cleaned
        else:
            merged[key] = value

    merged["date"] = _sanitize_date(primary.get("date") if primary else None) or _sanitize_date(
        fallback.get("date") if fallback else None
    )
    merged.setdefault("section", "khac")
    merged.setdefault("topic", "khac")
    return normalize_metadata_strings(merged)


def extract_metadata_with_llamacpp(page_1_text: str, filename_hint: str | None = None) -> dict:
    _safe_log("[ingest] extracting metadata")

    text_fallback = _extract_metadata_from_text(page_1_text)
    filename_fallback = _extract_metadata_from_filename(filename_hint)
    base_fallback = _merge_metadata(text_fallback, filename_fallback)
    if not page_1_text or not page_1_text.strip():
        return _merge_metadata({}, base_fallback)

    llm = ChatOpenAI(
        base_url=settings.OLLAMA_BASE_URL,
        api_key="sk-no-key-required",
        model=settings.LLM_MODEL,
        temperature=0,
        model_kwargs={"response_format": {"type": "json_object"}},
    )

    system_prompt = """
Bạn là chuyên gia văn thư. Hãy trích xuất metadata từ văn bản thành JSON.
{
  "doc_type": "Thông_báo | Quyết_định | Công_văn | Danh_sách | Kế_hoạch | Báo_cáo | Khác",
  "issuer": "Tên cơ quan ban hành hoặc 'Không xác định'",
  "doc_number": "Số hiệu văn bản hoặc 'Không xác định'",
  "date": "YYYY-MM-DD hoặc 'Không xác định'",
  "title": "Tiêu đề chính",
  "section": "snake_case",
  "topic": "snake_case"
}
Không thêm giải thích ngoài JSON.
"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"Tên file: {filename_hint or 'Không xác định'}\n\n"
                f"Văn bản:\n{page_1_text[:3000]}"
            )
        ),
    ]

    try:
        response = llm.invoke(messages)
        payload = json.loads(response.content)
    except Exception as exc:
        _safe_log(
            f"[ingest] metadata llm failed base_url={settings.OLLAMA_BASE_URL} model={settings.LLM_MODEL}: {exc}"
        )
        payload = {}

    return _merge_metadata(payload, base_fallback)


def _looks_like_student_header(header_cells: list[str]) -> bool:
    folded = fold_text_for_search(" ".join(header_cells))
    if not folded:
        return False

    strong_id = any(token in folded for token in ["ma sinh vien", "msv", "ma sv"])
    strong_name = any(token in folded for token in ["ho ten", "ten sinh vien", "sinh vien"])
    if strong_id and (strong_name or "lop" in folded):
        return True

    return False


def _chunk_markdown_table(markdown_text: str, max_chars: int = TABLE_MAX_CHARS) -> list[str]:
    lines = [line for line in markdown_text.split("\n") if line.strip()]
    if len(lines) <= 3:
        return [markdown_text]

    header = lines[:2]
    data_lines = lines[2:]
    chunks: list[str] = []
    current: list[str] = []

    for line in data_lines:
        candidate = "\n".join(header + current + [line])
        if current and len(candidate) > max_chars:
            chunks.append("\n".join(header + current))
            current = [line]
        else:
            current.append(line)

    if current:
        chunks.append("\n".join(header + current))

    return chunks


def _build_table_markdown(header: list[str], rows: list[list[str]]) -> str:
    md_lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for row in rows:
        if len(row) < len(header):
            row = row + [""] * (len(header) - len(row))
        md_lines.append("| " + " | ".join(row[: len(header)]) + " |")
    return "\n".join(md_lines)


def _extract_student_ids(rows: list[list[str]]) -> list[str]:
    ids: list[str] = []
    for row in rows:
        for cell in row:
            value = re.sub(r"\D", "", cell)
            if len(value) == 10:
                ids.append(value)
                break
    return list(dict.fromkeys(ids))


def extract_tables_to_markdown(pdf_path: str, global_metadata: dict) -> list[Document]:
    _safe_log("[ingest] extracting tables from native pdf")
    table_docs: list[Document] = []
    saved_header: list[str] | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables(
                table_settings={
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                }
            )
            if not tables:
                tables = page.extract_tables(
                    table_settings={"vertical_strategy": "text", "horizontal_strategy": "text"}
                )

            for table in tables:
                if not table or len(table) < 2:
                    continue

                rows_clean: list[list[str]] = []
                for row in table:
                    clean_row = [clean_ocr_text(str(cell or "")) for cell in row]
                    if any(cell for cell in clean_row):
                        rows_clean.append(clean_row)

                if len(rows_clean) < 2:
                    continue

                first_row = rows_clean[0]
                first_row_text = " ".join(first_row).lower()
                looks_like_header = _looks_like_student_header(first_row) or any(
                    token in first_row_text for token in ["stt", "mã", "nội dung", "khóa", "học kỳ"]
                )

                if looks_like_header:
                    saved_header = first_row
                    data_rows = rows_clean[1:]
                elif saved_header:
                    data_rows = rows_clean
                else:
                    continue

                if not data_rows:
                    continue

                header = saved_header or first_row
                content_type = "student_list" if _looks_like_student_header(header) else "table_md"

                for i in range(0, len(data_rows), ROWS_PER_TABLE_CHUNK):
                    chunk_rows = data_rows[i : i + ROWS_PER_TABLE_CHUNK]
                    markdown = _build_table_markdown(header, chunk_rows)
                    for markdown_chunk in _chunk_markdown_table(markdown):
                        meta = dict(global_metadata)
                        meta.update(
                            {
                                "source": os.path.basename(pdf_path),
                                "page": page_num + 1,
                                "content_type": content_type,
                                "chunk_type": "table",
                                "ocr_engine": "pdfplumber",
                                "table_headers": header,
                                "table_row_count": len(chunk_rows),
                            }
                        )
                        if content_type == "student_list":
                            meta["student_ids_in_chunk"] = _extract_student_ids(chunk_rows)
                        table_docs.append(Document(page_content=markdown_chunk, metadata=normalize_metadata_strings(meta)))

            gc.collect()

    _safe_log(f"[ingest] native table chunks={len(table_docs)}")
    return table_docs





def html_table_to_markdown(html_str: str) -> str:
    soup = BeautifulSoup(html_str, "html.parser")
    rows = soup.find_all("tr")
    markdown_lines: list[str] = []

    for i, row in enumerate(rows):
        cells = row.find_all(["td", "th"])
        values = [clean_ocr_text(cell.get_text(" ", strip=True)) for cell in cells]
        values = [apply_common_ocr_fixes(v) for v in values]
        if not any(values):
            continue
        markdown_lines.append("| " + " | ".join(values) + " |")
        if i == 0:
            markdown_lines.append("|" + "|".join(["---"] * len(values)) + "|")

    return "\n".join(markdown_lines).strip()


def extract_tables_from_scan(pdf_path: str, global_metadata: dict) -> list[Document]:
    _safe_log("[ingest] extracting tables from scan via ppstructure")
    from app.services.ppstructure_service import process_table

    table_docs: list[Document] = []
    session_id = uuid.uuid4().hex
    doc = None

    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        matrix = fitz.Matrix(SCAN_RENDER_DPI / 72, SCAN_RENDER_DPI / 72)
        temp_root = os.path.join(os.getcwd(), "temp")
        os.makedirs(temp_root, exist_ok=True)
        for page_num in range(total_pages):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            temp_img_path = os.path.join(temp_root, f"img_{session_id}_p{page_num}.jpg")
            temp_json_path = os.path.join(temp_root, f"res_{session_id}_p{page_num}.json")

            try:
                pix.save(temp_img_path)
                process_table(temp_img_path, temp_json_path)

                if not os.path.exists(temp_json_path):
                    continue

                with open(temp_json_path, "r", encoding="utf-8") as handle:
                    result_data = json.load(handle)

                for table_html in result_data.get("tables", []):
                    markdown = html_table_to_markdown(table_html)
                    if not markdown:
                        continue

                    markdown_chunks = _chunk_markdown_table(markdown)
                    for chunk in markdown_chunks:
                        lines = [line for line in chunk.split("\n") if line.strip()]
                        header_cells = [c.strip() for c in lines[0].strip("| ").split("|")] if lines else []
                        row_count = max(len(lines) - 2, 0)
                        content_type = "student_list" if _looks_like_student_header(header_cells) else "table_md_scan"

                        meta = dict(global_metadata)
                        meta.update(
                            {
                                "source": os.path.basename(pdf_path),
                                "page": page_num + 1,
                                "content_type": content_type,
                                "chunk_type": "table",
                                "ocr_engine": "ppstructure",
                                "table_headers": header_cells,
                                "table_row_count": row_count,
                            }
                        )
                        if content_type == "student_list":
                            data_rows = [
                                [c.strip() for c in row.strip("| ").split("|")]
                                for row in lines[2:]
                                if row.strip().startswith("|")
                            ]
                            meta["student_ids_in_chunk"] = _extract_student_ids(data_rows)

                        table_docs.append(Document(page_content=chunk, metadata=normalize_metadata_strings(meta)))
            except Exception as exc:
                _safe_log(f"[ingest] table scan failed page={page_num + 1}: {exc}")
            finally:
                _safe_unlink(temp_img_path)
                _safe_unlink(temp_json_path)

            gc.collect()
    except Exception as exc:
        _safe_log(f"[ingest] scan table extraction failed: {exc}")
    finally:
        if doc is not None:
            doc.close()

    _safe_log(f"[ingest] scan table chunks={len(table_docs)}")
    return table_docs


def _extract_json_array(stdout: str) -> list[dict[str, Any]]:
    if not stdout:
        return []

    starts = [idx for idx, ch in enumerate(stdout) if ch == "["]
    for start in reversed(starts):
        snippet = stdout[start:].strip()
        try:
            parsed = json.loads(snippet)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            continue
    return []


def run_hybrid_ocr(pdf_path: str, global_metadata: dict) -> list[Document]:
    _safe_log("[ingest] running hybrid ocr")
    docs: list[Document] = []
    doc = None
    image_paths: list[str] = []

    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        matrix = fitz.Matrix(SCAN_RENDER_DPI / 72, SCAN_RENDER_DPI / 72)

        temp_root = os.path.join(os.getcwd(), "temp")
        os.makedirs(temp_root, exist_ok=True)
        session_id = uuid.uuid4().hex
        for page_num in range(total_pages):
            page = doc[page_num]
            image_path = os.path.join(temp_root, f"page_{session_id}_{page_num}.png")
            page.get_pixmap(matrix=matrix, alpha=False).save(image_path)
            image_paths.append(image_path)

        doc.close()
        doc = None

        # Chạy OCR trong subprocess riêng để tránh xung đột DLL PaddlePaddle/PyTorch
        script_path = os.path.join(os.path.dirname(__file__), "hybrid_ocr_service.py")
        python_exe = sys.executable
        cmd = [python_exe, script_path, *image_paths]
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if process.returncode != 0:
            _safe_log(f"[ingest] hybrid ocr failed: {process.stderr.strip()[:200]}")
            return []

        page_results = _extract_json_array(process.stdout)
        for idx, item in enumerate(page_results):
            raw_text = str(item.get("text", ""))
            cleaned_text = clean_ocr_text(raw_text)
            if not cleaned_text:
                continue

            meta = dict(global_metadata)
            meta.update(
                {
                    "source": os.path.basename(pdf_path),
                    "page": idx + 1,
                    "content_type": "text",
                    "chunk_type": "text",
                    "ocr_engine": "hybrid_ocr",
                }
            )
            docs.append(Document(page_content=cleaned_text, metadata=normalize_metadata_strings(meta)))

    except Exception as exc:
        _safe_log(f"[ingest] hybrid ocr exception: {exc}")
    finally:
        if doc is not None:
            doc.close()
        for image_path in image_paths:
            _safe_unlink(image_path)

    return docs


def extract_text_pymupdf(pdf_path: str, global_metadata: dict) -> list[Document]:
    _safe_log("[ingest] extracting native text")
    docs: list[Document] = []

    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            raw_text = doc[page_num].get_text("text")
            cleaned_text = clean_ocr_text(raw_text)
            if not cleaned_text:
                continue

            meta = dict(global_metadata)
            meta.update(
                {
                    "source": os.path.basename(pdf_path),
                    "page": page_num + 1,
                    "content_type": "text",
                    "chunk_type": "text",
                    "ocr_engine": "native_pdf",
                }
            )
            docs.append(Document(page_content=cleaned_text, metadata=normalize_metadata_strings(meta)))

        doc.close()
    except Exception as exc:
        _safe_log(f"[ingest] native text extraction failed: {exc}")

    return docs
