import re
import unicodedata
from pathlib import Path

# ── Cấu hình đường dẫn (Đã sửa cho máy tính cá nhân) ─────────────────
# Lấy đường dẫn của thư mục hiện tại mà bạn đang mở terminal (D:\data_voz)
BASE_DIR = Path(__file__).parent 

INPUT_FILES = [
    "eco_teencode_processed.txt",
    "ent_teencode_processed.txt",
    "tech_teencode_processed.txt"
]

def remove_unbalanced_brackets(text):
    if not text: return ""
    
    stack = []
    to_remove = set()
    
    # Bước 1: Tìm các dấu ngoặc thừa
    for i, char in enumerate(text):
        if char == '(':
            stack.append(i)
        elif char == ')':
            if stack:
                stack.pop()
            else:
                # Dấu đóng thừa (không có mở trước đó)
                to_remove.add(i)
                
    # Bước 2: Gom các dấu mở không bao giờ được đóng
    while stack:
        to_remove.add(stack.pop())
        
    # Bước 3: Tạo chuỗi mới loại bỏ các vị trí lỗi
    return "".join([char for i, char in enumerate(text) if i not in to_remove])

import re
import unicodedata

def final_polish(text):
    if not text: return ""
    
    # 1. Chuẩn hóa Unicode NFC
    text = unicodedata.normalize("NFC", text.strip())
    
    # 2. Xử lý dấu ngoặc bừa bãi bằng Stack
    text = remove_unbalanced_brackets(text)
    
    # 3. Xử lý khoảng cách trước dấu câu (giữ lại cụm ... không bị tách)
    # Xóa space trước các dấu câu đơn lẻ
    text = re.sub(r'\s+([.?!:;])', r'\1', text)
    # Đảm bảo dấu ba chấm không bị dính space ở giữa (ví dụ . . . -> ...)
    text = re.sub(r'\.\s*\.\s*\.', '...', text)
    
    # 4. Chuẩn hóa viết hoa có điều kiện
    # Regex tách: tìm "..." hoặc các dấu [.?!] đơn lẻ
    # Dùng capturing group () để giữ lại dấu trong danh sách split
    tokens = re.split(r'(\.\.\.|[.?!])', text)
    
    new_parts = []
    # Mặc định chữ cái đầu tiên của cả đoạn phải viết hoa
    capitalize_next = True 
    
    for token in tokens:
        if not token:
            continue
            
        # Nếu token là dấu ngắt
        if token in ['.', '?', '!']:
            new_parts.append(token)
            capitalize_next = True # Sau dấu chấm đơn/hỏi/than -> VIẾT HOA
        elif token == '...':
            new_parts.append(token)
            capitalize_next = False # Sau dấu ba chấm -> KHÔNG viết hoa (giữ nguyên)
        else:
            # Nếu là nội dung chữ
            content = token.lstrip()
            # Lấy phần khoảng trắng bị lstrip ra để bù lại sau
            whitespace = token[:len(token) - len(content)]
            
            if content and capitalize_next:
                content = content[0].upper() + content[1:]
                capitalize_next = False # Reset sau khi đã viết hoa
            
            new_parts.append(whitespace + content)
    
    text = "".join(new_parts).strip()

    # 5. Thêm dấu chấm cuối dòng nếu thiếu (và không phải đang là ...)
    if text and text[-1] not in ['.', '?', '!'] and not text.endswith('...'):
        text += '.'
        
    return text

# ── Thực hiện xử lý ────────────────────────────────────────────────
print("🚀 Bắt đầu quá trình làm sạch cuối cùng...")

for file_in_name in INPUT_FILES:
    # Tìm file ngay tại thư mục D:\data_voz
    input_path = BASE_DIR / file_in_name
    
    # Tạo tên file output: eco_clean.txt, ent_clean.txt, tech_clean.txt
    output_name = file_in_name.replace("_teencode_processed.txt", "_clean.txt")
    output_path = BASE_DIR / output_name
    
    if not input_path.exists():
        print(f"⚠️ Bỏ qua: Không tìm thấy file {file_in_name} tại {BASE_DIR}")
        continue
        
    print(f"⏳ Đang xử lý {file_in_name}...")
    
    with open(input_path, "r", encoding="utf-8") as fin, \
         open(output_path, "w", encoding="utf-8") as fout:
        
        for line in fin:
            line_content = line.strip()
            if line_content:
                cleaned_line = final_polish(line_content)
                fout.write(cleaned_line + "\n")
                
    print(f"✅ Hoàn tất! File sạch lưu tại: {output_path.name}")

print("\n✨ Tất cả dữ liệu đã được làm sạch và chuẩn hóa.")