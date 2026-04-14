# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** Nhóm 10 - Đỗ Hải Nam  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Đỗ Hải Nam | Supervisor & Worker Owner | 26ai.namdh@vinuni.edu.vn |

**Ngày nộp:** 2026-04-14  
**Repo:** https://github.com/baeGil/2A202600038-DoHaiNam-Day09.git
**Độ dài khuyến nghị:** 600–1000 từ

---

## 1. Kiến trúc nhóm đã xây dựng (150–200 từ)

Hệ thống của tôi được xây dựng trên mô hình **Supervisor-Worker Orchestration** với 3 Worker chuyên biệt: Retrieval, Policy Tool, và Synthesis. Điểm khác biệt lớn nhất so với bài lab Day 08 là việc áp dụng Pipeline điều hướng linh hoạt dựa trên bối cảnh câu hỏi thay vì một chuỗi RAG cố định.

**Hệ thống tổng quan:**
- **Supervisor Node:** Phân tích câu hỏi để quyết định `supervisor_route`. Nếu là câu hỏi về quy định/cấp quyền, sẽ chuyển hướng sang `policy_tool_worker`. Nếu là câu tra cứu thông tin vận hành, chuyển sang `retrieval_worker`.
- **Retrieval Worker:** Sử dụng Jina Embedding API kết hợp với Jina Reranker v2 để đảm bảo context truyền vào synthesis là chất lượng nhất.
- **Policy Tool Worker:** Sử dụng LLM (Groq Kimi) để phân tích các ngoại lệ phức tạp và gọi các tool MCP để tra cứu thông tin thời gian thực.
- **Synthesis Worker:** Tổng hợp câu trả lời cuối cùng bám sát các chunks tìm được và cung cấp trích dẫn nguồn chi tiết.

**Routing logic cốt lõi:**
Tôi kết hợp giữa **Keyword Matching** (cho tốc độ cao với các từ khóa nhạy cảm như 'refund', 'access') và **Heuristic Logic** để đánh giá `risk_high`. Khi phát hiện từ khóa rủi ro hoặc mã lỗi hệ thống lạ (ERR-), Supervisor sẽ kích hoạt cờ `human_review` để đảm bảo an toàn.

**MCP tools đã tích hợp:**
- `search_kb`: Tìm kiếm sâu trong Knowledge Base.
- `get_ticket_info`: Tra cứu trạng thái ticket từ hệ thống mock.
- `check_access_permission`: Kiểm tra quyền hạn và quy trình phê duyệt khẩn cấp.

---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

**Quyết định:** Chuyển đổi toàn bộ cơ chế của `policy_tool_worker` từ Rule-based sang **LLM-based (Groq moonshotai/kimi-k2-instruct)**.

**Bối cảnh vấn đề:**
Ban đầu, tôi dự định dùng các câu lệnh `if-else` trong Python để bắt các ngoại lệ (như "Flash Sale" hay "Sản phẩm kỹ thuật số"). Tuy nhiên, thực tế test questions cho thấy người dùng hỏi rất đa dạng (ví dụ: "đơn ngày 31/01" — đòi hỏi so sánh thời gian để biết thuộc policy v3 hay v4). Rule-based trở nên quá cồng kềnh và dễ bỏ sót các trường hợp biên (edge cases).

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Rule-based (Python) | Tốc độ nhanh (gần như instantaneous), 0 cost. | Khó bảo trì, dễ sai với các câu hỏi phức tạp về temporal scoping. |
| LLM-based (Groq) | Thông minh, xử lý được ngôn ngữ tự nhiên, phân tích logic tốt. | Tăng chi phí API, tăng độ trễ (latency) của hệ thống. |

**Phương án đã chọn và lý do:**
Tôi chọn LLM-based. Lý do là model **Kimi K2 Instruct** trên Groq có tốc độ xử lý rất tốt và khả năng suy luận logic (reasoning) vượt trội ở tiếng Việt. Việc để LLM đọc trực tiếp các đoạn chính sách và so sánh với yêu cầu người dùng giúp hệ thống "hiểu" được ngữ cảnh thay vì chỉ bắt từ khóa thô.

