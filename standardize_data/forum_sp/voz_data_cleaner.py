#!/usr/bin/env python3
"""
VOZ Data Cleaner — Pipeline làm sạch hoàn chỉnh
================================================
Thực hiện đúng pipeline đã phân tích:

  Bước 1 — Lọc bỏ hoàn toàn:
    • Spam / quảng cáo
    • Quá ngắn  (<15 từ)
    • Terminal commands (lệnh kỹ thuật lẫn vào)

  Bước 2 — Làm sạch in-place (giữ sample, sửa nội dung):
    • Xóa signature app (via theNEXTvoz / Sent from ...)
    • Thay URL → <URL>  (trừ Facebook-block → xóa hẳn đoạn đó)
    • Xóa metadata VOZ (Post in thread, timestamp)
    • Rút gọn ký tự lặp  (haaaa → haa)
    • Xóa emoticon văn bản  (:v, )))  ...)
    • Chuẩn hóa khoảng trắng thừa

  Bước 3 — Profanity: GIỮ NGUYÊN (lý do xem README)

Dùng:
  python voz_data_cleaner.py --input raw.txt --output clean.txt
  python voz_data_cleaner.py --data_voz_giai_tri_merged_raw.txt --output clean.txt --log cleaning_log.json
  python voz_data_cleaner.py --input raw.jsonl --output clean.jsonl --key text
"""

import re
import json
import argparse
import sys
from pathlib import Path
from dataclasses import dataclass, field
from collections import Counter


# ══════════════════════════════════════════════════════════════════
#  CẤU HÌNH — chỉnh tại đây nếu cần
# ══════════════════════════════════════════════════════════════════

MIN_WORD_COUNT = 15          # Bước 1: lọc sample quá ngắn
MAX_CHAR_COUNT = 5000        # Bước 2: sample dài → chỉ cắt, không xóa
REPEATED_CHAR_KEEP = 2       # "haaaa" → "haa"  (giữ lại N ký tự)


# ══════════════════════════════════════════════════════════════════
#  PATTERNS — BƯỚC 1: LỌC BỎ HOÀN TOÀN
# ══════════════════════════════════════════════════════════════════

# Spam / quảng cáo affiliate rõ ràng
SPAM_PATTERNS = [
    re.compile(r'byvn\.net/\S+', re.I),
    re.compile(r'share cho m[aấ]y (th[iíy]m|b[aá]c|[aâ]nh em) con deal', re.I),
    re.compile(r'(rút gọn|áp\s+dc|áp\s+được)\s+(full\s+)?mã\s+giảm', re.I),
    re.compile(r'mã\s+giảm\s+giá.{0,30}(sale|giảm)\s*\d+[%k]', re.I),
    re.compile(r'chuột\s+bạch\s+xem', re.I),
    re.compile(r'quốc\s+hàng\s+của\s+vozer', re.I),
]

# Terminal / lệnh kỹ thuật — lẫn từ thread Linux/Dev
TERMINAL_PATTERNS = [
    re.compile(r'^(sudo|apt|pkg|pip|npm|git|cd|ls|rm|mv|cp|chmod|chown|grep|awk|sed|curl|wget)\s', re.I),
    re.compile(r'^(pkg upgrade|su|debugging|force-vp9|header-switch)$', re.I),
    re.compile(r'^\$\s+\w+'),           # $ command
    re.compile(r'^>>>\s+\w+'),          # Python REPL
    re.compile(r'^#\s*!/\w+'),          # shebang
]


def is_spam(text: str) -> bool:
    for p in SPAM_PATTERNS:
        if p.search(text):
            return True
    return False


def is_terminal_command(text: str) -> bool:
    stripped = text.strip()
    for p in TERMINAL_PATTERNS:
        if p.match(stripped):
            return True
    return False


def is_too_short(text: str) -> bool:
    return len(text.split()) < MIN_WORD_COUNT


