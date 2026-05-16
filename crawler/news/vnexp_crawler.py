import requests
from bs4 import BeautifulSoup
import time
import random
import os
import re
import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- 1. CẤU HÌNH CƠ BẢN ---
BASE_DIR = os.path.join("data", "raw", "vnx")
os.makedirs(BASE_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(BASE_DIR, "data_vnexpress_edu1.txt")
DB_FILE = os.path.join(BASE_DIR, "crawler_state_edu.db") # Dùng SQLite thay cho file txt để lưu trạng thái & hash

START_PAGE = 1
END_PAGE = 200 
MAX_WORKERS = 3  # Giảm xuống 3 để cực kỳ an toàn, tránh bị block IP

CATEGORY_URLS = [
    # "https://vnexpress.net/kinh-doanh",
    # "https://vnexpress.net/kinh-doanh/doanh-nghiep",
    # "https://vnexpress.net/kinh-doanh/vi-mo",
    # "https://vnexpress.net/kinh-doanh/tien-cua-toi",
    # "https://vnexpress.net/kinh-doanh/hang-hoa",
    # "https://vnexpress.net/kinh-doanh/quoc-te",
    # "https://vnexpress.net/bat-dong-san",
    # "https://vnexpress.net/bat-dong-san/thi-truong",
    # "https://vnexpress.net/bat-dong-san/chinh-sach",

    # "https://vnexpress.net/khoa-hoc-cong-nghe",
    # "https://vnexpress.net/khoa-hoc-cong-nghe/chuyen-doi-so",
    # "https://vnexpress.net/khoa-hoc-cong-nghe/ai",
    # "https://vnexpress.net/khoa-hoc-cong-nghe/thiet-bi",

    # "https://vnexpress.net/giai-tri/sach",
    # "https://vnexpress.net/giai-tri/phim",
    # "https://vnexpress.net/giai-tri/nhac",
    # "https://vnexpress.net/giai-tri/san-khau-my-thuat",
    # "https://vnexpress.net/bong-da",
    # "https://vnexpress.net/the-thao/cac-mon-khac",
    
    # "https://vnexpress.net/giao-duc",
    # "https://vnexpress.net/giao-duc/tin-tuc",
    # "https://vnexpress.net/giao-duc/tuyen-sinh",
    # "https://vnexpress.net/giao-duc/thao-luan",
    # "https://vnexpress.net/giao-duc/tuyen-sinh"
]

# Danh sách User-Agent để xoay vòng, giảm tỷ lệ bị chặn
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

def get_random_headers(referer="https://vnexpress.net/"):
    """Tạo headers ngẫu nhiên để giả lập trình duyệt thật"""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": referer,
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive"
    }

# --- 2. THIẾT LẬP SESSION & DATABASE ---
session = requests.Session()
retries = Retry(total=5, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries, pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS))

