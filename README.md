#  Hệ Thống Dự Đoán Từ Tiếp Theo Tiếng Việt (Vietnamese Next Word Prediction)

Dự án này là Đồ án Cuối kỳ môn **Khai thác dữ liệu và Khai phá tri thức**, Trường Đại học Tôn Đức Thắng (Năm 2026). 
Mục tiêu của dự án là xây dựng một pipeline hoàn chỉnh từ khâu thu thập, tiền xử lý dữ liệu văn bản tiếng Việt quy mô lớn, cho đến việc huấn luyện và đánh giá các kiến trúc học sâu khác nhau cho bài toán Dự đoán từ tiếp theo (Next Word Prediction - NWP).

**Tác giả thực hiện:**
* Lê Tiến Bảo (52300093)
* Trương Quốc Minh (52300127)

---

##  Tài nguyên Dự án (Kaggle)

Toàn bộ quá trình huấn luyện và đánh giá được thực hiện trên môi trường Kaggle. Bạn có thể truy cập tập dữ liệu và trọng số mô hình đã được huấn luyện tại các đường dẫn sau:

* **Tập dữ liệu (Dataset):** [Vietnamese NWP Dataset](https://www.kaggle.com/datasets/truongminh3105/nwp-dataset)
* **Trọng số Mô hình (Model Weights):** [My NLP Models](https://www.kaggle.com/datasets/truongminh3105/my-nlp-models)

---

##  Cấu trúc Thư mục

Dự án được tổ chức thành các module rõ ràng nhằm phục vụ cho từng giai đoạn của Data Pipeline:

```text
 repository-name
 ┣  code                               # Chứa các Jupyter Notebook để Huấn luyện & Chạy thử
 ┃ ┣  app-nwp-demo.ipynb               # Ứng dụng Demo so sánh trực tiếp 3 mô hình
 ┃ ┣  gru-nwp.ipynb                    # Notebook huấn luyện mô hình GRU
 ┃ ┣  qwen-nwp.ipynb                   # Notebook finetune/infer mô hình Qwen2-1.5B
 ┃ ┗  tcn-nwp.ipynb                    # Notebook huấn luyện mô hình TCN
 ┣  crawler                            # Các script thu thập dữ liệu thô
 ┃ ┣  forum                            # Thu thập dữ liệu từ diễn đàn
 ┃ ┃ ┗  crawl_voz.py
 ┃ ┗  news                             # Thu thập dữ liệu từ các trang báo điện tử
 ┃   ┣  dantri_crawler.py
 ┃   ┣  thanhnien_crawler.py
 ┃   ┗  vnexp_crawler.py
 ┗  standardize_data/pre_process       # Tiền xử lý, làm sạch và chuẩn hóa dữ liệu
   ┣  forum_sp                         # Xử lý đặc thù cho dữ liệu diễn đàn (VOZ)
   ┃ ┣  base_cleaning_forum.py
   ┃ ┣  clean_text.py
   ┃ ┣  final_clean.py
   ┃ ┣  teencode_process.py            # Chuẩn hóa teencode, từ lóng
   ┃ ┣  unigram_extract.py
   ┃ ┗  voz_data_cleaner.py
   ┗  new_sp                           # Xử lý đặc thù cho dữ liệu báo chí
     ┣  base_cleaning_news.py
     ┣  rich_jsonl_maker.py            # Đóng gói dữ liệu thành định dạng JSONL
     ┗  vn_word_segmenter.py           # Phân đoạn từ tiếng