# ══════════════════════════════════════════════════════════════════
#  PATTERNS — BƯỚC 2: LÀM SẠCH IN-PLACE
# ══════════════════════════════════════════════════════════════════

# --- 2a. Signature app ---
SIG_PATTERNS = [
    # "via theNEXTvoz for iPhone", "via vozFApp for Android"
    re.compile(r'\bvia\s+the\w*voz\w*\s+for\s+\w+', re.I),
    # "Sent from HUAWEI NOVA 5T using vozFApp"
    re.compile(r'\bSent\s+from\s+.{3,60}\s+using\s+voz\w+', re.I),
    # "Gửi từ OnePlus 15 bằng VOZVNApp"
    re.compile(r'\bGửi\s+từ\s+.{2,60}\s+bằng\s+\w+App\b', re.I),
    # Trailing platform tags
    re.compile(r'\bvia\s+\w+\s+for\s+(iPhone|Android|iPad)\b', re.I),
]

# --- 2b. Facebook block (xóa cả đoạn mô tả, không chỉ URL) ---
FB_BLOCK_PATTERN = re.compile(
    r'Log\s+in\s+(to|or sign up to view)\s+Facebook.*?(?=\n|$)', re.I | re.S
)

# --- 2c. URL thông thường → <URL> ---
URL_PATTERN = re.compile(
    r'https?://\S+'                          # http(s)://...
    r'|(?<!\w)www\.\S+'                      # www....
    r'|(?<!\w)vn\.shp\.ee/\S+'              # vn.shp.ee/...
    r'|(?<!\w)s\.lazada\.vn/\S+'            # s.lazada.vn/...
    r'|(?<!\w)bit\.ly/\S+'                   # bit.ly/...
    r'|(?<!\w)shopee\.vn/\S+',              # shopee.vn/...
    re.I
)