**Bằng chứng từ code/trace:**
Trong trace của câu hỏi về hoàn tiền ngày 07/02 cho đơn ngày 31/01, LLM đã nhận diện đúng đây là trường hợp đặc biệt:
```json
{
  "policy_applies": false,
  "policy_version_note": "Đơn trước 01/02 áp dụng chính sách v3 (không có trong docs)",
  "explanation": "Khách hàng mua trước ngày hiệu lực của v4 nên cần tra cứu lại v3."
}
```

---

## 3. Kết quả grading questions (150–200 từ)

**Tổng điểm raw ước tính:** 92 / 96

**Câu pipeline xử lý tốt nhất:**
- ID: `q11` (P1 ticket notification) — Lý do tốt: Hệ thống bóc tách được chính xác timeline escalation (10 phút) và các kênh notify (Slack, Email, PagerDuty) từ tài liệu `sla_p1_2026.txt`.

**Câu pipeline fail hoặc partial:**
- ID: `q09` (ERR-403) — Fail ở đâu: Supervisor có route đúng sang human review do risk_high, nhưng Synthesis thi thoảng vẫn cố gắng bịa ra lỗi 403 là lỗi cấm truy cập thay vì báo "Không có trong tài liệu". 
- Root cause: Prompt synthesis cần ép chặt hơn nữa phần "Abstain" nếu không thấy evidence trong chunks.

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được (150–200 từ)

**Metric thay đổi rõ nhất (có số liệu):**
Độ tin cậy (Confidence) và Độ chính xác (Accuracy) đã tăng từ mức **0.1 lên trung bình >0.54** (nhiều câu đạt 0.75-0.9). Điều này nhờ vào kiến trúc **Advanced RAG (Semantic Chunking + Hybrid Search)** mà tôi áp dụng ở cuối Day 09, triệt tiêu bài toán "loãng thông tin" của Day 08. Thời gian phản hồi cũng được tối ưu từ mốc treo 48s về mức 3.7 giây.

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**
Sự ổn định và khả năng debug (Robustness). Với single agent của Day 08, một thay đổi nhỏ ở chunk size hay prompt có thể làm xáo trộn toàn bộ kết quả. Với multi-agent (Day 09), tôi có thể áp dụng các công nghệ khác nhau lên từng worker biệt lập (vd: Reranker riêng biệt cho Retrieval, LLM prompt tuning riêng biệt cho Policy). Trace log trở thành công cụ đắt giá để chỉ định chính xác nút thắt cổ chai (bottleneck) của hệ thống.

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**
Đối với các câu hỏi cực kỳ đơn giản (SLA P1 là bao lâu?), multi-agent làm chậm hệ thống gấp 2 lần mà kết quả không thay đổi so với Day 08. Đối với doanh nghiệp, đây là sự đánh đổi giữa trải nghiệm người dùng rực rỡ và độ an toàn hệ thống cao.

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Đỗ Hải Nam | Graph, Retrieval & Synthesis Workers | 1, 2, 4 |
| Đỗ Hải Nam | MCP Integration & Jina API | 3 |
| Đỗ Hải Nam | Documentation & Trace Analysis | 4 |

*(Lưu ý: Do đặc thù lab cá nhân, tôi đã cover hầu hết các phần từ core logic đến tài liệu).*

**Điều nhóm làm tốt:**
Tích hợp thành công bộ đôi Jina API (Reranking) và Groq API, giúp hệ thống có chất lượng search và tổng hợp câu tiếng Việt xuất sắc.

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**
Việc thiết lập ban đầu cho ChromaDB bị lỗi embedding mismatch tốn khá nhiều thời gian để debug (đã được ghi vào báo cáo cá nhân).

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì? (50–100 từ)

Tôi sẽ triển khai **Evaluator Node** (Double Check). Sau khi Synthesis trả lời, một node khác sẽ đọc câu trả lời và đối chiếu với chunks gốc một lần nữa để triệt tiêu hoàn toàn hallucination, đặc biệt là cho các mã lỗi lạ.

---

