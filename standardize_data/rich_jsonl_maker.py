import glob
import os
import json
import pyvi
from pyvi import ViTokenizer

# --- CẤU HÌNH ĐƯỜNG DẪN ---
current_file_path = os.path.abspath(__file__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))

# Input từ Module 1
INPUT_DIR = os.path.join(BASE_DIR, "data", "processed", "base")
# Output cuối cùng cho training
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "processed", "rich_jsonl", "final_rich_dataset.jsonl")

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

# Cấu hình Buffer
BATCH_SIZE = 10000 

def run_module_2():
    if not os.path.exists(INPUT_DIR):
        print(f"[-] Lỗi: Không tìm thấy thư mục đầu vào tại {INPUT_DIR}")
        return

    jsonl_files = glob.glob(os.path.join(INPUT_DIR, "*.jsonl"))
    
    if not jsonl_files:
        print(f"[-] Không tìm thấy file JSONL nào trong {INPUT_DIR}")
        return

    total_processed = 0
    buffer = [] # Bộ nhớ đệm tạm thời

    print("\nBẮT ĐẦU MODULE 2: WORD SEGMENTATION (PYVI) & BATCH WRITING")
    print(f"[*] Tìm thấy {len(jsonl_files)} file cần xử lý.")
    
    try:
        # Mở file với chế độ ghi đè 'w'
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f_out:
            
            for file_path in jsonl_files:
                file_name = os.path.basename(file_path)
                print(f"\n[>] Đang xử lý file: {file_name}")
                
                with open(file_path, 'r', encoding='utf-8') as f_in:
                    for line in f_in:
                        if not line.strip():
                            continue
                            
                        data = json.loads(line)
                        raw_text = data.get("raw_text", "")
                        
                        if not raw_text:
                            continue
                        
                        # BƯỚC 1: Word Segmentation bằng PyVi (Tốc độ cao)
                        # Giữ nguyên dấu câu để model học ngữ cảnh tốt hơn
                        segmented_text = ViTokenizer.tokenize(raw_text)
                        
                        # BƯỚC 2: Cập nhật dữ liệu (BỎ hoàn toàn clean_text)
                        enriched_data = {
                            "source": data.get("source"),
                            "domain": data.get("domain"),
                            "raw_text": raw_text,
                            "segmented_text": segmented_text
                        }
                        
                        # BƯỚC 3: Đưa vào Buffer thay vì ghi ngay
                        buffer.append(json.dumps(enriched_data, ensure_ascii=False) + "\n")
                        total_processed += 1
                        
                        # BƯỚC 4: Kiểm tra và xả (Flush) buffer xuống đĩa
                        if len(buffer) >= BATCH_SIZE:
                            f_out.writelines(buffer)
                            buffer.clear() # Giải phóng RAM
                            print(f"    [...] Đã xử lý {total_processed:,} dòng.")

            # Ghi nốt phần dư còn lại trong buffer sau khi hết vòng lặp
            if buffer:
                f_out.writelines(buffer)
                buffer.clear()

        print(f"\n--- HOÀN THÀNH MODULE 2 ---")
        print(f"[+] Tổng số bản ghi đã được Word Segment: {total_processed:,}")
        print(f"[+] Dữ liệu cuối cùng (Rich Dataset) lưu tại: {OUTPUT_FILE}")
        
    except Exception as e:
        print(f"\n[!] LỖI TRONG QUÁ TRÌNH XỬ LÝ: {e}")

if __name__ == "__main__":
    # Cài đặt pyvi nếu chưa có: pip install pyvi
    run_module_2()