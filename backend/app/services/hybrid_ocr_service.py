import os
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

# Tắt OneDNN để tránh lỗi "NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support"
os.environ["FLAGS_use_onednn"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import cv2
import json
import numpy as np
import yaml
from PIL import Image

# ==========================================
# 1. LAZY KHỞI TẠO CÁC MÔ HÌNH
# ==========================================
# Trì hoãn khởi tạo model để tránh xung đột DLL giữa PaddlePaddle và PyTorch trên Windows.

_det_model = None
_recognizer = None
_recognizer_load_failed = False
_NO_PROXY_OPENER = None


def _get_det_model():
    """Lazy-load PaddleOCR detection model."""
    global _det_model
    if _det_model is None:
        from paddleocr import PaddleOCR
        _det_model = PaddleOCR(use_angle_cls=True, lang='vi', show_log=False)
    return _det_model


def _safe_stderr(message):
    try:
        print(message, file=sys.stderr)
    except UnicodeEncodeError:
        sys.stderr.buffer.write(message.encode("utf-8", errors="replace") + b"\n")


def _write_json_stdout(payload):
    data = json.dumps(payload, ensure_ascii=False)
    sys.stdout.buffer.write(data.encode("utf-8", errors="replace") + b"\n")


def _get_no_proxy_opener():
    global _NO_PROXY_OPENER
    if _NO_PROXY_OPENER is None:
        _NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        _NO_PROXY_OPENER.addheaders = [("User-Agent", "Mozilla/5.0")]
    return _NO_PROXY_OPENER


def _download_to_temp(url, timeout=300):
    filename = Path(urlparse(url).path).name or "vietocr_asset.bin"
    target = Path(tempfile.gettempdir()) / filename
    if target.exists() and target.stat().st_size > 0:
        return str(target)

    temp_target = target.with_name(target.name + ".part")
    opener = _get_no_proxy_opener()
    try:
        with opener.open(url, timeout=timeout) as response, open(temp_target, "wb") as handle:
            shutil.copyfileobj(response, handle)
        os.replace(temp_target, target)
    finally:
        if temp_target.exists():
            try:
                temp_target.unlink()
            except OSError:
                pass
    return str(target)


def _download_yaml_config(config_name):
    resource = config_name.split("/")[-1]
    candidates = []
    if config_name.startswith(("http://", "https://")):
        candidates.append(config_name)
    else:
        candidates.extend(
            [
                f"https://raw.githubusercontent.com/pbcquoc/vietocr/master/config/{resource}",
                f"https://vocr.vn/data/vietocr/config/{resource}",
            ]
        )

    opener = _get_no_proxy_opener()
    last_error = None
    for url in candidates:
        try:
            with opener.open(url, timeout=30) as response:
                content = response.read().decode("utf-8")
            config_dict = yaml.safe_load(content)
            if isinstance(config_dict, dict):
                return config_dict
        except Exception as exc:
            last_error = exc
            continue

    raise RuntimeError(f"Failed to download VietOCR config '{config_name}': {last_error}")


def _prepare_page_image(img_cv):
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    gray = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def _prepare_crop_image(cropped_img_cv):
    gray = cv2.cvtColor(cropped_img_cv, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    scale = 1.0
    if max(h, w) < 96:
        scale = 2.0
    elif h < 40 or w < 160:
        scale = 1.5
    if scale != 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    return Image.fromarray(enhanced)


def _get_recognizer():
    """Lazy-load VietOCR recognizer model."""
    global _recognizer, _recognizer_load_failed
    if _recognizer_load_failed:
        return None
    if _recognizer is not None:
        return _recognizer
    try:
        import vietocr.tool.config as vietocr_config
        import vietocr.tool.predictor as vietocr_predictor
        import vietocr.tool.utils as vietocr_utils
        from vietocr.tool.config import Cfg
        from vietocr.tool.predictor import Predictor

        # --- BẮT ĐẦU FIX LỖI SERVER VOCR.VN BỊ SẬP (Errno 111 Connection refused) ---
        def safe_download_config(config_name):
            return _download_yaml_config(config_name)

        def safe_download_weights(uri, cached=None, md5=None, quiet=False):
            if uri.startswith(("http://", "https://")):
                return _download_to_temp(uri)
            return uri

        vietocr_utils.download_config = safe_download_config
        vietocr_utils.download_weights = safe_download_weights
        vietocr_config.download_config = safe_download_config
        vietocr_predictor.download_weights = safe_download_weights
        config = Cfg.load_config_from_name("vgg_transformer")
        # --- KẾT THÚC BẢN VÁ ---

        config['cnn']['pretrained'] = False
        config['device'] = 'cpu'  # Mặc định CPU cho ổn định
        _recognizer = Predictor(config)
        return _recognizer
    except Exception as exc:
        _recognizer_load_failed = True
        _safe_stderr(
            f"[WARN] VietOCR unavailable, falling back to PaddleOCR recognition: {exc}",
        )
        return None


def _group_extracted_lines(extracted_lines):
    extracted_lines.sort(key=lambda item: (item['y_coord'], item['x_coord']))

    grouped_lines = []
    current_line = []
    current_y = None

    for item in extracted_lines:
        text = item['text'].strip()
        if not text:
            continue

        y = item['y_coord']
        if current_y is None:
            current_y = y
            current_line.append(text)
        elif abs(y - current_y) <= 20:
            current_line.append(text)
        else:
            grouped_lines.append(" ".join(current_line))
            current_y = y
            current_line = [text]

    if current_line:
        grouped_lines.append(" ".join(current_line))

    return "\n".join(grouped_lines)


def _process_with_paddleocr(img_cv, det_model):
    result = det_model.ocr(img_cv, cls=True)
    if not result or not result[0]:
        return {"text": ""}

    extracted_lines = []
    for item in result[0]:
        if not item or len(item) < 2:
            continue

        box, rec = item[0], item[1]
        text = rec[0] if isinstance(rec, (list, tuple)) and rec else rec
        if not text:
            continue

        pts = np.array(box, dtype=np.float32)
        extracted_lines.append(
            {
                "text": str(text),
                "y_coord": int(min(pts[:, 1])),
                "x_coord": int(min(pts[:, 0])),
            }
        )

    return {"text": _group_extracted_lines(extracted_lines)}


def process_image(image_path):
    if not os.path.exists(image_path):
        return {"error": f"File not found: {image_path}", "text": ""}

    img_cv = cv2.imread(image_path)
    if img_cv is None:
        return {"error": f"Failed to read image: {image_path}", "text": ""}

    recognizer = _get_recognizer()
    det_model = _get_det_model()
    prepared_page = _prepare_page_image(img_cv)
    if recognizer is None:
        return _process_with_paddleocr(prepared_page, det_model)

    # 1. Tìm bounding boxes bằng PaddleOCR
    result = det_model.ocr(prepared_page, cls=False, rec=False)
    
    if not result or not result[0]:
        return {"text": ""}

    boxes = result[0]
    extracted_lines = []

    # 2. Cắt ảnh và nhận diện bằng VietOCR
    for box in boxes:
        pts = np.array(box, dtype=np.float32)
        
        x_min = int(min(pts[:, 0]))
        x_max = int(max(pts[:, 0]))
        y_min = int(min(pts[:, 1]))
        y_max = int(max(pts[:, 1]))
        
        # Thêm padding
        pad = 4
        y_min = max(0, y_min - pad)
        y_max = min(img_cv.shape[0], y_max + pad)
        x_min = max(0, x_min - pad)
        x_max = min(img_cv.shape[1], x_max + pad)

        cropped_img_cv = img_cv[y_min:y_max, x_min:x_max]
        if cropped_img_cv.size == 0:
            continue
            
        cropped_img_pil = _prepare_crop_image(cropped_img_cv)
        
        try:
            text = recognizer.predict(cropped_img_pil)
            if text:
                extracted_lines.append({
                    'text': text,
                    'y_coord': y_min,
                    'x_coord': x_min
                })
        except Exception as e:
            # Bỏ qua nếu lỗi trên 1 dòng
            continue

    if not extracted_lines:
        return _process_with_paddleocr(prepared_page, det_model)

    # 3. Sắp xếp theo thứ tự đọc (Y trước, X sau)
    return {"text": _group_extracted_lines(extracted_lines)}

if __name__ == "__main__":
    import traceback
    try:
        if len(sys.argv) < 2:
            _write_json_stdout({"error": "No image path provided"})
            sys.exit(1)

        image_paths = sys.argv[1:]
        results = []

        for path in image_paths:
            res = process_image(path)
            results.append(res)

        _write_json_stdout(results)
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
