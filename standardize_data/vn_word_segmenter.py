#!/usr/bin/env python3
"""
Vietnamese Word Segmenter with Entity Protection
================================================
Thực hiện Tách từ tiếng Việt nhưng "bảo kê" các Entity đã được đóng gói từ trước.

Pipeline:
1. Masking: Quét các từ chứa dấu '_' (VD: rtx_3060_ti) -> Thay bằng [ENT_X]
2. Punctuation Spacing: Tách ranh giới dấu câu (ngon quá. -> ngon quá .)
3. Tokenization: Tách từ tiếng Việt (sinh viên -> sinh_viên)
4. Unmasking: Trả [ENT_X] về lại nguyên gốc.

Sử dụng:
python vn_word_segmenter.py --input clean.jsonl --output segmented.jsonl --key text
python vn_word_segmenter.py --input clean.txt --output segmented.txt
"""

import re
import json
import argparse
from pathlib import Path
from pyvi import ViTokenizer

# ══════════════════════════════════════════════════════════════════
# CẤU HÌNH PATTERNS
# ══════════════════════════════════════════════════════════════════

# Pattern tìm các Entity đã đóng gói (chữ/số nối với nhau bằng dấu _)
# Sử dụng \b để giới hạn ranh giới từ. VD: i5_12400f, rtx_3060_ti
ENTITY_PATTERN = re.compile(r'\b\w+(?:_\w+)+\b')

# Pattern nhận diện dấu câu cần tách rời khỏi từ
# Gồm: chấm, phẩy, chấm hỏi, chấm than, hai chấm, chấm phẩy, ngoặc...
# Tách dấu phẩy/chấm NẾU KHÔNG bị kẹp giữa 2 chữ số. Các dấu khác tách bình thường.
PUNCTUATION_PATTERN = re.compile(r'(?<!\d)([.,])(?!\d)|([!?;:()\[\]{}”"’\'])')

# Khoảng trắng thừa
WHITESPACE_PATTERN = re.compile(r'[ \t]{2,}')


# ══════════════════════════════════════════════════════════════════
# HÀM XỬ LÝ LÕI (CORE LOGIC)
# ══════════════════════════════════════════════════════════════════

def segment_text(text: str) -> str:
    """Thực hiện chuỗi Masking -> Tokenizing -> Unmasking"""
    if not text:
        return ""

    entities_map = {}
    counter = 0

    # ── BƯỚC 1: MASKING ─────────────────────────────────────────
    def mask_replacer(match):
        nonlocal counter
        original_entity = match.group(0)
        # Tạo token giả, dùng dạng __ENT_0__ để tránh trùng lặp tự nhiên
        placeholder = f"MASKEDENTTOKEN{counter}X"
        entities_map[placeholder] = original_entity
        counter += 1
        return placeholder

    # Thay thế entity bằng placeholder
    masked_text = ENTITY_PATTERN.sub(mask_replacer, text)

    # ── BƯỚC 2: PUNCTUATION SPACING ─────────────────────────────
    # Tách dấu câu ra để tokenizer không dính dấu câu vào từ
    # VD: "ngon quá." -> "ngon quá ."
    spaced_text = PUNCTUATION_PATTERN.sub(r' \1 ', masked_text)
    
    # Dọn dẹp khoảng trắng thừa do việc tách dấu câu sinh ra
    spaced_text = WHITESPACE_PATTERN.sub(' ', spaced_text).strip()

    # ── BƯỚC 3: TOKENIZATION (TÁCH TỪ TIẾNG VIỆT) ───────────────
    # Tokenizer sẽ biến khoảng trắng giữa các âm tiết của 1 từ thành '_'
    # Placeholder __ENT_0__ là 1 khối liền mạch nên sẽ không bị ảnh hưởng.
    tokenized_text = ViTokenizer.tokenize(spaced_text)

    # ── BƯỚC 4: UNMASKING ───────────────────────────────────────
    # Lặp qua dictionary và trả lại entity gốc
    unmasked_text = tokenized_text
    for placeholder, original_entity in entities_map.items():
        unmasked_text = unmasked_text.replace(placeholder, original_entity)

    # Dọn dẹp lại khoảng trắng lần cuối
    final_text = WHITESPACE_PATTERN.sub(' ', unmasked_text).strip()

    return final_text


# ══════════════════════════════════════════════════════════════════
# PIPELINE XỬ LÝ FILE
# ══════════════════════════════════════════════════════════════════

def process_file(
    input_path: str,
    output_path: str,
    json_key: str = None,
    encoding: str = 'utf-8',
    report_every: int = 50_000
):
    in_path = Path(input_path)
    is_jsonl = in_path.suffix.lower() in ('.jsonl', '.json') or json_key

    print(f"[INFO] Bắt đầu Word Segmentation...")
    print(f"[INFO] Input : {input_path}")
    print(f"[INFO] Output: {output_path}")

    total_processed = 0

    with (
        open(input_path, encoding=encoding, errors='replace') as fin,
        open(output_path, 'w', encoding=encoding) as fout,
    ):
        for raw_line in fin:
            raw_line = raw_line.rstrip('\n')
            if not raw_line.strip():
                continue

            # Lấy text từ JSONL hoặc TXT
            meta_obj = None
            if is_jsonl:
                try:
                    meta_obj = json.loads(raw_line)
                    text = meta_obj.get(json_key or 'text') or ''
                except json.JSONDecodeError:
                    text = raw_line
            else:
                text = raw_line

            # Core Logic
            segmented_text = segment_text(text)

            # Ghi ra output
            if is_jsonl and meta_obj is not None:
                meta_obj[json_key or 'text'] = segmented_text
                fout.write(json.dumps(meta_obj, ensure_ascii=False) + '\n')
            else:
                fout.write(segmented_text + '\n')

            total_processed += 1

            if total_processed % report_every == 0:
                print(f" ... Đã tách từ {total_processed:>9,} dòng")

    print(f"[+] HOÀN THÀNH. Tổng số dòng đã xử lý: {total_processed:,}")


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Vietnamese Word Segmenter with Entity Protection"
    )
    parser.add_argument('--input', '-i', required=True,
                        help='File input (.txt hoặc .jsonl)')
    parser.add_argument('--output', '-o', required=True,
                        help='File output đã tách từ')
    parser.add_argument('--key', '-k', default=None,
                        help='Key chứa text trong JSONL (mặc định: "text")')
    parser.add_argument('--encoding', '-e', default='utf-8',
                        help='Encoding file (mặc định: utf-8)')

    args = parser.parse_args()

    process_file(
        input_path=args.input,
        output_path=args.output,
        json_key=args.key,
        encoding=args.encoding
    )