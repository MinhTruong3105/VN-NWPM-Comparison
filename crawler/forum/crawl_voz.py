import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import time
import random
import os

# --- CẤU HÌNH NGUỒN ---
CHROME_VERSION = 146  
FORUM_ID = "bat-dong-san.79"      # Đã chuyển sang box Thể dục thể thao
PREFIX_ID = 12                        # Nhãn tương ứng với link của bạn
OUTPUT_FILE = "data_voz_bat_dong_san_thao_luan.txt" # Đổi tên file cho box mới

# Bắt đầu cào từ trang 1 (bạn có thể tự chỉnh lại nếu cần cào tiếp)
START_PAGE = 1
END_PAGE = 100

# --- TỐI ƯU HÓA SPEED CỰC HẠN ---
options = uc.ChromeOptions()
# Cấm tải hình ảnh, icon, CSS nặng để dồn toàn bộ băng thông cho Text
options.add_argument('--blink-settings=imagesEnabled=false') 

driver = uc.Chrome(options=options, version_main=CHROME_VERSION)

def get_thread_urls(page_number):
    """Lấy danh sách link bài viết"""
    if page_number == 1:
        url = f"https://voz.vn/f/{FORUM_ID}/?prefix_id={PREFIX_ID}"
    else:
        url = f"https://voz.vn/f/{FORUM_ID}/page-{page_number}?prefix_id={PREFIX_ID}"
    
    try:
        print(f"\n--- ĐANG QUÉT TRANG DANH SÁCH: {page_number} ---")
        driver.get(url)
        
        # [SPEED HACK MỚI] Danh sách bài: Giảm xuống cực thấp (0.8, 1.3) giây
        time.sleep(random.uniform(0.8, 1.3)) 
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        thread_items = soup.select('.structItem--thread:not(.structItem--sticky)')
        
        links = []
        for item in thread_items:
            link_el = item.select_one('.structItem-title a[href*="/t/"]')
            if link_el:
                href = link_el.get('href')
                full_url = "https://voz.vn" + href.split('unread')[0].rstrip('/')
                if full_url not in links:
                    links.append(full_url)
        return links
    except Exception as e:
        print(f"   [!] Lỗi quét link: {e}")
        return []

def crawl_and_write_comments(post_url, file_handle):
    """Cào nội dung và lật trang"""
    current_page = 1
    total_added = 0
    
    while True:
        target_url = f"{post_url}/page-{current_page}" if current_page > 1 else post_url
        try:
            driver.get(target_url)
            
            # [SPEED HACK MỚI] Load comment: Giảm xuống (0.3, 0.6) giây
            time.sleep(random.uniform(0.3, 0.6)) 
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            comment_blocks = soup.select('.bbWrapper')
            
            if not comment_blocks:
                break
                
            for block in comment_blocks:
                for quote in block.select('blockquote'):
                    quote.decompose()
                
                content = block.get_text(separator=" ", strip=True)
                if len(content) > 25: 
                    file_handle.write(content + "\n")
                    total_added += 1

            file_handle.flush()
            os.fsync(file_handle.fileno())

            next_button = soup.select_one('.pageNav-jump--next')
            if not next_button or current_page >= 50: 
                break
            current_page += 1
        except Exception:
            break
            
    return total_added

# --- CHƯƠNG TRÌNH CHÍNH ---
try:
    print("🚀 HỆ THỐNG: Đang khởi động chế độ Speed Cực Hạn...")
    driver.get(f"https://voz.vn/f/{FORUM_ID}/")
    
    input("=> HÃY CLICK XÁC NHẬN CLOUDFLARE TRÊN TRÌNH DUYỆT (nếu có), SAU ĐÓ NHẤN ENTER TẠI ĐÂY...")

    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        for p in range(START_PAGE, END_PAGE + 1):
            thread_links = get_thread_urls(p)
            
            if not thread_links:
                continue
                
            print(f"📍 Tìm thấy {len(thread_links)} bài. Bắt đầu ép tốc độ...")
            
            for index, link in enumerate(thread_links):
                count = crawl_and_write_comments(link, f)
                print(f"   [OK] {index+1}/{len(thread_links)}: Ghi {count} câu.")
                
                # [SPEED HACK MỚI] Nghỉ giữa các bài: Gần như ngay lập tức (0.2, 0.4) giây
                time.sleep(random.uniform(0.2, 0.4))

    print(f"\n✨ HOÀN THÀNH! Dữ liệu đã lưu tại {OUTPUT_FILE}")

except Exception as e:
    print(f"❌ LỖI HỆ THỐNG: {e}")
finally:
    driver.quit()