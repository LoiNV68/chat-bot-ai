import os
import sys

# Tắt OneDNN để tránh lỗi "NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support" trên WSL
os.environ["FLAGS_use_onednn"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

import cv2
import json
import numpy as np
from PIL import Image
from paddleocr import PaddleOCR
from vietocr.tool.predictor import Predictor
from vietocr.tool.config import Cfg

# ==========================================
# 1. KHỞI TẠO CÁC MÔ HÌNH
# ==========================================

# PaddleOCR: Chỉ dùng để tìm khung chữ
# PaddleOCR 2.8.0 sử dụng use_angle_cls và hỗ trợ show_log
det_model = PaddleOCR(use_angle_cls=True, lang='vi', show_log=False)

# VietOCR: Sử dụng vgg_transformer
config = Cfg.load_config_from_name('vgg_transformer')
config['cnn']['pretrained'] = False
config['device'] = 'cpu' # Mặc định CPU cho ổn định trên WSL
recognizer = Predictor(config)

def process_image(image_path):
    if not os.path.exists(image_path):
        return {"error": f"File not found: {image_path}", "text": ""}

    img_cv = cv2.imread(image_path)
    if img_cv is None:
        return {"error": f"Failed to read image: {image_path}", "text": ""}

    # 1. Tìm bounding boxes bằng PaddleOCR
    # PaddleOCR 2.8.0 hỗ trợ cls=False, rec=False ở .ocr()
    result = det_model.ocr(img_cv, cls=False, rec=False)
    
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
        pad = 2
        y_min = max(0, y_min - pad)
        y_max = min(img_cv.shape[0], y_max + pad)
        x_min = max(0, x_min - pad)
        x_max = min(img_cv.shape[1], x_max + pad)

        cropped_img_cv = img_cv[y_min:y_max, x_min:x_max]
        if cropped_img_cv.size == 0:
            continue
            
        cropped_img_pil = Image.fromarray(cv2.cvtColor(cropped_img_cv, cv2.COLOR_BGR2RGB))
        
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

    # 3. Sắp xếp theo thứ tự đọc (Y trước, X sau)
    # Dùng y_coord // 15 để nhóm các dòng cùng độ cao
    extracted_lines.sort(key=lambda item: (item['y_coord'] // 15, item['x_coord']))
    
    full_text = "\n".join([item['text'] for item in extracted_lines if item['text'].strip()])
    return {"text": full_text}

if __name__ == "__main__":
    import traceback
    try:
        if len(sys.argv) < 2:
            print(json.dumps({"error": "No image path provided"}))
            sys.exit(1)

        image_paths = sys.argv[1:]
        results = []

        for path in image_paths:
            res = process_image(path)
            results.append(res)

        print(json.dumps(results, ensure_ascii=False))
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