# Database setup (SQLite giúp kiểm tra trùng lặp cực nhanh không tốn RAM)
db_lock = threading.Lock()
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS visited_links (url TEXT PRIMARY KEY)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS seen_hashes (hash TEXT PRIMARY KEY)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS crawl_state (id INTEGER PRIMARY KEY, cat_idx INTEGER, page INTEGER)''')
conn.commit()

# --- 3. ĐỌC TIẾN TRÌNH CŨ TỪ DATABASE ---
cursor.execute("SELECT cat_idx, page FROM crawl_state WHERE id = 1")
row = cursor.fetchone()
current_cat_idx, current_page = row if row else (0, START_PAGE)

def check_and_save_hash(text_hash):
    """Kiểm tra hash có tồn tại không, nếu chưa thì lưu lại (Dùng DB Lock)"""
    with db_lock:
        cursor.execute("SELECT 1 FROM seen_hashes WHERE hash = ?", (text_hash,))
        if cursor.fetchone():
            return True # Đã tồn tại
        cursor.execute("INSERT INTO seen_hashes (hash) VALUES (?)", (text_hash,))
        return False # Chưa tồn tại

def check_and_save_link(url):
    """Kiểm tra link đã cào chưa, lưu lại tiến trình"""
    with db_lock:
        cursor.execute("SELECT 1 FROM visited_links WHERE url = ?", (url,))
        if cursor.fetchone():
            return True
        cursor.execute("INSERT INTO visited_links (url) VALUES (?)", (url,))
        return False

# --- 4. HÀM CÀO DỮ LIỆU ---
def get_article_urls(category_page_url):
    """Lấy toàn bộ link bài viết hợp lệ trên 1 trang chuyên mục"""
    try:
        headers = get_random_headers()
        response = session.get(category_page_url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        links = []
        selectors = 'h1.title-news a, h2.title-news a, h3.title-news a, h4.title-news a, div.thumb-art a'
        
        for a_tag in soup.select(selectors):
            href = a_tag.get('href')
            if href and 'vnexpress.net' in href:
                href = href.split('?')[0].split('#')[0]
                
                # Bỏ qua các định dạng không phải bài viết chuẩn
                blacklisted_keywords = ['/video/', '/podcast/', '/interactive/', '/infographics/']
                if any(x in href for x in blacklisted_keywords):
                    continue
                    
                if href not in links:
                    links.append(href)
                    
        return links
    except Exception as e:
        print(f"   [!] Lỗi mạng tại {category_page_url}: {e}")
        return None 

def crawl_and_clean_article(article_url, f_data):
    """Cào chi tiết 1 bài, lọc text an toàn và ghi file"""
    try:
        headers = get_random_headers(referer=article_url)
        response = session.get(article_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        article_body = soup.select_one('article.fck_detail')
        valid_texts = []
        
        if article_body:
            # 1. Dọn dẹp các thẻ rác gây nhiễu nội dung
            trash_selectors = 'figcaption, .fig_caption, .tplCaption, .box-tin-lien-quan, .list-news, table, .compound-box'
            for tag in article_body.select(trash_selectors):
                tag.decompose()
                
            # 2. Lấy toàn bộ thẻ chứa text ở cấp độ trực tiếp (tránh bỏ sót các format khác nhau)
            paragraphs = article_body.find_all(['p', 'div'], recursive=False)
            
            for p in paragraphs:
                if p.get('style') and 'text-align:right' in p.get('style').replace(" ", ""):
                    continue
                
                text = p.get_text(separator=" ", strip=True)
                text = re.sub(r'>>\s*Xem thêm:.*$', '', text, flags=re.IGNORECASE)
                text = re.sub(r'\s+', ' ', text)
                
                # Chỉ xử lý các câu có ý nghĩa (độ dài > 50 ký tự) để tránh hash những câu như "Cảm ơn", "Chia sẻ"
                if len(text) > 50:
                    text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
                    
                    # Kiểm tra trùng lặp bằng SQLite
                    if not check_and_save_hash(text_hash):
                        valid_texts.append(text)
        
        total_added = 0
        
        # Ghi data vào file txt và commit DB
        if valid_texts:
            with db_lock:
                f_data.write("\n".join(valid_texts) + "\n")
                f_data.flush()
            total_added = len(valid_texts)
            
        # Đánh dấu link đã cào
        check_and_save_link(article_url)
        
        # Commit Database định kỳ (Mỗi bài commit 1 lần là an toàn)
        with db_lock:
            conn.commit()
            
        return total_added

    except Exception:
        # Im lặng bỏ qua nếu gặp lỗi cụ thể của 1 bài viết để không làm gián đoạn tiến trình
        return 0

# --- 5. VÒNG LẶP CHÍNH ---
try:
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f_data:
        for cat_idx in range(current_cat_idx, len(CATEGORY_URLS)):
            base_cat_url = CATEGORY_URLS[cat_idx]
            
            for p in range(current_page, END_PAGE + 1):
                # Lưu trạng thái tiến trình vào SQLite
                with db_lock:
                    cursor.execute("INSERT OR REPLACE INTO crawl_state (id, cat_idx, page) VALUES (1, ?, ?)", (cat_idx, p))
                    conn.commit()
                
                cat_page_url = base_cat_url if p == 1 else f"{base_cat_url}-p{p}"
                print(f"\n--- [MỤC {cat_idx+1}/{len(CATEGORY_URLS)}] QUÉT TRANG: {p} ---")
                
                article_links = get_article_urls(cat_page_url)
                
                if article_links is None:
                    print("   [!] Bỏ qua trang này do lỗi kết nối.")
                    time.sleep(5)
                    continue 
                
                if not article_links:
                    print("   [-] Trang thực sự trống. Chuyển sang chuyên mục tiếp theo.")
                    break 

                links_to_crawl = []
                for count, link in enumerate(article_links, 1):
                    # Kiểm tra link trong DB
                    with db_lock:
                        cursor.execute("SELECT 1 FROM visited_links WHERE url = ?", (link,))
                        is_visited = cursor.fetchone()
                    
                    if is_visited:
                        print(f"   [-] Bỏ qua ({count}/{len(article_links)}): {link} (Đã cào)")
                    else:
                        links_to_crawl.append((count, link))

                if links_to_crawl:
                    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                        futures = {
                            executor.submit(crawl_and_clean_article, link, f_data): (count, link) 
                            for count, link in links_to_crawl
                        }
                        
                        for future in as_completed(futures):
                            count, url = futures[future]
                            added_count = future.result()
                            
                            if added_count > 0:
                                print(f"   [OK] Đã cào ({count}/{len(article_links)}): {url} (+{added_count} đoạn)")
                            else:
                                print(f"   [-] Bỏ qua ({count}/{len(article_links)}): {url} (Rỗng/Trùng lặp)")
                else:
                    print("   [i] Toàn bộ bài trên trang này đã được cào từ trước.")
                        
                # Nghỉ dài hơn một chút để tránh cơ chế Anti-Bot
                time.sleep(random.uniform(1.5, 3.5)) 
            
            # Reset lại page về 1 khi qua chuyên mục mới
            current_page = 1 

    print("\nHOÀN THÀNH!")
    # Tùy chọn: Xóa state khi xong hoàn toàn
    # with db_lock:
    #     cursor.execute("DELETE FROM crawl_state WHERE id = 1")
    #     conn.commit()

except KeyboardInterrupt:
    print("\n[i] Đã dừng bởi người dùng (Ctrl+C). Tiến trình đã được lưu lại tự động.")
except Exception as e:
    print(f"\n[!] LỖI NGHIÊM TRỌNG: {e}")
finally:
    conn.close()