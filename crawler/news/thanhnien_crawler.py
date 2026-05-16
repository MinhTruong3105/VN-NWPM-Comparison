import requests
from bs4 import BeautifulSoup
import time
import random
import os
import re
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- THƯ VIỆN MỚI DÀNH CHO TRANG ĐỘNG ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# --- CẤU HÌNH ---
BASE_DIR = os.path.join("data", "raw", "thanhnien")
os.makedirs(BASE_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(BASE_DIR, "data_thanhnien_finance.txt")
VISITED_FILE = os.path.join(BASE_DIR, "visited_thanhnien_finance.txt")

MAX_WORKERS = 5 
MAX_CLICKS = 30  # Số lần bấm nút "Xem thêm" tối đa (Giới hạn để không bị treo máy)

CATEGORY_URLS = [
    "https://thanhnien.vn/kinh-te/chung-khoan.htm",
    # "https://thanhnien.vn/kinh-te/doanh-nghiep.htm",
    # "https://thanhnien.vn/kinh-te/chinh-sach-phat-trien.htm",
    # "https://thanhnien.vn/kinh-te/ngan-hang.htm"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# --- THIẾT LẬP SESSION & THREAD LOCKS ---
session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries, pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS))

write_lock = threading.Lock() 

# --- ĐỌC TIẾN TRÌNH CŨ ---
visited_links = set()
if os.path.exists(VISITED_FILE):
    with open(VISITED_FILE, "r", encoding="utf-8") as f:
        visited_links.update(line.strip() for line in f)

global_seen_hashes = set()
if os.path.exists(OUTPUT_FILE):
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line_hash = hashlib.md5(line.strip().encode('utf-8')).hexdigest()
            global_seen_hashes.add(line_hash)

def get_all_links_with_selenium(category_url):
    """Giả lập Chrome tự động cuộn trang và bấm nút 'Xem thêm' để vét link"""
    print(f"   [Selenium] Mở trình duyệt ẩn để quét trang: {category_url}")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") # Chạy ngầm
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    
    # --- CÁC TÙY CHỌN TỐI ƯU TRÁNH TIMEOUT VÀ RÒ RỈ BỘ NHỚ ---
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # Tắt tải hình ảnh để web nhẹ hơn, load nhanh hơn
    chrome_options.add_argument("--blink-settings=imagesEnabled=false") 
    
    links = []
    driver = None
    
    try:
        # Tự động tải ChromeDriver
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        
        # Thiết lập thời gian chờ tối đa (120 giây)
        driver.set_page_load_timeout(120)
        driver.implicitly_wait(5)
        
        try:
            driver.get(category_url)
        except TimeoutException:
            print("   [!] Lỗi Timeout khi load trang ban đầu. Vẫn tiếp tục xử lý phần HTML đã tải...")
        
        click_count = 0
        while click_count < MAX_CLICKS:
            try:
                # Tìm nút Xem thêm
                xpath_btn = "//a[contains(text(), 'Xem thêm') or contains(text(), 'XEM THÊM')] | //button[contains(text(), 'Xem thêm')]"
                view_more_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath_btn))
                )
                
                # Cuộn xuống nút và click bằng Javascript
                driver.execute_script("arguments[0].scrollIntoView();", view_more_btn)
                time.sleep(1) 
                driver.execute_script("arguments[0].click();", view_more_btn)
                
                click_count += 1
                print(f"   [Selenium] Bấm 'Xem thêm' lần {click_count}/{MAX_CLICKS}...")
                time.sleep(2) # Chờ bài báo mới tải về
                
            except Exception:
                print("   [Selenium] Tới đáy trang hoặc không còn nút 'Xem thêm'.")
                break
                
        # Hút toàn bộ HTML sau khi đã "nở" to nhất
        html_content = driver.page_source
        
        # Quăng lại cho BeautifulSoup bóc tách link
        soup = BeautifulSoup(html_content, 'html.parser')
        selectors = 'h2 a, h3 a, h4 a, .box-title-text, .box-category-link-title'
        
        for a_tag in soup.select(selectors):
            href = a_tag.get('href')
            if href:
                href = urljoin("https://thanhnien.vn", href)
                if 'thanhnien.vn' in href and href.endswith('.htm'):
                    href = href.split('?')[0].split('#')[0]
                    if any(x in href for x in ['/video/', '/podcast/', '/infographic/', '/interactive/']):
                        continue
                    if href not in links:
                        links.append(href)
                        
    except WebDriverException as e:
        print(f"   [!] Lỗi WebDriver (Trình duyệt có thể đã bị treo/đóng): {e}")
    except Exception as e:
        print(f"   [!] Lỗi không xác định trong quá trình vét link: {e}")
    finally:
        # BẮT BUỘC: Luôn đóng driver dù code chạy thành công hay báo lỗi
        if driver:
            driver.quit()
            print("   [Selenium] Đã đóng trình duyệt giải phóng RAM.")
            
    print(f"   [Selenium] Tổng kết: Gom được {len(links)} link bài viết hợp lệ.")
    return links

