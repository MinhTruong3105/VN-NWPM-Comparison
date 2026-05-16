
from bs4 import BeautifulSoup
import time
import random
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from urllib.parse import urljoin

# IMPORT THƯ VIỆN CHỐNG CHẶN
from curl_cffi import requests

# --- CẤU HÌNH ---
BASE_DIR = os.path.join("data", "raw", "dantri")
os.makedirs(BASE_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(BASE_DIR, "data_dantri_tech.txt")
VISITED_FILE = os.path.join(BASE_DIR, "visited_dantri_tech.txt")
STATE_FILE = os.path.join(BASE_DIR, "state_dantri.txt")

START_PAGE = 1
END_PAGE = 30
MAX_WORKERS = 3  

CATEGORY_URLS = [
    # "https://dantri.com.vn/kinh-doanh.htm",
    # "https://dantri.com.vn/kinh-doanh/tai-chinh.htm",
    # "https://dantri.com.vn/kinh-doanh/doanh-nghiep.htm",

    # "https://dantri.com.vn/giao-duc.htm",
    # "https://dantri.com.vn/giao-duc/tuyen-sinh.htm",
    # "https://dantri.com.vn/giao-duc/du-hoc.htm",
    # "https://dantri.com.vn/giao-duc/giao-duc-nghe-nghiep.htm",

    # "https://dantri.com.vn/giai-tri/sach-hay.htm",
    # "https://dantri.com.vn/giai-tri/am-nhac.htm",
    # "https://dantri.com.vn/giai-tri/dien-anh.htm",
    # "https://dantri.com.vn/giai-tri/my-thuat-san-khau.htm",
    # "https://dantri.com.vn/the-thao/bong-da.htm",
    # "https://dantri.com.vn/the-thao/tennis.htm",
    # "https://dantri.com.vn/the-thao/vo-thuat-cac-mon-khac.htm",

    "https://dantri.com.vn/cong-nghe.htm",
    "https://dantri.com.vn/cong-nghe/ai-internet.htm",
    "https://dantri.com.vn/cong-nghe/an-ninh-mang.htm",
    "https://dantri.com.vn/cong-nghe/san-pham-cong-dong.htm"
]

# --- THIẾT LẬP SESSION CURL_CFFI ---
# Giả lập hoàn toàn vân tay mạng của Google Chrome phiên bản 110
session = requests.Session(impersonate="chrome110")

# Header cơ bản (User-Agent đã được tự động lo bởi impersonate)
session.headers.update({
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://dantri.com.vn/"
})

write_lock = threading.Lock() 

# --- ĐỌC TIẾN TRÌNH CŨ ---
visited_links = set()
if os.path.exists(VISITED_FILE):
    with open(VISITED_FILE, "r", encoding="utf-8") as f:
        visited_links.update(line.strip() for line in f if line.strip())

current_cat_idx = 0
current_page = START_PAGE
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state_data = f.read().strip().split(",")
        if len(state_data) == 2:
            current_cat_idx, current_page = map(int, state_data)

# --- HÀM HỖ TRỢ ---
def fetch_with_retry(url, max_retries=3):
    """Hàm tải trang có tích hợp cơ chế thử lại khi gặp lỗi mạng"""
    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=20)
            if response.status_code == 200:
                # Kiểm tra xem có bị dính tường lửa Cloudflare/Captcha không
                if "Just a moment..." in response.text or "Checking your browser" in response.text:
                    print(f"   [!] Bị Cloudflare chặn tại: {url}. Đang chờ để thử lại...")
                    time.sleep(random.uniform(5.0, 10.0))
                    continue
                return response
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"   [!] Lỗi mạng ({url}): {e}")
            time.sleep(random.uniform(2.0, 5.0))
    return None

# --- HÀM CÀO DỮ LIỆU ---
def get_article_urls(category_page_url):
    """Lấy toàn bộ link bài viết hợp lệ trên 1 trang chuyên mục"""
    response = fetch_with_retry(category_page_url)
    if not response:
        return None

    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        links = []
        selectors = 'h3.article-title a, h2.article-title a, div.article-thumb a'
        
        for a_tag in soup.select(selectors):
            href = a_tag.get('href')
            if href:
                full_link = urljoin("https://dantri.com.vn", href)
                full_link = full_link.split('?')[0].split('#')[0]
                
                blacklisted_keywords = ['/video/', '/emagazine/', '/infographic/', '/podcast/']
                if any(x in full_link for x in blacklisted_keywords):
                    continue
                    
                if full_link not in links and "dantri.com.vn" in full_link:
                    links.append(full_link)
                    
        return links
    except Exception as e:
        print(f"   [!] Lỗi phân tích HTML tại {category_page_url}: {e}")
        return None 

