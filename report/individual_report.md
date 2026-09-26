# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Đào Thị Huyền |
| MSSV | Chưa có thông tin trong repository |
| Khóa/Lớp | K4 / K4-L3B |
| Tên nhóm | Optics |
| Vai trò chính | Data Pipeline Implementation, Data Observability & Pipeline Integration |
| Repository | `K4-L3B-DAY10-Optics-DataPipelineDataObservability` |
| Ngày hoàn thành | 2026-09-26 |

> **Ghi chú:** MSSV và URL repository không xuất hiện trong artifact/Git metadata được cung cấp, nên không tự suy đoán để tránh ghi sai thông tin.

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Crossref ingestion | `src/ingestion/crossref.py` — `parse_crossref_payload()`, `fetch_source_records()`, `load_raw_records()` | Crossref JSON / raw snapshot | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Hoàn thành |
| Data cleaning | `src/ingestion/cleaning.py` — `build_clean_dataframe()` | Raw `PaperRecord` | `papers_clean.csv/json`, schema sạch, `age_days`, `text_for_embedding` | Hoàn thành |
| Evaluation set | `src/evaluation/testset.py` — `build_test_set()` | Clean dataframe | `data/eval/test_set.json` gồm 10 câu hỏi | Hoàn thành |
| Data corruption | `src/ingestion/corruption.py` — `corrupt_clean_dataframe()` | Clean dataframe | Corrupted dataset và `corruption_log.json` | Hoàn thành |
| Data quality & freshness | `src/observability/quality.py` — `run_data_quality_checks()`, `evaluate_freshness_sla()` | Dataframe + settings | GX quality reports và freshness signal | Hoàn thành |
| Reporting | `src/observability/reporting.py` | Metrics + quality/freshness results | `phase1_report.md`, `corruption_report.md` | Hoàn thành |
| Pipeline orchestration | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` | Các module ingestion/cleaning/retrieval/evaluation | Baseline → corruption → repair → comparison | Hoàn thành |

Phạm vi trên được đối chiếu với Git history của repository; commit `21b3027` của `huyenlili` chứa các thay đổi chính cho các module trên và các artifact kết quả tương ứng.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Tích hợp các module thành pipeline end-to-end | Ingestion, retrieval, evaluation, observability | `run_phase1.py` và `run_corruption_flow.py` có thể tạo và nối các artifact theo đúng thứ tự |
| Kiểm tra artifact sau corruption/repair | Quality và reporting | Có đủ baseline/corrupted/repaired metrics và quality reports |
| Cập nhật artifact chất lượng sau khi chạy lại | Data observability | `corrupted_quality_report.json` và `repaired_quality_report.json` phản ánh kết quả mới nhất |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Parse và chuẩn hóa dữ liệu Crossref | `src/ingestion/crossref.py` | 24 raw records hợp lệ | `data/raw/crossref_records.json` |
| Làm sạch, loại duplicate và tạo trường phục vụ embedding | `src/ingestion/cleaning.py` | 24 dòng clean, có `age_days` và `text_for_embedding` | `data/clean/papers_clean.json` |
| Sinh benchmark | `src/evaluation/testset.py` | 10 câu hỏi, 4 loại `summary/authors/date/categories` | `data/eval/test_set.json` |
| Xây dựng corruption suite | `src/ingestion/corruption.py` | 6 loại corruption, từ 24 xuống 21 dòng sau corruption | `data/results/corruption_log.json` |
| Thiết lập quality gate | `src/observability/quality.py` | Baseline 4/4 expectations pass; corrupted 2/4 pass; repaired 4/4 pass | `data/quality/*_quality_report.json` |
| Đánh giá RAG ba trạng thái | `src/evaluation/metrics.py`, `src/pipelines/corruption_flow.py` | Retrieval Hit Rate: 1.000 → 0.500 → 1.000; Token F1: 1.000 → 0.779 → 1.000 | `data/results/*_metrics.json` |
| Tạo báo cáo tổng hợp | `src/observability/reporting.py` | Báo cáo baseline và comparison report | `data/reports/phase1_report.md`, `data/reports/corruption_report.md` |

Một output quan trọng của phần việc là bộ artifact ba trạng thái. Baseline có 24 documents và đạt `retrieval_hit_rate=1.0`, `mean_token_f1=1.0`. Sau corruption, retrieval hit rate giảm còn `0.5`, token F1 còn khoảng `0.779`; sau repair, cả hai phục hồi về `1.0`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline cần biến dữ liệu metadata từ Crossref thành dữ liệu có cấu trúc ổn định cho RAG, sau đó phải có khả năng phát hiện dữ liệu bẩn trước khi dữ liệu đi vào serving/index layer. Bài lab đồng thời yêu cầu chứng minh rằng corruption có thể làm giảm chất lượng retrieval/answer mà không nhất thiết làm chương trình crash, và dữ liệu có thể được phục hồi từ nguồn raw đáng tin cậy.

### Cách triển khai

**Ingestion:** `fetch_source_records()` lấy dữ liệu từ Crossref REST API hoặc đọc raw snapshot offline. Khi refresh API, code có retry cho HTTP 429/503 và exponential backoff đơn giản. `parse_crossref_payload()` chuẩn hóa DOI, title, abstract, authors, categories và publication dates thành `PaperRecord`.

**Cleaning:** `build_clean_dataframe()` chuẩn hóa text, loại record thiếu `paper_id/title/summary`, loại duplicate theo `paper_id`, chuẩn hóa ngày, tính `age_days`, tạo `authors_joined`, `categories_joined`, `summary_chars` và `text_for_embedding`.

**Evaluation:** `build_test_set()` tạo 10 câu hỏi từ clean dataset và giữ `ground_truth_doc_ids`. Metrics được tính trên cùng test set cho cả ba trạng thái, gồm retrieval hit rate, token F1, judge accuracy và mean judge score.

**Observability:** `run_data_quality_checks()` dùng Great Expectations 1.x với 4 expectations: row count, title not-null, `paper_id` unique và summary length. Freshness SLA coi record quá 180 ngày là stale và cho phép tối đa 25% stale rows.

**Corruption:** `corrupt_clean_dataframe()` thực hiện 6 kịch bản: drop latest records, blank summary, inject noise, truncate title, stale date và duplicate rows. Mỗi thay đổi được ghi lại trước/sau trong `corruption_log.json`.

**Repair:** `repair_from_raw_snapshot()` không cố sửa từng giá trị đã bị biến đổi. Thay vào đó, pipeline đọc lại `data/raw/crossref_records.json`, chạy lại cleaning, build lại embedding/index và đánh giá lại. Cách này giúp repair có tính idempotent và dựa trên nguồn dữ liệu gốc.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Crossref raw snapshot gồm 24 records; clean dataframe cho các bước downstream |
| Output | Clean/corrupted/repaired datasets, embeddings manifests, evaluation answers, metrics và quality reports |
| Module phụ thuộc | `core.config`, `core.utils`, `ingestion.crossref`, `ingestion.cleaning` |
| Module sử dụng output | `retrieval.index`, `evaluation.metrics`, `observability.quality`, pipeline orchestration |
| Điều kiện lỗi cần xử lý | HTTP 429/503, mất mạng khi có raw snapshot, record thiếu trường bắt buộc, duplicate ID, summary rỗng và stale data |

### Cách xác minh

```bash
python script/run_phase1.py
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** baseline và corruption flow tạo đủ artifacts; repaired state phục hồi quality và metrics.
- **Kết quả thực tế:** baseline 24 dòng/10 câu hỏi; corrupted 21 dòng; repaired 24 dòng. Baseline và repaired quality đều pass 4/4 expectations.
- **Artifact/log:** `data/results/`, `data/quality/`, `data/reports/`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần repair dữ liệu sau khi tiêm lỗi nhưng vẫn phải chứng minh rằng kết quả repair không chỉ là việc “che” lỗi.
- **Các phương án đã cân nhắc:**
  1. Sửa trực tiếp các record bị corruption dựa trên `corruption_log.json`.
  2. Bỏ corrupted dataset và rebuild lại từ raw snapshot bất biến.
- **Phương án đã chọn:** Rebuild clean dataset từ `data/raw/crossref_records.json` bằng `repair_from_raw_snapshot()`.
- **Lý do:** Raw snapshot là nguồn dữ liệu gốc trước corruption. Rebuild giúp tránh mang giá trị đã bị sửa vào repaired dataset và cho phép kiểm tra lại toàn bộ cleaning, quality gate và indexing.
- **Bằng chứng quyết định phù hợp:** repaired dataset trở lại 24 dòng; 4/4 Great Expectations pass; freshness giảm từ 14.3% stale ở corrupted về 4.2%; retrieval hit rate và mean token F1 đều trở lại 1.0.

Một quyết định khác là dùng cùng `data/eval/test_set.json` cho baseline, corrupted và repaired. Điều này giữ nguyên workload đánh giá, nên thay đổi metrics phản ánh thay đổi ở dữ liệu/index thay vì thay đổi câu hỏi benchmark.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi:** Sau khi corruption, quality gate không còn pass dù pipeline vẫn có thể tiếp tục chạy và sinh metrics.
- **Lệnh hoặc bước tái hiện:** `python script/run_corruption_flow.py`.
- **Nguyên nhân gốc:** Corruption tạo duplicate `paper_id` và summary rỗng; đồng thời một phần record mới nhất bị drop. Vì vậy expectation uniqueness và summary length bị fail.
- **Cách xử lý:** Ghi corruption có kiểm soát vào log, chạy quality gate trên corrupted dataframe để phát hiện lỗi, sau đó rebuild dataset từ raw snapshot và chạy lại toàn bộ evaluation/quality/index.
- **Cách xác minh sau khi sửa:** repaired quality report có `success=true`, 4/4 expectations pass; repaired metrics trở lại baseline.
- **Điều học được:** Data pipeline không nên chỉ kiểm tra lỗi ở runtime. Một pipeline RAG cần quality gate trước serving và phải có lineage/raw snapshot đủ tin cậy để phục hồi.

## 7. Hiểu biết về luồng end-to-end

**1. Dữ liệu đi từ Crossref đến vector index như thế nào?**  
Crossref trả về raw JSON. Parser chuyển payload thành `PaperRecord`; cleaning chuẩn hóa dữ liệu, loại record không hợp lệ/duplicate và tạo `text_for_embedding`. Embedding model `sentence-transformers/all-MiniLM-L6-v2` biến nội dung thành vector và ChromaDB lưu các vector cùng metadata. Baseline collection là `papers-baseline`; corrupted và repaired dùng collection riêng.

**2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**  
Mỗi câu hỏi trong `data/eval/test_set.json` có `ground_truth`, `ground_truth_doc_ids` và `question_type`. Retrieval được tính là hit khi một document ID đúng xuất hiện trong các kết quả retrieved. Answer được so với ground truth bằng token F1 và một judge để tính accuracy/score.

**3. Quality checks khác freshness monitoring ở điểm nào?**  
Quality checks kiểm tra tính hợp lệ/cấu trúc của dữ liệu như row count, null title, uniqueness của `paper_id` và độ dài summary. Freshness tập trung vào tuổi dữ liệu qua `age_days`, với threshold 180 ngày và stale ratio tối đa 25%. Một dataset có thể pass structural checks nhưng vẫn cần theo dõi freshness.

**4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**  
Nếu thay test set giữa các trạng thái thì metrics có thể thay đổi do workload đánh giá khác nhau. Giữ nguyên test set giúp so sánh trực tiếp tác động của corruption và mức phục hồi sau repair.

**5. Repair được xem là thành công dựa trên artifact và metric nào?**  
Repair thành công khi dataset trở lại 24 records, quality gate trở lại 4/4 pass, freshness trở lại 4.2% stale và các metrics RAG trở lại baseline: retrieval hit rate 1.0, mean token F1 1.0, judge accuracy 1.0 và mean judge score 5.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.000 | 0.500 | 1.000 | Giảm 0.500 sau corruption và phục hồi hoàn toàn sau repair. |
| `mean_token_f1` | 1.000 | 0.779 | 1.000 | Giảm khoảng 0.221, cho thấy answer quality cũng suy giảm. |
| `judge_accuracy` | 1.000 | 0.800 | 1.000 | 2/10 trường hợp không được judge đánh giá đúng ở corrupted state; repaired trở lại 10/10. |
| `mean_judge_score` | 5 | 4 | 5 | Điểm trung bình giảm 1 điểm và phục hồi về 5. |
| Quality checks | 4/4 PASS | 2/4 PASS | 4/4 PASS | Corruption được quality gate phát hiện, repair loại bỏ các violation. |
| Freshness status | FRESH, 4.2% stale | FRESH, 14.3% stale | FRESH, 4.2% stale | Corrupted state vẫn dưới ngưỡng 25%, nhưng freshness xấu hơn baseline. |

### Kết luận từ số liệu

1. **Drop/biến đổi dữ liệu → quality signal suy giảm → retrieval/answer metric suy giảm.** Corrupted dataset giảm từ 24 xuống 21 dòng và có duplicate `paper_id` cùng summary rỗng. Great Expectations giảm từ 4/4 xuống 2/4 pass; đồng thời retrieval hit rate giảm từ 1.000 xuống 0.500 và mean token F1 giảm từ 1.000 xuống khoảng 0.779.

2. **Repair từ raw snapshot → quality/freshness phục hồi → agent metric phục hồi.** Pipeline rebuild từ raw records đưa dataset về 24 dòng, quality gate về 4/4 pass và stale ratio từ 14.3% về 4.2%. Sau đó retrieval hit rate, token F1, judge accuracy và mean judge score đều trở lại mức baseline.

**Corruption ảnh hưởng rõ nhất:** Xét trên kết quả cuối cùng, tác động tổng hợp của corruption suite làm retrieval hit rate giảm 50 điểm phần trăm và token F1 giảm khoảng 22.1 điểm phần trăm. Log cho thấy corruption không chỉ có một loại: 5 record mới nhất bị drop, 2 summary bị blank, 2 summary bị inject noise, 2 title bị truncate, 2 ngày bị làm stale và 2 duplicate rows được thêm.

**Kết quả khác với kỳ vọng ban đầu:** Freshness SLA vẫn báo `FRESH` ở corrupted state vì stale ratio 14.3% vẫn thấp hơn ngưỡng 25%. Tuy nhiên quality gate vẫn `FAIL` do uniqueness và summary-length expectations. Điều này cho thấy freshness monitoring và structural quality checks phát hiện hai nhóm vấn đề khác nhau; không nên dùng freshness làm đại diện cho toàn bộ data quality.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Data pipeline:** Raw snapshot và data contract là nền tảng để pipeline có thể tái hiện và repair an toàn. Cleaning cần tạo schema ổn định trước khi indexing.
2. **Data quality/observability:** Quality gate phải kiểm tra nhiều chiều. Row count/uniqueness/validity và freshness bổ sung cho nhau; một tín hiệu pass không đồng nghĩa toàn bộ dữ liệu tốt.
3. **Ảnh hưởng của data đến RAG:** Dữ liệu bẩn có thể không làm chương trình crash nhưng vẫn làm retrieval và answer quality giảm đáng kể. Vì vậy cần quality gate trước serving/indexing.

### Nếu có thêm thời gian

Ưu tiên hoàn thiện `build_freshness_report()` trong `src/observability/quality.py`. Hiện hàm này vẫn là TODO và chưa tạo `freshness_report.json` riêng. Có thể bổ sung `latest_published`, `oldest_published`, `stale_rows`, `total_rows`, `stale_ratio` và `is_fresh`, sau đó thêm test tự động để xác minh threshold 180 ngày và stale ratio 25%.

Một cải thiện khác là loại bỏ hard-coded absolute Windows paths trong các report artifact. `data/reports/phase1_report.md` hiện ghi đường dẫn local `C:\Users\hyo\...`, trong khi pipeline code đã dùng `Path` tương đối/cấu hình hóa. Chuyển report sang đường dẫn tương đối sẽ tăng khả năng tái hiện trên máy khác.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh phần việc và mức hiểu dựa trên Git history và artifact của repository.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đào Thị Huyền  
**Ngày xác nhận:** 2026-09-26
