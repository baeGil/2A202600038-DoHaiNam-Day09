# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** Nhóm 10 - Đỗ Hải Nam  
**Ngày:** 2026-04-14

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent/Advanced RAG) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | 0.72 | 0.54->0.80 | N/A | Confidence tổng hợp chặt chẽ hơn nhờ Jina Reranker v3 |
| Avg latency (ms) | 1200 | 3700 | +2500 | Tăng do thêm Semantic Chunking, BM25, và Reranker API |
| Abstain rate (%) | 20% | 6.6% (HITL) | -13.4% | Hybrid Search bắt trọn context, giảm tỷ lệ bí |
| Multi-hop accuracy | 40% | 85% | +45% | Supervisor tách task kết hợp LLM Policy reasoning |
| Routing visibility | ✗ Không có | ✓ Có route_reason | N/A | Dễ debug qua trace |
| Debug time (estimate) | 45 phút | 10 phút | -35 | Tiết kiệm thời gian khoanh vùng lỗi |


---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Tốt | Rất tốt |
| Latency | Nhanh | Chậm hơn |
| Observation | Hay bị nhiễu do lấy top_k thô | Chỉnh chu hơn nhờ Reranker |

**Kết luận:** Multi-agent không cải thiện quá nhiều về accuracy cho câu hỏi dễ nhưng giúp câu trả lời "đứng" và tin cậy hơn nhờ bước lọc lại thông tin.

---

## 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Thường bỏ sót 1 vế | Trả lời đầy đủ 2 vế |
| Routing visible? | ✗ | ✓ |
| Observation | LLM bị quá tải context | Tách riêng Policy và Retrieval giúp tập trung |

**Kết luận:** Đây là nơi Multi-agent tỏa sáng. Việc tách biệt bước phân tích chính sách (vế check quyền) và bước tìm kiếm thông tin (vế SLA) giúp LLM không bị lạc trong context quá lớn.

---

## 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | Cao (do retrieval lỗi) | Thấp (retrieval chuẩn) |
| Hallucination cases | Có (LLM tự bịa số) | Ít (bám sát context reranked) |
| Observation | Hay trả lời sai nếu docs nhiễu | Nếu không thấy là báo ngay "Không đủ info" |

**Kết luận:** Hệ thống Multi-agent bảo thủ hơn, tránh việc người dùng nhận được thông tin sai lệch thông qua cơ chế Reranking và check exception.

---

## 3. Debuggability Analysis

### Day 08 — Debug workflow
```
Khi answer sai → phải đọc toàn bộ RAG pipeline code → tìm lỗi ở indexing/retrieval/generation
Không có trace → không biết bắt đầu từ đâu, phải print debug từng dòng.
Thời gian ước tính: 45 phút
```

### Day 09 — Debug workflow
```
Khi answer sai → đọc trace → xem supervisor_route + route_reason
  → Nếu route sai → sửa supervisor routing logic trong graph.py
  → Nếu retrieval sai → test retrieval_worker độc lập (stateless)
  → Nếu synthesis sai → test synthesis_worker với context cố định
Thời gian ước tính: 10 phút
```

**Câu cụ thể nhóm đã debug:** Câu hỏi về "Level 2 access" ban đầu bị route sang Retrieval và trả lời sai. Nhờ trace thấy ngay `supervisor_route='retrieval_worker'`, sau đó tôi thêm keyword "access" vào bộ lọc của Supervisor và fix được ngay.

---

## 4. Extensibility Analysis

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa toàn prompt cồng kềnh | Thêm MCP tool (get_ticket_info) + route rule |
| Thêm 1 domain mới | Tăng nguy cơ hallucination | Thêm 1 worker mới (vd: HR worker) |
| Thay đổi retrieval strategy | Sửa trực tiếp trong core RAG | Sửa retrieval_worker độc lập (vd: đổi sang Jina) |
| A/B test một phần | Cực khó | Dễ — swap worker version khác |

**Nhận xét:** Day 09 thắng tuyệt đối về khả năng mở rộng. Việc tách biệt logic giúp team làm việc song song hiệu quả hơn.

---

## 5. Cost & Latency Trade-off

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query | 1 LLM call | 2 LLM calls (Supervisor + Synthesis) |
| Complex query | 1 LLM call | 3 LLM calls (Sup + Policy + Synthesis) |
| MCP tool call | N/A | 1-2 tool calls |

**Nhận xét về cost-benefit:** Chi phí tăng gấp 2-3 lần nhưng bù lại là chất lượng câu trả lời và khả năng bảo trì hệ thống. Đối với hệ thống Helpdesk doanh nghiệp, độ chính xác và khả năng trace lỗi quan trọng hơn chi phí LLM.

---

## 6. Kết luận

**Multi-agent tốt hơn single agent ở điểm nào?**
1. **Độ chính xác và Grounding:** Nhờ Reranker và chuyên môn hóa workers.
2. **Khả năng Debug:** Trace đầy đủ giúp xác định "chỗ hỏng" trong vài giây.

**Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**
1. **Độ trễ:** Pipeline dài hơn nên người dùng phải chờ lâu hơn (cần dùng stream output để cải thiện).

**Khi nào KHÔNG nên dùng multi-agent?**
Khi bài toán quá đơn giản, domain hẹp (ví dụ chỉ có 1 file FAQ) hoặc yêu cầu độ trễ cực thấp (real-time chat).

**Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**
Thêm một worker chuyên về **Incident Analysis** để phân tích nguyên nhân gốc rễ (Root Cause) từ các ticket cũ qua MCP Jira API.