def crawl_and_clean_article(article_url, f_data, f_visited):
    """Cào chi tiết bài, gom Tiêu đề + Sapo + Nội dung thành text phẳng"""
    # Ngủ ngẫu nhiên để tránh tạo luồng request quá dồn dập
    time.sleep(random.uniform(1.0, 3.0))
    
    response = fetch_with_retry(article_url)
    if not response:
        return 0

    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        valid_texts = []
        seen_texts_local = set() 
        
        def add_text(raw_text):
            text = re.sub(r'>>\s*Xem thêm:.*$', '', raw_text, flags=re.IGNORECASE)
            text = re.sub(r'\s+', ' ', text).strip()
            if len(text) > 40 and text not in seen_texts_local:
                seen_texts_local.add(text)
                valid_texts.append(text)

        # 1. Bóc tách Tiêu đề
        title = soup.select_one('h1[data-slot="title"], h1.title-page')
        if title: add_text(title.get_text(separator=" "))

        # 2. Bóc tách Sapo (Tóm tắt)
        sapo = soup.select_one('h2[data-slot="sapo"], h2.singular-sapo')
        if sapo: add_text(sapo.get_text(separator=" "))

        # 3. Bóc tách Nội dung (Bổ sung thêm div[data-slot="content"])
        article_body = soup.select_one('div[data-slot="content"], div.singular-content, div.e-magazine__body, div.dt-news__content')
        if article_body:
            # Xóa rác: Ảnh, chú thích, video, bảng, quảng cáo (ads-in-content)
            for tag in article_body.select('figure, figcaption, .video, table, .related-news, .dantri-widget, .ad-container, [data-slot="ads-in-content"]'):
                tag.decompose()
                
            for p in article_body.select('p'):
                style = p.get('style', '')
                classes = p.get('class', [])
                # Bỏ qua dòng tác giả hoặc căn phải
                if 'text-align:right' in style.replace(" ", "") or 'author' in str(classes):
                    continue
                add_text(p.get_text(separator=" "))
        
        # Ghi dữ liệu
        with write_lock:
            if article_url not in visited_links:
                f_visited.write(article_url + "\n")
                f_visited.flush()
                visited_links.add(article_url)
            
            if valid_texts:
                f_data.write("\n".join(valid_texts) + "\n")
                f_data.flush()
                return len(valid_texts)
                
        return 0

    except Exception as e:
        return 0

# --- VÒNG LẶP CHÍNH ---
if __name__ == "__main__":
    try:
        with open(OUTPUT_FILE, "a", encoding="utf-8") as f_data, \
             open(VISITED_FILE, "a", encoding="utf-8") as f_visited:
            
            for cat_idx in range(current_cat_idx, len(CATEGORY_URLS)):
                base_cat_url = CATEGORY_URLS[cat_idx].strip()
                if not base_cat_url.endswith(".htm"):
                    base_cat_url += ".htm"
                
                for p in range(current_page, END_PAGE + 1):
                    with open(STATE_FILE, "w", encoding="utf-8") as f_state:
                        f_state.write(f"{cat_idx},{p}")
                    
                    cat_page_url = base_cat_url if p == 1 else base_cat_url.replace(".htm", f"/trang-{p}.htm")
                    print(f"\n--- [MỤC {cat_idx+1}/{len(CATEGORY_URLS)}] QUÉT TRANG: {p} ---")
                    
                    article_links = get_article_urls(cat_page_url)
                    
                    if article_links is None:
                        print("   [!] Lỗi kết nối hoặc bị chặn. Thử lại ở trang sau.")
                        continue 
                    if not article_links:
                        print("   [-] Trang thực sự trống. Chuyển chuyên mục.")
                        break 

                    links_to_crawl = [(count, link) for count, link in enumerate(article_links, 1) if link not in visited_links]

                    for count, link in enumerate(article_links, 1):
                        if link in visited_links:
                             print(f"   [-] Bỏ qua ({count}/{len(article_links)}): Đã cào từ trước")

                    if links_to_crawl:
                        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                            futures = {
                                executor.submit(crawl_and_clean_article, link, f_data, f_visited): (count, link) 
                                for count, link in links_to_crawl
                            }
                            
                            for future in as_completed(futures):
                                count, url = futures[future]
                                added_count = future.result()
                                
                                if added_count > 0:
                                    print(f"   [OK] Đã cào ({count}/{len(article_links)}): {url} (+{added_count} đoạn)")
                                else:
                                    print(f"   [-] Lỗi/Bỏ qua ({count}/{len(article_links)}): {url} (Rỗng/Đã tồn tại)")
                    else:
                        print("   [i] Toàn bộ bài trên trang này đã được cào từ trước.")
                            
                    time.sleep(random.uniform(2.0, 4.0))
                
                current_page = 1 

        print(f"\nHOÀN THÀNH!")
        if os.path.exists(STATE_FILE): os.remove(STATE_FILE)

    except KeyboardInterrupt:
        print("\n[i] Đã dừng bởi người dùng (Ctrl+C). Tiến trình đã được lưu lại.")
    except Exception as e:
        print(f"\n[!] LỖI NGHIÊM TRỌNG: {e}")