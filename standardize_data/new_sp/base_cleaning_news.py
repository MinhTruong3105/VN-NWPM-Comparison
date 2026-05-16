import re
import unicodedata
import os
import hashlib
import json
import glob

# --- CẤU HÌNH ĐƯỜNG DẪN ---
current_file_path = os.path.abspath(__file__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))

# 3. Định nghĩa các đường dẫn dựa trên BASE_DIR
INPUT_DIR = os.path.join(BASE_DIR, "data", "raw", "voz_forum")
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "processed", "base", "voz_base_cleaned.jsonl")

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

def clean_and_format_text(text):
    """
    Làm sạch và chuẩn hóa văn bản (Regex Level 1):
    Fix khoảng trắng ẩn, ngoặc kép lệch, xóa URL/Email rác, và chuẩn hóa dấu câu an toàn.
    """
    if not text:
        return ""
    
    text = text.replace('\xa0', ' ')
    text = re.sub(r'[“”]', '"', text)
    text = unicodedata.normalize('NFC', text)
    
    # Loại bỏ URL và Email rác
    text = re.sub(r'https?\s*:\s*/\s*/\s*\S+', ' ', text)
    text = re.sub(r'\S+@\S+\.\S+', ' ', text)
    
    # [CẬP NHẬT 1]: Chuẩn hóa dấu chấm lửng thành 1 ký tự chuẩn
    text = re.sub(r'\.{3,}', '…', text)
    
    # Xóa khoảng trắng TRƯỚC các dấu câu
    text = re.sub(r'\s+([,.:;!?…])', r'\1', text)
    
    # [CẬP NHẬT 2]: Thêm khoảng trắng SAU các dấu , : ; ! ? (Không áp dụng cho dấu chấm)
    # Ràng buộc: Chỉ chèn nếu sau nó là các ký tự chữ/số (không dính vào ngoặc kép hoặc số)
    text = re.sub(r'([,:;!?])(?=[^\s\d"”\)])', r'\1 ', text)
    
    # [CẬP NHẬT 3]: Xử lý an toàn dấu chấm (.)
    # Dùng lookbehind & lookahead: Chỉ chèn khoảng trắng nếu kết thúc là chữ thường (vd: 'm')
    # và bắt đầu câu mới là chữ hoa (vd: 'N'). Điều này bảo vệ an toàn cho TP.HCM, Th.S, PGS.TS...
    text = re.sub(r'(?<=[a-zà-ỹ])\.(?=[A-ZÀ-Ỹ])', '. ', text)
    
    # Gom các khoảng trắng thừa
    text = re.sub(r' +', ' ', text).strip()
    
    # Xử lý ngoặc kép "mồ côi"
    if text.count('"') % 2 != 0:
        text = text.replace('"', '')
        
    return text.strip()

def is_quality_text(text):
    """
    Bộ lọc Heuristic: Loại bỏ câu quá ngắn (< 15 từ) hoặc chứa > 5% ký tự rác.
    """
    words = text.split()
    if len(words) < 15:
        return False
        
    special_chars = len(re.findall(r'[^\w\s.,!?;:\-"\'()/%…]', text))
    if special_chars > len(text) * 0.05:
        return False
        
    return True

def get_md5_hash(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def run_module_1():
    if not os.path.exists(INPUT_DIR):
        print(f"[-] Lỗi: Không tìm thấy thư mục đầu vào tại {INPUT_DIR}")
        return

    all_files = glob.glob(os.path.join(INPUT_DIR, "*.txt"))
    txt_files = [f for f in all_files if not os.path.basename(f).startswith("visited_")]
    
    if not txt_files:
        print(f"[-] Không tìm thấy file dữ liệu hợp lệ nào trong {INPUT_DIR}")
        return

    seen_hashes = set()
    total_processed_lines = 0
    total_valid_records = 0

    print(" BẮT ĐẦU MODULE 1: BASE CLEANING & CONSOLIDATION ")
    print(f"[*] Tìm thấy {len(txt_files)} file cần xử lý.")
    
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f_out:
            for file_path in txt_files:
                file_name = os.path.basename(file_path)
                print(f"\n[>] Đang xử lý file: {file_name}")
                
                # [CẬP NHẬT 4]: Trích xuất 'domain' từ tên file
                # Ví dụ: 'thanhnien_edu.txt' -> 'edu'
                # [CẬP NHẬT 4]: Trích xuất 'source' và 'domain' từ tên file
                # Ví dụ: 'vnx_tech.txt' -> source = 'news_vnx', domain = 'tech'
                # Ví dụ: 'thanhnien_edu.txt' -> source = 'news_thanhnien', domain = 'edu'
                match = re.search(r'([a-zA-Z0-9]+)_([a-zA-Z0-9]+)\.txt$', file_name)
                
                if match:
                    # Gắn thêm tiền tố 'news_' để phân biệt hẳn với 'forum_' sau này
                    source = f"forum_{match.group(1).lower()}" 
                    domain = match.group(2).lower()
                else:
                    source = "news_unknown"
                    domain = "unknown"
                
                file_processed_lines = 0
                file_valid_records = 0
                
                with open(file_path, 'r', encoding='utf-8') as f_in:
                    for line in f_in:
                        total_processed_lines += 1
                        file_processed_lines += 1
                        raw_text = line.strip()
                        
                        if not raw_text:
                            continue
                            
                        cleaned_text = clean_and_format_text(raw_text)
                        
                        if is_quality_text(cleaned_text):
                            line_hash = get_md5_hash(cleaned_text)
                            if line_hash not in seen_hashes:
                                seen_hashes.add(line_hash)
                                
                                # [CẬP NHẬT 5]: Đóng gói JSON với trường Metadata
                                json_record = {
                                    "source": source,
                                    "domain": domain,
                                    "raw_text": cleaned_text
                                }
                                f_out.write(json.dumps(json_record, ensure_ascii=False) + "\n")
                                
                                file_valid_records += 1
                                total_valid_records += 1
                                
                print(f"    -> Lĩnh vực: [{domain.upper()}] | Đã quét {file_processed_lines:,} dòng, thu được {file_valid_records:,} dòng sạch.")

        print(f"\n---  HOÀN THÀNH MODULE 1  ---")
        print(f"[+] Tổng số dòng dữ liệu thô đã quét: {total_processed_lines:,}")
        print(f"[+] Số dòng sạch duy nhất (đã loại trùng lặp): {total_valid_records:,}")
        if total_processed_lines > 0:
            print(f"[+] Tỷ lệ giữ lại toàn cục: {(total_valid_records/total_processed_lines)*100:.2f}%")
        print(f"[+] File đã gom và lưu tại: {OUTPUT_FILE}")

    except Exception as e:
        print(f"\n[!] LỖI NGHIÊM TRỌNG TRONG QUÁ TRÌNH XỬ LÝ: {e}")

if __name__ == "__main__":
    run_module_1()