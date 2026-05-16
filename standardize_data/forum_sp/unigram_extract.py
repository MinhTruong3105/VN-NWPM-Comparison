import csv
import json
import os
import re
import urllib.request
from collections import Counter


def download_if_missing(url, filename):
    """Tự động tải file từ điển từ nguồn mở nếu trong thư mục chưa có sẵn."""
    if not os.path.exists(filename):
        print(f"[*] Không tìm thấy '{filename}' -> Đang tự động tải về...")
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req) as response, open(
                filename, "wb"
            ) as f:
                f.write(response.read())
            print(f"[+] Đã tải và lưu thành công: {filename}")
        except Exception as e:
            print(f"[!] Lỗi khi tải {filename}: {e}")


def load_dictionaries(vn_dict_path, en_dict_path):
    """Tải và gộp 2 từ điển vào một set duy nhất để tra cứu O(1)."""
    vn_url = "https://raw.githubusercontent.com/duyet/vietnamese-wordlist/master/Viet74K.txt"
    en_url = "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt"

    download_if_missing(vn_url, vn_dict_path)
    download_if_missing(en_url, en_dict_path)

    combined_vocab = set()
    print("\n[*] Đang nạp từ điển Tiếng Việt và Tiếng Anh vào bộ nhớ...")

    try:
        with open(vn_dict_path, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip().lower().replace("_", " ")
                if word:
                    combined_vocab.add(word)
        print(f"  -> Đã nạp {len(combined_vocab):,} từ/cụm từ Tiếng Việt.")
    except FileNotFoundError:
        print(f"[!] Lỗi: Không thể đọc file từ điển VN ({vn_dict_path}).")

    initial_count = len(combined_vocab)
    try:
        with open(en_dict_path, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip().lower()
                if word:
                    combined_vocab.add(word)
        print(
            f"  -> Đã bổ sung {len(combined_vocab) - initial_count:,} từ Tiếng Anh."
        )
    except FileNotFoundError:
        print(f"[!] Lỗi: Không thể đọc file từ điển EN ({en_dict_path}).")

    print(
        f"[+] Tổng quy mô từ điển chuẩn: {len(combined_vocab):,} từ (đã gộp trùng)."
    )
    return combined_vocab


def extract_tokens(text):
    """Xử lý text và tách thành danh sách các từ thuần túy (không lấy số riêng lẻ)."""
    text = re.sub(r"<url>|https?://\S+|www\.\S+", " ", str(text).lower())
    raw_tokens = re.findall(
        r"[a-zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ0-9]+",
        text,
    )
    # Lọc bỏ token thuần số
    return [t for t in raw_tokens if not t.isdigit()]


def export_to_csv(filename, counter_data, min_freq=5, is_bigram=False):
    """Xuất dữ liệu ra file CSV."""
    filtered_sorted = sorted(
        [(k, v) for k, v in counter_data.items() if v >= min_freq],
        key=lambda x: x[1],
        reverse=True,
    )

    col_name = "bigram" if is_bigram else "unigram"

    with open(filename, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([col_name, "frequency"])
        writer.writerows(filtered_sorted)

    return filtered_sorted


def main():
    input_file = "clean.txt"
    vn_dict_file = "vietnamese_dict.txt"
    en_dict_file = "english_dict.txt"

    output_unigram_csv = "oov_unigrams_v2.csv"
    output_bigram_csv = "oov_bigrams_v2.csv"

    standard_vocab = load_dictionaries(vn_dict_file, en_dict_file)
    if not standard_vocab:
        print("[!] Từ điển trống. Dừng chương trình.")
        return

    oov_unigrams = Counter()
    oov_bigrams = Counter()

    print(f"\n[*] Đang quét file '{input_file}' với logic N-gram ưu tiên...")

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                tokens = extract_tokens(line)
                if not tokens:
                    continue

                n = len(tokens)
                part_of_standard_ngram = [False] * n

                # --- BƯỚC 1: ƯU TIÊN QUÉT BIGRAM TRƯỚC ---
                for i in range(n - 1):
                    w1, w2 = tokens[i], tokens[i + 1]
                    bigram = f"{w1} {w2}"

                    # KIỂM TRA: Nếu cụm ghép lại LÀ MỘT TỪ CHUẨN (VD: 'băng thông', 'thi công')
                    if bigram in standard_vocab:
                        # Đánh dấu 2 từ này đã thuộc cụm có nghĩa, không xem là từ lẻ bị OOV
                        part_of_standard_ngram[i] = True
                        part_of_standard_ngram[i + 1] = True
                    else:
                        # Nếu cụm ghép không chuẩn -> Kiểm tra xem nó có phải cụm lóng/teencode (VD: 'k dc')
                        # Tiêu chí: Cả 2 từ cấu thành đều không phải từ chuẩn
                        if (
                            w1 not in standard_vocab
                            and w2 not in standard_vocab
                        ):
                            oov_bigrams[bigram] += 1

                # --- BƯỚC 2: QUÉT UNIGRAM (ĐÃ TRỪ CÁC TỪ THUỘC N-GRAM CHUẨN) ---
                for i in range(n):
                    token = tokens[i]
                    # Chỉ đưa vào OOV Unigram nếu:
                    # 1. Nó CHƯA được ghép vào một bigram chuẩn nào ở bước trên
                    # 2. Bản thân nó không nằm trong từ điển chuẩn
                    if (
                        not part_of_standard_ngram[i]
                        and token not in standard_vocab
                    ):
                        oov_unigrams[token] += 1

        print("\n[+] Quét hoàn tất!")
        print(f"  -> Phát hiện {len(oov_unigrams):,} Unigram OOV duy nhất.")
        print(f"  -> Phát hiện {len(oov_bigrams):,} Bigram OOV duy nhất.")

        print("\n[*] Đang xuất file báo cáo...")
        top_uni = export_to_csv(output_unigram_csv, oov_unigrams, min_freq=10)
        print(
            f"[+] Đã lưu Unigram OOV (freq >= 10) vào: {output_unigram_csv}"
        )

        top_bi = export_to_csv(
            output_bigram_csv, oov_bigrams, min_freq=5, is_bigram=True
        )
        print(f"[+] Đã lưu Bigram OOV (freq >= 5) vào: {output_bigram_csv}")

        print("\n--- TOP 10 UNIGRAM OOV (ĐÃ LỌC N-GRAM) ---")
        for k, v in top_uni[:10]:
            print(f"  {k}: {v}")

        print("\n--- TOP 10 BIGRAM OOV (SIÊU SẠCH) ---")
        for k, v in top_bi[:10]:
            print(f"  {k}: {v}")

    except FileNotFoundError:
        print(f"[!] Lỗi: Không tìm thấy file dữ liệu '{input_file}'.")


if __name__ == "__main__":
    main()