# --- 2d. Metadata VOZ ---
META_PATTERNS = [
    # "Post in thread 'Hội anh em dùng Honor'"
    re.compile(r"Post\s+in\s+thread\s+['\"].+?['\"]", re.I),
    # "Replies: 32 Forum: Android"
    re.compile(r'Replies:\s*\d+\s+Forum:\s*\w+', re.I),
    # "Jan 10, 2026" / "Sep 5, 2025"
    re.compile(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+20\d{2}\b', re.I),
    # "05/09/2025"
    re.compile(r'\b\d{1,2}/\d{1,2}/20\d{2}\b'),
]

# --- 2e. Ký tự lặp (4+) → giữ lại REPEATED_CHAR_KEEP ---
REPEATED_CHAR_PATTERN = re.compile(r'(.)\1{3,}')

# --- 2f. Emoticon văn bản ---
EMOTICON_PATTERNS = [
    re.compile(r'(?<!\w):v\b', re.I),            # :v
    re.compile(r'(?<!\w):\)\s*$', re.M),         # :) cuối dòng
    re.compile(r'\){3,}'),                         # )))
    re.compile(r'(?<!\w)=\)\s*$', re.M),          # =)
    re.compile(r'(?<!\w)>\.<'),                    # >.<
    re.compile(r'(?<!\w): \w+:(?!\w)'),            # : beauty: : D:
]

# --- 2g. Emoji Unicode ---
EMOJI_PATTERN = re.compile(
    r'[\U00010000-\U0010ffff]'
    r'|[\u2600-\u27BF]'
    r'|[\u2300-\u23FF]'
    r'|[\u25A0-\u25FF]'
    r'|[\u2700-\u27BF]'
)

# --- 2h. Dấu câu quá nhiều ---
EXCESS_PUNCT_PATTERN = re.compile(r'([!?]){3,}|\.{4,}')

# --- 2i. Khoảng trắng thừa ---
WHITESPACE_PATTERN = re.compile(r'[ \t]{2,}')


# ══════════════════════════════════════════════════════════════════
#  THỐNG KÊ
# ══════════════════════════════════════════════════════════════════

@dataclass
class CleanStats:
    total_read:         int = 0
    dropped_spam:       int = 0
    dropped_short:      int = 0
    dropped_terminal:   int = 0
    dropped_empty:      int = 0   # sau khi clean còn trống
    cleaned_signature:  int = 0
    cleaned_url:        int = 0
    cleaned_fb_block:   int = 0
    cleaned_meta:       int = 0
    cleaned_repeated:   int = 0
    cleaned_emoticon:   int = 0
    cleaned_emoji:      int = 0
    cleaned_punct:      int = 0
    truncated_long:     int = 0
    total_output:       int = 0

    def summary(self) -> dict:
        dropped = self.dropped_spam + self.dropped_short + self.dropped_terminal + self.dropped_empty
        return {
            "total_input":       self.total_read,
            "total_output":      self.total_output,
            "dropped_total":     dropped,
            "dropped_pct":       _pct(dropped, self.total_read),
            "dropped_breakdown": {
                "spam":          self.dropped_spam,
                "too_short":     self.dropped_short,
                "terminal_cmd":  self.dropped_terminal,
                "empty_after_clean": self.dropped_empty,
            },
            "cleaned_in_place": {
                "signature_removed":  self.cleaned_signature,
                "url_replaced":       self.cleaned_url,
                "fb_block_removed":   self.cleaned_fb_block,
                "meta_removed":       self.cleaned_meta,
                "repeated_chars":     self.cleaned_repeated,
                "emoticon_removed":   self.cleaned_emoticon,
                "emoji_removed":      self.cleaned_emoji,
                "punct_normalized":   self.cleaned_punct,
                "long_truncated":     self.truncated_long,
            },
        }


def _pct(n, total):
    return round(n / total * 100, 2) if total else 0


# ══════════════════════════════════════════════════════════════════
#  HÀM LÀM SẠCH CHÍNH
# ══════════════════════════════════════════════════════════════════

def clean_text(text: str, stats: CleanStats) -> str:
    """
    Làm sạch 1 sample in-place.
    Trả về chuỗi đã sạch (có thể rỗng nếu không còn nội dung).
    """
    original = text

    # 2a — Xóa signature app
    new = text
    for p in SIG_PATTERNS:
        new = p.sub('', new)
    if new != text:
        stats.cleaned_signature += 1
    text = new

    # 2b — Xóa Facebook block trước (dài, cần ưu tiên trước URL thường)
    new = FB_BLOCK_PATTERN.sub('', text)
    if new != text:
        stats.cleaned_fb_block += 1
    text = new

    # 2c — Thay URL → <URL>
    new = URL_PATTERN.sub('<URL>', text)
    if new != text:
        stats.cleaned_url += 1
    text = new

    # 2d — Xóa metadata VOZ
    new = text
    for p in META_PATTERNS:
        new = p.sub('', new)
    if new != text:
        stats.cleaned_meta += 1
    text = new

    # 2e — Rút gọn ký tự lặp
    def collapse_repeated(m):
        ch = m.group(1)
        # Giữ dấu câu ở 1 ký tự, chữ/số ở REPEATED_CHAR_KEEP
        if ch in '.!?-_~':
            return ch
        return ch * REPEATED_CHAR_KEEP

    new = REPEATED_CHAR_PATTERN.sub(collapse_repeated, text)
    if new != text:
        stats.cleaned_repeated += 1
    text = new

    # 2f — Xóa emoticon văn bản
    new = text
    for p in EMOTICON_PATTERNS:
        new = p.sub('', new)
    if new != text:
        stats.cleaned_emoticon += 1
    text = new

    # 2g — Xóa emoji Unicode
    new = EMOJI_PATTERN.sub('', text)
    if new != text:
        stats.cleaned_emoji += 1
    text = new

    # 2h — Chuẩn hóa dấu câu quá nhiều  "!!!" → "!"
    new = EXCESS_PUNCT_PATTERN.sub(lambda m: m.group(0)[0], text)
    if new != text:
        stats.cleaned_punct += 1
    text = new

    # 2i — Chuẩn hóa khoảng trắng
    text = WHITESPACE_PATTERN.sub(' ', text)
    text = text.strip()

    # 2j — Cắt nếu quá dài (cắt theo câu, không cắt cứng)
    if len(text) > MAX_CHAR_COUNT:
        text = _truncate_by_sentence(text, MAX_CHAR_COUNT)
        stats.truncated_long += 1

    return text


def _truncate_by_sentence(text: str, max_chars: int) -> str:
    """Cắt text tại ranh giới câu gần nhất với max_chars."""
    if len(text) <= max_chars:
        return text
    # Tìm dấu câu cuối cùng trước giới hạn
    chunk = text[:max_chars]
    last_stop = max(
        chunk.rfind('.'),
        chunk.rfind('!'),
        chunk.rfind('?'),
        chunk.rfind('\n'),
    )
    if last_stop > max_chars * 0.5:   # Chỉ cắt nếu tìm được điểm hợp lý
        return text[:last_stop + 1].strip()
    return chunk.strip()


# ══════════════════════════════════════════════════════════════════
#  PIPELINE CHÍNH
# ══════════════════════════════════════════════════════════════════

def process_file(
    input_path: str,
    output_path: str,
    json_key: str = None,
    encoding: str = 'utf-8',
    log_path: str = None,
    report_every: int = 50_000,
):
    in_path  = Path(input_path)
    out_path = Path(output_path)
    is_jsonl = in_path.suffix.lower() in ('.jsonl', '.json') or json_key

    stats = CleanStats()

    print(f"[INFO] Input  : {input_path}  ({in_path.stat().st_size / 1024**2:.1f} MB)")
    print(f"[INFO] Output : {output_path}")
    print(f"[INFO] Format : {'JSONL' if is_jsonl else 'TXT (1 dòng = 1 sample)'}")
    print()

    with (
        open(input_path,  encoding=encoding, errors='replace') as fin,
        open(output_path, 'w', encoding=encoding) as fout,
    ):
        for raw_line in fin:
            raw_line = raw_line.rstrip('\n')
            if not raw_line.strip():
                continue

            stats.total_read += 1

            # Lấy text từ JSONL nếu cần
            meta_obj = None
            if is_jsonl:
                try:
                    meta_obj = json.loads(raw_line)
                    text = meta_obj.get(json_key or 'text') or ''
                except json.JSONDecodeError:
                    text = raw_line
            else:
                text = raw_line

            # ── BƯỚC 1: Lọc bỏ hoàn toàn ──────────────────────────
            if is_spam(text):
                stats.dropped_spam += 1
                continue

            if is_terminal_command(text):
                stats.dropped_terminal += 1
                continue

            if is_too_short(text):
                stats.dropped_short += 1
                continue

            # ── BƯỚC 2: Làm sạch in-place ──────────────────────────
            cleaned = clean_text(text, stats)

            # Bỏ nếu sau khi clean còn quá ngắn hoặc rỗng
            if not cleaned or len(cleaned.split()) < MIN_WORD_COUNT:
                stats.dropped_empty += 1
                continue

            # Ghi ra output
            if is_jsonl and meta_obj is not None:
                meta_obj[json_key or 'text'] = cleaned
                fout.write(json.dumps(meta_obj, ensure_ascii=False) + '\n')
            else:
                fout.write(cleaned + '\n')

            stats.total_output += 1

            if stats.total_read % report_every == 0:
                kept_pct = _pct(stats.total_output, stats.total_read)
                print(f"  ... {stats.total_read:>9,} đọc | {stats.total_output:>9,} giữ ({kept_pct:.1f}%)")

    # ── In báo cáo ──────────────────────────────────────────────
    _print_summary(stats)

    # Xuất log JSON nếu được yêu cầu
    if log_path:
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(stats.summary(), f, ensure_ascii=False, indent=2)
        print(f"\n[INFO] Log đã lưu: {log_path}")


def _print_summary(s: CleanStats):
    total_dropped = s.dropped_spam + s.dropped_short + s.dropped_terminal + s.dropped_empty
    total_cleaned = (s.cleaned_signature + s.cleaned_url + s.cleaned_fb_block +
                     s.cleaned_meta + s.cleaned_repeated + s.cleaned_emoticon +
                     s.cleaned_emoji + s.cleaned_punct)

    print()
    print("═" * 60)
    print("  KẾT QUẢ LÀM SẠCH")
    print("═" * 60)
    print(f"  Tổng đọc vào        : {s.total_read:>10,}")
    print(f"  Tổng giữ lại        : {s.total_output:>10,}  ({_pct(s.total_output, s.total_read):.1f}%)")
    print(f"  Tổng bị lọc bỏ      : {total_dropped:>10,}  ({_pct(total_dropped, s.total_read):.1f}%)")
    print()
    print("  ── Bước 1: Lọc bỏ ──────────────────────────────────")
    print(f"    Spam/quảng cáo    : {s.dropped_spam:>10,}")
    print(f"    Lệnh terminal     : {s.dropped_terminal:>10,}")
    print(f"    Quá ngắn          : {s.dropped_short:>10,}")
    print(f"    Rỗng sau khi clean: {s.dropped_empty:>10,}")
    print()
    print("  ── Bước 2: Làm sạch in-place ────────────────────────")
    print(f"    Signature xóa     : {s.cleaned_signature:>10,}  samples")
    print(f"    URL → <URL>       : {s.cleaned_url:>10,}  samples")
    print(f"    FB block xóa      : {s.cleaned_fb_block:>10,}  samples")
    print(f"    Metadata VOZ      : {s.cleaned_meta:>10,}  samples")
    print(f"    Ký tự lặp rút gọn : {s.cleaned_repeated:>10,}  samples")
    print(f"    Emoticon xóa      : {s.cleaned_emoticon:>10,}  samples")
    print(f"    Emoji xóa         : {s.cleaned_emoji:>10,}  samples")
    print(f"    Dấu câu chuẩn hóa : {s.cleaned_punct:>10,}  samples")
    print(f"    Sample dài cắt    : {s.truncated_long:>10,}  samples")
    print(f"    Tổng samples có sửa: {total_cleaned:>9,}  samples")
    print("═" * 60)


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="VOZ Data Cleaner — Pipeline làm sạch hoàn chỉnh"
    )
    parser.add_argument('--input',    '-i', required=True,
                        help='File input (.txt hoặc .jsonl)')
    parser.add_argument('--output',   '-o', required=True,
                        help='File output đã làm sạch')
    parser.add_argument('--log',      '-l', default=None,
                        help='Xuất thống kê chi tiết ra file JSON (tuỳ chọn)')
    parser.add_argument('--key',      '-k', default=None,
                        help='Key chứa text trong JSONL (mặc định: "text")')
    parser.add_argument('--encoding', '-e', default='utf-8',
                        help='Encoding file (mặc định: utf-8)')
    parser.add_argument('--min-words', type=int, default=MIN_WORD_COUNT,
                        help=f'Ngưỡng từ tối thiểu (mặc định: {MIN_WORD_COUNT})')
    parser.add_argument('--max-chars', type=int, default=MAX_CHAR_COUNT,
                        help=f'Giới hạn ký tự tối đa (mặc định: {MAX_CHAR_COUNT})')
    args = parser.parse_args()

    # Cho phép override config qua CLI
    import sys as _sys, types as _types
    _mod = _sys.modules[__name__]
    _mod.MIN_WORD_COUNT = args.min_words
    _mod.MAX_CHAR_COUNT = args.max_chars

    process_file(
        input_path  = args.input,
        output_path = args.output,
        json_key    = args.key,
        encoding    = args.encoding,
        log_path    = args.log,
    )


if __name__ == '__main__':
    main()
