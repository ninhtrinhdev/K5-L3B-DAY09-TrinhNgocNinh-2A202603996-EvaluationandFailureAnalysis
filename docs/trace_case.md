# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `<shape> <claim>@<seed>`, run ID trong report |
| Triệu chứng | Grader nào fail; reply nói gì so với ledger ghi gì |
| Bước sai đầu tiên | Số thứ tự event + kind + trích payload (≤1 dòng) |
| Vì sao là bước *đầu tiên* | Các bước trước đó đúng ra sao (dẫn số event) |
| Failure mode | Mã FM-xx trong `docs/failure_taxonomy.md` |
| Đối chứng | Cùng claim@seed trên shape `fixed`: bước đó khác thế nào |
| Regression test | Tên test + grader/assert nào bắt được; đã thấy fail trên variant lỗi và pass trên `fixed` chưa |
| Chưa chắc chắn | Điều trace không chứng minh được |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.

---

## Case của tôi: `swarm C-002@55`

| Trường | Nội dung |
|---|---|
| Trial | `swarm C-002@55`, run ID `R-swarm-C-002-s55`. Cùng lỗi ở `seeded_regression C-002@11..55`. |
| Triệu chứng | Lab8 grader FAIL `status resolved != denied`. Ledger ghi hoàn 20.000đ (1 lần), nhãn đúng là 0đ và `denied`. |
| Bước sai đầu tiên | Event 3, `model_override`, payload `{"delay_days": 5}`. |
| Vì sao là bước *đầu tiên* | Event 1 `handoff` đúng (`owner_order_only`, `allowed_tools` hợp lệ). Event 2 `investigator` đọc đúng DB: đơn O-202 `delay_days: 2`, `delivered`. Event 3 là lúc agent ghi đè 2 thành 5 theo ticket ("giao trễ 5 ngày"). Event 4 `quote` 20.000đ "entitled" và khoản hoàn sai chỉ là hệ quả của event 3. |
| Failure mode | **FM-03** `ticket_trust` (tin ticket hơn DB). |
| Đối chứng | `fixed C-002@55`: event 3 là `quote {"amount_vnd": 0, "reason": "no_entitlement"}`, không có `model_override`. Reply "chưa đủ điều kiện hoàn", ledger=0, `denied`, lab8 PASS. |
| Regression test | `tests/test_lab9_trace_case.py`: `test_fixed_keeps_db_delay_and_denies` (pass trên `fixed`) và `test_ticket_trust_is_caught_at_first_wrong_step` (chạy trên `swarm` và `seeded_regression`, assert bước sai đầu tiên = event 3, lab8 FAIL, ledger 20000). Đã chạy: 3 passed. Test dùng grader code (so `delay_days` của `model_override` với DB và đọc ledger), không dùng judge. |
| Chưa chắc chắn | Trace chỉ cho thấy agent ghi đè `delay_days`, không cho thấy lý do bên trong mô hình. Biến thể `quiet_override` cũng tin ticket nhưng **không ghi event** `model_override`; test sẽ không bắt bằng event đó mà chỉ bắt được qua ledger/lab8 grader. Lỗi ở swarm gốc chỉ xuất hiện ở seed 55 (seed chia hết cho 5), nên 4 seed còn lại không chứng minh gì về độ tin cậy. |

### Vì sao chọn C-002@55 làm regression test
1. **Lỗi có thật trên agent gốc, không phải lỗi cài thêm.** Đây là điểm yếu có sẵn của swarm tham chiếu mà lab08 đã ghi nhận ("Swarm fail đúng một trial"), và `tests/test_public_matrix.py` còn khai báo sẵn `SWARM_EXPECTED_MISSES = {("C-002", 55)}`. Nếu một bản sửa sau này quay lại tin ticket, test này bắt được.
2. **Bước sai nhìn thấy được trên trace.** Event 3 `model_override` cho phép chỉ đúng "bước sai đầu tiên" thay vì chỉ thấy kết quả cuối.
3. **Chấm được bằng code, tất định.** Tiền và approval phải chấm bằng code. MockLLM với seed cố định cho cùng một trace mỗi lần, nên test không chập chờn.
4. **Đủ hai chiều.** Test pass trên `fixed` và fail (bị bắt đúng bước 3) trên `swarm` và `seeded_regression`, nên nó phân biệt được bản đúng với bản sai.
5. **Ảnh hưởng tiền thật.** Lỗi làm hoàn 20.000đ cho đơn không đủ điều kiện, thuộc nhóm lỗi tiền bạc có mức rủi ro cao nhất.