def crawl_and_clean_article(article_url, f_data, f_visited):
    try:
        response = session.get(article_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        article_body = soup.select_one('div.detail-cmain, div.detail-content')
        valid_texts = []
        
        if article_body:
            for tag in article_body.select('figcaption, .image-caption, .quote, .relate-container, table, .video-wrap'):
                tag.decompose()
                
            paragraphs = article_body.select('p')
            
            for p in paragraphs:
                if p.get('style') and 'text-align:right' in p.get('style').replace(" ", ""):
                    continue
                
                text = p.get_text(separator=" ", strip=True)
                text = re.sub(r'>>\s*Xem thêm:.*$', '', text, flags=re.IGNORECASE)
                text = re.sub(r'Mời các bạn tham gia.*$', '', text, flags=re.IGNORECASE)
                text = re.sub(r'\s+', ' ', text)
                
                if len(text) > 40:
                    text_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
                    
                    with write_lock:
                        if text_hash not in global_seen_hashes:
                            global_seen_hashes.add(text_hash)
                            valid_texts.append(text)
        
        total_added = 0
        
        with write_lock:
            if article_url not in visited_links:
                f_visited.write(article_url + "\n")
                f_visited.flush()
                visited_links.add(article_url)
            
            if valid_texts:
                f_data.write("\n".join(valid_texts) + "\n")
                f_data.flush()
                total_added = len(valid_texts)
                
        return total_added
    except Exception as e:
        return 0

# --- VÒNG LẶP CHÍNH ---
try:
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f_data, \
         open(VISITED_FILE, "a", encoding="utf-8") as f_visited:
        
        for index, category_url in enumerate(CATEGORY_URLS, 1):
            print(f"\n--- [MỤC {index}/{len(CATEGORY_URLS)}] BẮT ĐẦU QUÉT: {category_url} ---")
            
            # Bước 1: Dùng Selenium để lấy sạch link
            article_links = get_all_links_with_selenium(category_url)
            
            if not article_links:
                print("   [-] Không tìm thấy link nào hoặc bị lỗi mạng. Chuyển mục tiếp theo.")
                time.sleep(3)
                continue

            # Phân loại link
            links_to_crawl = []
            for count, link in enumerate(article_links, 1):
                if link in visited_links:
                    print(f"   [-] Bỏ qua ({count}/{len(article_links)}): {link} (Đã cào)")
                else:
                    links_to_crawl.append((count, link))

            # Bước 2: Dùng ThreadPool để tải nội dung đa luồng siêu tốc
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
                            print(f"   [-] Bỏ qua ({count}/{len(article_links)}): {url} (Video/Podcast/Trùng Text)")
            else:
                print("   [i] Toàn bộ bài trong chuyên mục này đã được cào từ trước.")
                
            time.sleep(random.uniform(2, 4)) # Nghỉ một lát trước khi sang chuyên mục tiếp theo

    print(f"\nHOÀN THÀNH!")

except KeyboardInterrupt:
    print("\n[i] Đã dừng bởi người dùng (Ctrl+C). Tiến trình đã được lưu lại.")
except Exception as e:
    print(f"\n[!] LỖI NGHIÊM TRỌNG Ở VÒNG LẶP CHÍNH: {e}")