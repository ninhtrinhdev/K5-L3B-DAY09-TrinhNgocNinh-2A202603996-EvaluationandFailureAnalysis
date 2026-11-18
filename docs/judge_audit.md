# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt cả 3 | **Dùng** (kèm sửa rubric bên dưới) |
| helpful | 100 | 0.375 | 1.000 | 0.300 | **Không đạt**: κ < 0.6 và R < 0.7 (P đạt) | **Loại**, không dùng làm gate |

Ma trận nhầm lẫn (FAIL là lớp dương):

| Tiêu chí | tp | fp | fn | tn | Tỉ lệ FAIL quan sát | Tỉ lệ FAIL sau hiệu chỉnh Rogan-Gladen |
|---|---|---|---|---|---|---|
| tone_ok | 24 | 4 | 6 | 66 | 0.28 | 0.30 |
| helpful | 9 | 0 | 21 | 70 | 0.09 | 0.30 |

## ≥5 case audit thủ công
Lấy từ `judge_tone_public.csv` (10 bất đồng: 6 judge bỏ sót lỗi, 4 judge báo thừa).

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người | Xưng "em" + "nha" quá suồng sã; judge nhầm là thân thiện. Rubric thêm: bắt buộc "Dạ" + xưng "anh/chị", cấm "em/nha/bạn ơi" với khách. |
| 2 | H-029 "Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm." | PASS | FAIL | Người | Giọng ra lệnh, judge chỉ thấy chữ "Dạ, vui lòng". Rubric thêm: không dùng câu cấm/ra lệnh ("không cần...", "đừng..."). |
| 3 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Ngắn nhưng đủ ý; judge phạt vì "thiếu xin lỗi". Rubric sửa: chỉ yêu cầu xin lỗi khi từ chối hoặc có sự cố, không bắt buộc ở mọi câu. |
| 4 | H-051 "Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ." | FAIL | PASS | Người | CS LogiX cho phép dùng "refund"; judge phạt vì tiếng Anh. Rubric thêm danh sách thuật ngữ cho phép (refund, ...). |
| 5 | H-063 "Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ." | PASS | FAIL | Người | Hứa "sẽ hoàn thêm" ngoài kết quả của hệ thống. Rubric thêm: không hứa hành động mà hệ thống chưa ghi nhận. |
| 6 | H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ." | FAIL | PASS | **Judge** | Theo ghi chú trong dữ liệu, nhãn người sai do đọc nhầm ticket; cần **sửa nhãn người**, không phải sửa judge. |
| 7 | H-088 "Dạ, dạ, LogiX đã hoàn 40.000đ cho đơn O-233 ạ." | FAIL | PASS | Người (có tranh cãi) | Lặp "Dạ" là lỗi gõ, không phải giọng điệu. Rubric nói rõ: lỗi gõ vặt không tính vào tone_ok. |

Nhận xét chung: trong 7 ca, judge đúng 1 ca (H-081, lỗi nằm ở nhãn người), còn 6 ca là judge sai do rubric thiếu quy tắc cụ thể về xưng hô, giọng ra lệnh, thuật ngữ cho phép và hứa ngoài hệ thống.

## Kết luận
- **Tiêu chí bị loại: `helpful`.** Ma trận nhầm lẫn: tp=9, fp=0, fn=21, tn=70. Lý do loại là **recall = 0.3 < 0.7** và **κ = 0.375 < 0.6**: cứ 10 lỗi thật thì judge bỏ sót 7 (21/30). Precision = 1.0 không cứu được, vì precision chỉ đo độ đúng của những lần judge dám báo FAIL (9/9), mà judge rất dễ dãi và hầu như không bao giờ báo FAIL (9/100 trả lời). Precision cao ở đây là triệu chứng của một judge quá dễ dãi, không phải lý do để tin nó. Gate dùng judge này sẽ báo xanh trong khi 70% lỗi vẫn nằm đó.
- **Vì sao judge bỏ sót:** cả 21 bất đồng đều là judge PASS còn người FAIL, gồm 18 ca "sai tiền" (reply nói số tiền khác ledger, ví dụ HL-015 nói 55.000đ trong khi ledger ghi 40.000đ) và 3 ca "sai xưng hô". Judge chỉ đọc câu trả lời, không thấy ledger, nên không có cách nào biết số tiền sai. Trong 9 lỗi judge bắt được, không có ca "sai tiền" nào (4 giọng cụt, 3 không hỏi lại mã đơn, 2 lạc đề).
- **Số liệu bị méo:** tỉ lệ FAIL quan sát chỉ 0.09, sau hiệu chỉnh Rogan-Gladen là 0.30, tức judge đánh giá thấp lỗi khoảng 3 lần.
- **Việc đúng để làm:** lỗi "sai tiền" phải chấm bằng **code** so reply với ledger (đây là FM-08 trong taxonomy), không giao cho judge. Phần còn lại của `helpful` cần judge có rubric thấy được ledger, hoặc chấm tay.
- **Rủi ro còn lại:** judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật. `tone_ok` vượt ngưỡng nhưng recall 0.8 vẫn bỏ sót 6/30 lỗi (xưng hô suồng sã, giọng ra lệnh, hứa ngoài hệ thống), nên rubric phải sửa như bảng trên rồi đo lại. Ca H-081 cho thấy nhãn người cũng có thể sai, nên không coi nhãn người là chân lý tuyệt đối.
