# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** DoHaiNam  
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

**Quyết định:** Tôi đã quyết định sử dụng **Jina Reranker v2** trong `retrieval_worker` thay vì chỉ sử dụng kết quả tìm kiếm thô từ ChromaDB.

**Lý do:** Trong các thử nghiệm ban đầu (từ Day 08), tôi nhận thấy tìm kiếm ngữ nghĩa đôi khi trả về các đoạn văn bản có độ tương đồng cao nhưng không chứa thông tin trả lời trực tiếp cho câu hỏi (vd: câu hỏi về SLA P1 nhưng trả về FAQ chung). Việc chỉ lấy Top 3 từ vector database là không đủ an toàn. 

Tôi đã chọn cách tiếp cận: lấy Top 10 chunks từ ChromaDB, sau đó gởi toàn bộ danh sách này kèm query sang Jina Reranker API. Reranker sử dụng mô hình cross-encoder mạnh mẽ hơn để chấm điểm lại mức độ phù hợp thực sự. Kết quả cuối cùng chỉ lấy Top 3 đã rerank.

**Trade-off đã chấp nhận:** Quyết định này làm tăng độ trễ (latency) của hệ thống thêm khoảng 300-500ms cho mỗi lượt truy vấn và tốn thêm chi phí API call. Tuy nhiên, đổi lại độ chính xác của thông tin đầu vào cho bước Synthesis tăng lên rõ rệt, giảm thiểu tình trạng LLM trả lời "không tìm thấy thông tin" (abstain) sai lệch.

**Bằng chứng từ trace/code:**
```python
def retrieve_dense(query: str, top_k: int = 10) -> list:
    # ... call chromadb ...
    # Rerank với Jina để lấy Top 3 chất lượng nhất
    reranked = rerank_with_jina(query, chunks)
    return reranked
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** Trace ghi nhận `retrieved_chunks` luôn trống dù câu hỏi rất rõ ràng.

**Symptom:** Khi chạy pipeline lần đầu với câu hỏi "SLA P1 là bao lâu?", hệ thống trả về "Không đủ thông tin" dù trong thư mục docs đã có file `sla_p1_2026.txt`.

**Root cause:** Nguyên nhân nằm ở việc không khớp (mismatch) giữa Embedding Model dùng để Index dữ liệu ban đầu và Embedding Model dùng để Query. Dữ liệu cũ trong `chroma_db` được index bằng mô hình local `all-MiniLM-L6-v2`, trong khi tôi mới cập nhật `retrieval.py` sang dùng `jina-embeddings-v2-base-en`. Gradient của hai không gian vector này hoàn toàn khác nhau khiến kết quả similarity luôn thấp hơn ngưỡng tìm kiếm.

**Cách sửa:** Tôi đã viết script `reindex.py` để xóa toàn bộ collection cũ và thực hiện embedding lại toàn bộ 5 tài liệu nội bộ bằng Jina API đồng nhất với retrieval logic.

**Bằng chứng trước/sau:** 
- Trước khi sửa: `confidence: 0.1`, `retrieved_chunks: []`.
- Sau khi sửa: `confidence: 0.92`, `retrieved_chunks: [{"text": "SLA P1: phản hồi 15 phút...", "source": "sla_p1_2026.txt", "score": 0.89}]`.

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

Tôi sẽ cải tiến `supervisor_node` bằng cách sử dụng một mô hình LLM nhỏ (như `llama-3-8b` trên Groq) thay vì keyword. Tôi sẽ thử điều này vì trace của câu `q15` (câu hỏi multi-hop khó nhất) cho thấy Supervisor đôi khi chỉ chọn `policy_tool_worker` mà bỏ qua `retrieval_worker` nếu câu hỏi có quá nhiều từ khóa về rule/policy cùng lúc.

---
