import re
import unicodedata
from typing import Iterable


_OCR_FIXES_REGEX: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bKh6a\b", flags=re.IGNORECASE), "Khóa"),
    (re.compile(r"\bChuo['’]?ng\b", flags=re.IGNORECASE), "Chương"),
    (re.compile(r"\bchuong\b", flags=re.IGNORECASE), "chương"),
    (re.compile(r"\bTién\b", flags=re.IGNORECASE), "Tiền"),
    (re.compile(r"\bdién\b", flags=re.IGNORECASE), "điện"),
    (re.compile(r"\bnuóc\b", flags=re.IGNORECASE), "nước"),
    (re.compile(r"\buóng\b", flags=re.IGNORECASE), "uống"),
    (re.compile(r"\bTong cong\b", flags=re.IGNORECASE), "Tổng cộng"),
    (re.compile(r"\bNoi dung\b", flags=re.IGNORECASE), "Nội dung"),
    (re.compile(r"\bDai hoc\b", flags=re.IGNORECASE), "Đại học"),
    (re.compile(r"\?\s*Ngân", flags=re.IGNORECASE), "- Ngân"),
    (re.compile(r"\bcá nám\b", flags=re.IGNORECASE), "cả năm"),
)

_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_WHITESPACE_PATTERN = re.compile(r"[ \t]+")
_MULTI_NEWLINE_PATTERN = re.compile(r"\n{3,}")

_TABLE_LINE_PATTERN = re.compile(
    r"^\s*(\|.+\|)$|^(\s*[0-9]+(?:[.,][0-9]+){1,}\s*)$|^(\s*(?:STT|Noi|Nội|Khóa|Khoa)\b.*)$",
    flags=re.IGNORECASE,
)


def normalize_unicode(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("\u00A0", " ")
    normalized = normalized.replace("\u200B", "")
    normalized = normalized.replace("\u200C", "")
    normalized = normalized.replace("\u200D", "")
    normalized = _CONTROL_CHAR_PATTERN.sub("", normalized)
    return normalized


def normalize_whitespace(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(_WHITESPACE_PATTERN, " ", line).strip() for line in text.split("\n")]
    cleaned = "\n".join(line for line in lines if line)
    cleaned = _MULTI_NEWLINE_PATTERN.sub("\n\n", cleaned)
    return cleaned.strip()


def apply_common_ocr_fixes(text: str) -> str:
    if not text:
        return ""
    fixed = text
    for pattern, replacement in _OCR_FIXES_REGEX:
        fixed = pattern.sub(replacement, fixed)

    # Common OCR artifacts around day numbers.
    fixed = re.sub(r"(?<=\d)[oO](?=[1-9]\b)", "0", fixed)
    fixed = re.sub(r"\bolf\b", "01", fixed, flags=re.IGNORECASE)
    fixed = re.sub(r"\b0l\b", "01", fixed, flags=re.IGNORECASE)
    return fixed


def is_noisy_line(line: str) -> bool:
    if not line:
        return True
    candidate = line.strip()
    if not candidate:
        return True

    if len(candidate) <= 2:
        return True

    if _TABLE_LINE_PATTERN.match(candidate):
        return True

    alpha = sum(ch.isalpha() for ch in candidate)
    digit = sum(ch.isdigit() for ch in candidate)
    if alpha == 0 and digit > 0:
        return True
    if digit > alpha * 2 and len(candidate) > 12:
        return True

    junk_chars = candidate.count("?") + candidate.count("_")
    if junk_chars >= max(3, len(candidate) // 4):
        return True

    return False


def clean_ocr_text(text: str, drop_table_like_lines: bool = False) -> str:
    if not text:
        return ""

    text = normalize_unicode(text)
    text = apply_common_ocr_fixes(text)
    text = normalize_whitespace(text)
    if not text:
        return ""

    lines: list[str] = []
    seen: set[str] = set()
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if drop_table_like_lines and is_noisy_line(line):
            continue
        line_key = fold_text_for_search(line)
        if not line_key or line_key in seen:
            continue
        seen.add(line_key)
        lines.append(line)

    return "\n".join(lines).strip()


def fold_text_for_search(text: str) -> str:
    if not text:
        return ""
    base = normalize_unicode(text)
    decomp = unicodedata.normalize("NFKD", base)
    without_marks = "".join(ch for ch in decomp if not unicodedata.combining(ch))
    without_marks = without_marks.replace("đ", "d").replace("Đ", "D")
    lowered = without_marks.lower()
    lowered = re.sub(r"[^0-9a-z]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def normalize_metadata_strings(meta: dict) -> dict:
    normalized: dict = {}
    for key, value in meta.items():
        if isinstance(value, str):
            normalized[key] = normalize_whitespace(normalize_unicode(value))
        elif isinstance(value, (list, tuple)):
            normalized[key] = [
                normalize_whitespace(normalize_unicode(v)) if isinstance(v, str) else v
                for v in value
            ]
        else:
            normalized[key] = value
    return normalized


def compact_keywords(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = normalize_whitespace(normalize_unicode(value or ""))
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out
