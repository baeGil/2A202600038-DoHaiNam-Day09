# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Đỗ Hải Nam
**Vai trò trong nhóm:** Supervisor Owner / Worker Owner 
**Ngày nộp:** 2026-04-14  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Trong dự án này, tôi chịu trách nhiệm chính về kiến trúc hệ thống và luồng điều phối (Orchestration context). Tôi đã trực tiếp thiết kế và triển khai file `graph.py` để xây dựng cấu trúc Supervisor-Worker, đảm bảo dữ liệu được truyền đi thông suốt qua `AgentState`. 

Bên cạnh đó, tôi cũng trực tiếp triển khai logic lõi cho ba Worker quan trọng:
- `workers/retrieval.py`: Tích hợp Jina Embedding và Jina Reranker để tối ưu hóa việc tìm kiếm thông tin.
- `workers/policy_tool.py`: Chuyển đổi từ rule-based sang LLM-based (sử dụng model Groq Kimi) để phân tích các ngoại lệ chính sách một cách thông minh hơn.
- `workers/synthesis.py`: Thiết lập grounded prompt để tổng hợp câu trả lời cuối cùng, đảm bảo có trích dẫn nguồn (citation) đầy đủ.

Công việc của tôi đóng vai trò là "xương sống" của hệ thống, kết nối các module của các thành viên khác (như MCP server) vào luồng xử lý chung của Pipeline.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Tôi đã quyết định nâng cấp toàn bộ hệ thống lên **Advanced RAG** bằng cách áp dụng **Semantic Chunking (Jina Segmenter API)**, **Hybrid Search (Vector + BM25)** và **Jina Reranker v3**.

**Lý do:** Trong các thử nghiệm ban đầu, độ tin cậy (confidence) của hệ thống chỉ ở mức 0.1 và tìm kiếm thiếu chính xác do việc index nguyên cả file thay vì chia nhỏ đoạn. Thêm vào đó, chỉ dùng Dense Search (Vector) dễ bỏ lỡ các từ khóa chuyên ngành chính xác như "ERR-403".

Tôi đã chọn cách tiếp cận toàn diện:
1. Chia nhỏ văn bản theo độ gối đầu dựa trên ngữ nghĩa của con người (bằng mô hình Jina Segmenter và chuẩn CL100K_Base).
2. Khi retrieve, kết hợp BM25 (theo từ khóa chính xác) lẫn ChromaDB (ngữ nghĩa), lấy top 20 của mỗi bên phối hợp lại.
3. Chạy qua thuật toán Jina Reranker v3 để chắt lọc top 5 ứng viên tốt nhất.

**Trade-off đã chấp nhận:** Việc kết hợp nhiều hệ thống (Segmenter API, BM25, Reranker v3) làm tăng độ trễ và phức tạp trong khâu code (phải dùng `rank_bm25` module để tokenize cục bộ). Đổi lại, độ tin cậy được nâng từ mức dưới trung bình lên mức xuất sắc (trung bình >0.5-0.7).

**Bằng chứng từ trace/code:**
```python
def retrieve_hybrid(query: str, top_k: int = 5) -> list:
    dense_chunks = retrieve_dense(query, top_k=20)
    sparse_chunks = retrieve_sparse(query, top_k=20)   # BM25Okapi
    # Combines and Rerank
    reranked = rerank_with_jina(query, candidate_chunks)
    return reranked[:top_k]
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Trace ghi nhận `retrieved_chunks` luôn lỗi Dimension (768 vs 1024) và hệ thống Groq LLM bị treo (timeout 48 giây).

**Symptom:** Khi chạy pipeline lần đầu, ChromaDB liên tục chửi "Embedding dimension 768 does not match 1024". Tốc độ trả lời của LLM `policy_tool_worker` kéo dài tới gần 1 phút.

**Root cause:** 
1. Lỗi data index: Dữ liệu cũ trong `chroma_db` được index bằng mô hình `all-MiniLM-L6-v2` (768D), trong khi code mới chạy `jina-embeddings-v5-text-small` (1024D). Không tương thích hệ vector.
2. Lỗi timeout: LLM Kimi phải đọc quá nhiều raw text (chưa chunk) cộng với việc không giới hạn max_tokens ở module Groq.

**Cách sửa:** Tôi đã viết script `reindex.py` để xóa sạch toàn collection cũ, bổ sung Jina Segmenter API và embed lại với 1024D. Đối với `policy_tool.py`, tôi khai báo tham số `max_tokens=300` để ép Groq phản hồi ngay lập tức, đưa latency trung bình hệ thống từ > 40,000ms xuống dưới 4,000ms.

**Bằng chứng trước/sau:** 
- Trước khi sửa: Lỗi crash ChromaDB, thời gian là 48836ms, confidence: 0.1.
- Sau khi sửa: Lỗi biến mất, thời gian phản hồi: 3763ms, confidence: 0.54-0.75.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**  
Tôi đã thiết kế được một cấu trúc AgentState rất chặt chẽ, cho phép trace toàn bộ lịch sử (history) và nhật ký IO của từng worker (`worker_io_logs`). Điều này giúp cho việc debug và điền tài liệu đánh giá sau đó trở nên cực kỳ nhanh chóng.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**  
Logic điều phối của Supervisor trong node `supervisor_node` hiện vẫn đang phụ thuộc khá nhiều vào keyword. Điều này có thể dẫn đến sai sót với những câu hỏi mang tính ẩn dụ hoặc cấu trúc câu phức tạp.

**Nhóm phụ thuộc vào tôi ở đâu?**  
Toàn bộ dự án phụ thuộc vào phần điều phối Graph của tôi. Nếu `graph.py` gặp lỗi logic trong việc route, các worker khác dù tốt đến đâu cũng sẽ không nhận được input đúng.

**Phần tôi phụ thuộc vào thành viên khác:**  
Tôi phụ thuộc vào MCP Owner để đảm bảo các mock data trong `mcp_server.py` (như ticket IT-9847) khớp với các kịch bản test trong `test_questions.json`.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ cải tiến `supervisor_node` bằng cách sử dụng một mô hình LLM mạnh mẽ hơn thay vì keyword. Tôi sẽ thử điều này vì trace của câu `q15` (câu hỏi multi-hop khó nhất) cho thấy Supervisor đôi khi chỉ chọn `policy_tool_worker` mà bỏ qua `retrieval_worker` nếu câu hỏi có quá nhiều từ khóa về rule/policy cùng lúc.

---
