import json
import re
import unicodedata
from pathlib import Path

# ── 1. Cấu hình đường dẫn ──────────────────────────────────────────
TEENCODE_JSON = "teencode.json"
FILES_TO_PROCESS = ["eco.txt", "ent.txt", "tech.txt"]

def load_teencode_map(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Lấy đúng mục unigrams bạn yêu cầu
    return data.get("teencode_unigrams_meaningful", {})

def clean_and_translate(text, mapping):
    # Chuẩn hóa về NFC để xử lý các ký tự tiếng Việt chuẩn xác
    text = unicodedata.normalize("NFC", text)
    
    # Sắp xếp từ dài nhất đến ngắn nhất để tránh dịch đè (ví dụ 'tphcm' trước 'hcm')
    sorted_keys = sorted(mapping.keys(), key=len, reverse=True)
    
    for key in sorted_keys:
        # Sử dụng Regex \b để khớp chính xác từ đứng độc lập
        # re.IGNORECASE giúp khớp cả chữ hoa và chữ thường
        pattern = re.compile(r'\b' + re.escape(key) + r'\b', re.IGNORECASE)
        text = pattern.sub(mapping[key], text)
    
    return text

# ── 2. Thực hiện xử lý ─────────────────────────────────────────────
if not Path(TEENCODE_JSON).exists():
    print(f"❌ Không tìm thấy file {TEENCODE_JSON}. Hãy đảm bảo bạn đã upload file này.")
else:
    # Load từ điển từ file JSON
    unigram_map = load_teencode_map(TEENCODE_JSON)
    print(f"📦 Đã nạp {len(unigram_map)} quy tắc unigram từ file JSON.")

    for file_name in FILES_TO_PROCESS:
        input_path = Path(f"{file_name}")
        output_path = Path(f"{file_name.replace('.txt', '_teencode_processed.txt')}")
        
        if not input_path.exists():
            print(f"❌ Bỏ qua {file_name} (không tìm thấy file).")
            continue
        
        print(f"⏳ Đang xử lý: {file_name}...")
        
        with open(input_path, "r", encoding="utf-8") as fin, \
             open(output_path, "w", encoding="utf-8") as fout:
            
            for line in fin:
                # Dịch teencode sang tiếng Việt chuẩn
                cleaned_line = clean_and_translate(line, unigram_map)
                fout.write(cleaned_line)
                
        print(f"✅ Hoàn tất! File đã dịch: {output_path.name}")

    print("\n🚀 Quá trình chuẩn hóa hoàn tất.")