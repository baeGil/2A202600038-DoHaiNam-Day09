# Routing Decisions Log — Lab Day 09

**Nhóm:** Nhóm 10 - Đỗ Hải Nam  
**Ngày:** 2026-04-14

---

## Routing Decision #1

**Task đầu vào:**
> SLA xử lý ticket P1 là bao lâu?

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `default route` (không chứa từ khóa chính sách/quyền truy cập)  
**MCP tools được gọi:** None  
**Workers called sequence:** `retrieval_worker` -> `synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): Ticket P1 có thời gian phản hồi ban đầu là 15 phút và thời gian xử lý là 4 giờ. [sla_p1_2026.txt]
- confidence: 0.95
- Correct routing? Yes

**Nhận xét:** Routing này hoàn toàn chính xác. Vì đây là câu hỏi tra cứu thông tin vận hành chuẩn, không vi phạm chính sách hay cần kiểm tra ngoại lệ, nên retrieval worker là lựa chọn tối ưu.

---

## Routing Decision #2

**Task đầu vào:**
> Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `task contains policy/access keyword`  
**MCP tools được gọi:** `search_kb` (gọi từ trong policy worker để lấy context)  
**Workers called sequence:** `policy_tool_worker` -> `retrieval_worker` (auto-triggered) -> `synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): Không, đơn hàng Flash Sale không được hoàn tiền theo Điều 3 chính sách v4. [policy_refund_v4.txt]
- confidence: 0.88
- Correct routing? Yes

**Nhận xét:** Supervisor nhận diện tốt từ khóa "hoàn tiền" và "flash sale". Việc chuyển hướng sang policy worker giúp hệ thống focus vào việc tìm kiếm các ngoại lệ thay vì chỉ liệt kê quy trình hoàn tiền chung.

---

## Routing Decision #3

**Task đầu vào:**
> Cần cấp quyền Level 3 để khắc phục P1 khẩn cấp. Quy trình là gì?

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `task contains policy/access keyword | risk_high flagged`  
**MCP tools được gọi:** `check_access_permission`  
**Workers called sequence:** `policy_tool_worker` -> `retrieval_worker` -> `synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): Level 3 không có quy trình cấp khẩn cấp (emergency bypass). Phải có đủ 3 bên phê duyệt. [access_control_sop.txt]
- confidence: 0.91
- Correct routing? Yes

**Nhận xét:** Đây là ca routing kết hợp. Supervisor vừa nhận diện được nhu cầu kiểm tra quyền truy cập, vừa gắn cờ `risk_high` do có từ khóa "khẩn cấp" và "P1". Kết quả cho thấy Policy worker đã gọi đúng tool MCP để kiểm tra điều kiện bypass.

---

## Routing Decision #4 (tuỳ chọn — bonus)

**Task đầu vào:**
> ERR-999-FATAL: Hệ thống sập không rõ nguyên nhân lúc 2am.

**Worker được chọn:** `human_review`  
**Route reason:** `unknown error code + risk_high → human review`

**Nhận xét: Đây là trường hợp routing khó nhất trong lab. Tại sao?**
Bởi vì "ERR-999-FATAL" không tồn tại trong bất kỳ tài liệu nào. Nếu để tự động, Retrieval Worker sẽ trả ra kết quả rỗng và Synthesis có thể hallucinate hoặc trả lời chung chung. Supervisor đã nhận diện được mã lỗi lạ cùng bối cảnh thời gian nhạy cảm (2am) để trigger HITL, đảm bảo an toàn hệ thống.

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 8 | 53% |
| policy_tool_worker | 7 | 47% |
| human_review | 1 | 6% |

### Routing Accuracy

- Câu route đúng: 14 / 15
- Câu route sai (đã sửa bằng cách nào?): 1 (Câu hỏi về Level 2 access ban đầu bị route vào retrieval, đã sửa bằng cách thêm từ khóa "access" vào policy_keywords).
- Câu trigger HITL: 1

### Lesson Learned về Routing

1. **Hybrid Approach:** Kết hợp giữa từ khóa cứng (keywords) cho các trường hợp rõ ràng và risk-keywords cho các trường hợp khẩn cấp là cách tiếp cận cân bằng giữa tốc độ và an toàn.
2. **Context First:** Policy worker nên tự động trigger Retrieval nếu chưa có context để tránh việc LLM phải tự đoán chính sách.

### Route Reason Quality

Các `route_reason` hiện tại (vd: "task contains policy/access keyword") đã khá đủ để debug. Tuy nhiên, nếu có thêm thông tin về "winning keywords" cụ thể (vd: "found: refund") thì sẽ còn hỗ trợ tốt hơn nữa cho việc điều chỉnh bộ lọc từ khóa.

