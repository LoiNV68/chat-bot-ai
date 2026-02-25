import sys
import json
import cv2
import logging
import numpy as np
import paddleocr.paddleocr as pm

# --- MONKEY PATCH (Lách lỗi ngôn ngữ Layout của Paddle) ---
_orig_get_model_config = pm.get_model_config
def patched_get_model_config(type, version, model_type, lang):
    if type == "STRUCTURE" and model_type == "layout" and lang not in ['en', 'ch']:
        lang = 'en'
    return _orig_get_model_config(type, version, model_type, lang)
pm.get_model_config = patched_get_model_config

from paddleocr import PPStructure

logging.getLogger("ppocr").setLevel(logging.ERROR)

def find_table_grids_opencv(image):
    """
    Sử dụng OpenCV để dò tìm các đường kẻ ngang/dọc tạo thành bảng.
    Trả về danh sách các tọa độ [x, y, w, h] bao quanh cái bảng.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Tăng độ tương phản để làm rõ đường kẻ
    thresh = cv2.adaptiveThreshold(~gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, -2)

    # Kernel dò đường ngang và dọc (độ dài tối thiểu 50 pixel)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 50))

    h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel)
    v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel)

    # Gộp đường ngang và dọc lại sẽ ra cái khung lưới (Grid)
    mask = h_lines + v_lines
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    bboxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        # Bộ lọc: Bảng phải đủ to (Rộng > 200px, Cao > 100px) thì mới lấy
        if w > 200 and h > 100:
            bboxes.append((x, y, w, h))
            
    # Sắp xếp từ trên xuống dưới theo tọa độ y
    return sorted(bboxes, key=lambda b: b[1])


def process_table(image_path, output_json_path):
    response = {"status": "error", "tables": [], "debug_log": []}
    
    try:
        # Đọc ảnh gốc
        original_img = cv2.imread(image_path)
        if original_img is None:
            raise ValueError(f"Cannot read image: {image_path}")

        tables_html = []
        
        # 1. Khởi tạo Engine ở chế độ AI tự đoán bố cục (Layout=True)
        table_engine_layout = PPStructure(lang='vi', show_log=False, layout=True)
        result_layout = table_engine_layout(original_img)
        
        for region in result_layout:
            if region['type'] == 'table':
                tables_html.append(region['res']['html'])

        response["debug_log"].append(f"AI Layout Mode found: {len(tables_html)} tables.")

        # 2. CHẾ ĐỘ GIẢI CỨU (FALLBACK): Nếu AI bị mù vì nhiễu, gọi OpenCV ra tay!
        if len(tables_html) == 0:
            response["debug_log"].append("AI Layout failed. Activating OpenCV Grid Detection...")
            
            # Tìm tọa độ bảng bằng OpenCV
            bboxes = find_table_grids_opencv(original_img)
            response["debug_log"].append(f"OpenCV found {len(bboxes)} table grids.")
            
            # Khởi tạo Engine ở chế độ "Chỉ đọc bảng, bỏ qua phân tích bố cục" (Layout=False)
            table_engine_force = PPStructure(lang='vi', show_log=False, layout=False)
            
            for (x, y, w, h) in bboxes:
                # Cắt nới rộng ra 5 pixel mỗi viền để không lẹm mất nét kẻ
                pad = 5
                y1 = max(0, y - pad)
                y2 = min(original_img.shape[0], y + h + pad)
                x1 = max(0, x - pad)
                x2 = min(original_img.shape[1], x + w + pad)
                
                cropped_table_img = original_img[y1:y2, x1:x2]
                
                # Ép AI dịch duy nhất phần ảnh vừa cắt này sang HTML
                res_force = table_engine_force(cropped_table_img)
                
                # Vì layout=False nên res_force trả về thẳng kết quả của mảng bảng
                if len(res_force) > 0 and 'html' in res_force[0]['res']:
                    tables_html.append(res_force[0]['res']['html'])

        # === GHI KẾT QUẢ ===
        response["status"] = "success"
        response["tables"] = tables_html
        
    except Exception as e:
        response["message"] = str(e)

    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(response, f, ensure_ascii=False)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(1)
    process_table(sys.argv[1], sys.argv[2])
