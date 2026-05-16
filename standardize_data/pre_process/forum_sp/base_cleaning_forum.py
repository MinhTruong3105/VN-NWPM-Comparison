import re
import unicodedata
import os
import hashlib
import json
import glob
import html

# --- CẤU HÌNH ĐƯỜNG DẪN ---
current_file_path = os.path.abspath(__file__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))

# Trỏ thẳng vào thư mục chứa các file sp_process
INPUT_DIR = os.path.join(BASE_DIR, "data", "forum_sp_process")
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "processed", "base", "forum_base_cleaned.jsonl")

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)


def remove_forum_signatures(text):
    """Xóa các cấu trúc rác đặc thù của diễn đàn"""
    # Xóa nội dung trong thẻ QUOTE
    text = re.sub(r'\[QUOTE\].*?\[/QUOTE\]', ' ', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Xóa chữ ký thiết bị phổ biến
    signatures = [
        r'Sent from (my )?[a-zA-Z0-9 ]+ using .*',
        r'Sent from .* via .*',
        r'via theNEXTvoz.*',
        r'Gửi từ .* bằng .*'
    ]
    for sig in signatures:
        text = re.sub(sig, ' ', text, flags=re.IGNORECASE)
        
    return text

def clean_forum_text(text):
    """Pipeline làm sạch kết hợp Entity Packaging"""
    if not text: return ""
    
    # Bước 1: Xóa rác Forum & Basic Format
    text = html.unescape(text)
    text = remove_forum_signatures(text)
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'https?\s*:\s*/\s*/\s*\S+', ' ', text)
    text = re.sub(r'\S+@\S+\.\S+', ' ', text)
    
    # Chuyển chữ thường để dễ map entity
    text = text.lower()
    
    # Bước 2: Entity Packaging (Bảo vệ thuật ngữ Công nghệ)
    # Gom số và đơn vị đo lường (1080 p -> 1080p, 144 hz -> 144hz)
    text = re.sub(r'\b(\d+)\s*(k|vnd|đ|nd|th|st|rd|gb|tb|hz|mhz|p|fps)\b', r'\1\2', text)
    text = re.sub(r'(?<![-/a-z])\b(\d+)\s*["\']', r'\1inch ', text)
    
    # Đóng gói CPU / GPU (i5 12400f -> i5_12400f, rtx 3060 ti -> rtx_3060_ti)
    text = re.sub(r'\b(i|r)\s*(\d)\s*[-_]?\s*(\d{4,5})\s*([kxf]{0,2})\b', r'\1\2_\3\4', text)
    text = re.sub(
        r'\b(rtx|gtx|rx|hd|gt)\s*[-_]?\s*(\d{3,4})\s*[-_]?\s*(ti|xt|super)?\b', 
        lambda m: m.group(1) + '_' + m.group(2) + ('_' + m.group(3) if m.group(3) else ''), 
        text
    )
    
    # Đóng gói đồ Gear (logitech g102 -> logitech_g102)
    text = re.sub(r'\b(logitech|corsair|fuhlen|mchose|vxe|razer|dareu)\s+([a-z0-9]+)\b', r'\1_\2', text)
    
    
    # Bước 3: Chỉnh sửa Dấu câu
    text = re.sub(r'\.{3,}', '…', text)
    text = re.sub(r'\s+([,.:;!?…])', r'\1', text)
    text = re.sub(r'([,:;!?])(?=[^\s\d"”\)])', r'\1 ', text)
    text = re.sub(r' +', ' ', text).strip()
    
    return text

def is_quality_forum_text(text):
    """Lọc các dòng lỗi, code dump, hoặc quá ngắn"""
    words = text.split()
    if len(words) < 4:
        return False
        
    # Lọc rác code dump 
    trash_keywords = {
        "script", "html", "div", "doctype", "src", "href", "interface", 
        "ethernet", "pppoe", "wlan", "ssid", "dhcp", "mikrotik", 
        "hotspot", "default-name", "supplicant", "wpa2", "ap-bridge"
    }
    if len(trash_keywords.intersection(set(words))) >= 2:
        return False
        
    # Lọc Spam (Lặp từ liên tục)
    if any(words.count(w) > 5 for w in set(words) if len(w) > 1):
        return False
        
    return True

def run_forum_base_clean():
    if not os.path.exists(INPUT_DIR):
        print(f"[-] Lỗi: Không tìm thấy thư mục: {INPUT_DIR}")
        return

    # [CẬP NHẬT]: Chỉ lấy các file kết thúc chính xác bằng normalized.txt
    # Điều này sẽ tự động loại bỏ các file có đuôi cleaned.txt
    txt_files = glob.glob(os.path.join(INPUT_DIR, "*_normalized.txt"))
    
    if not txt_files:
        print(f"[-] Không tìm thấy file *_normalized.txt nào trong {INPUT_DIR}")
        return

    seen_hashes = set()
    total_processed = total_valid = 0

    print("BẮT ĐẦU MODULE 1: FORUM BASE CLEANING")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f_out:
        for file_path in txt_files:
            file_name = os.path.basename(file_path)
            
            # Trích xuất Metadata (Ví dụ: voz_tech.txt -> source: forum_voz, domain: tech)
            match = re.search(r'^data_([^_]+)_([^_]+)_normalized\.txt$', file_name)
            if match:
                source = f"forum_{match.group(1).lower()}" 
                domain = match.group(2).lower()   
            else:
                source, domain = "forum_unknown", "unknown"
                
            print(f"\n[>] Đang xử lý: {file_name} | Nguồn: {source} | Lĩnh vực: {domain}")
            
            with open(file_path, 'r', encoding='utf-8') as f_in:
                for line in f_in:
                    total_processed += 1
                    raw_text = line.strip()
                    
                    cleaned_text = clean_forum_text(raw_text)
                    
                    if is_quality_forum_text(cleaned_text):
                        line_hash = hashlib.md5(cleaned_text.encode('utf-8')).hexdigest()
                        if line_hash not in seen_hashes:
                            seen_hashes.add(line_hash)
                            
                            # Ghi ra JSONL chung Schema
                            json_record = {
                                "source": source,
                                "domain": domain,
                                "raw_text": cleaned_text
                            }
                            f_out.write(json.dumps(json_record, ensure_ascii=False) + "\n")
                            total_valid += 1

    print(f"\n---HOÀN THÀNH---")
    print(f"[+] Dòng thô: {total_processed:,} | Dòng sạch: {total_valid:,}")
    print(f"[+] Lưu tại: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_forum_base_clean()