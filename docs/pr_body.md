## Lab 9 — Evaluation & Failure Analysis (LogiX-VN)

Hoàn thành M0 đến M7. Tài liệu: `docs/failure_taxonomy.md`, `judge_audit.md`, `trace_case.md`, `eval_card.md`, `PRD_v1.1.md`.

### Gate `seeded_regression` (v1) — exit 1
```
$ python -m lab9.gate --pr reports/eval_seeded_regression.json --baseline reports/baseline_v1.json
  refund_amount_correct  0.8571   Δ -0.129 CI [-0.315, +0.000] BLOCK
  pass_rate              0.7143   Δ -0.271 CI [-0.500, -0.057] BLOCK
  reply_matches_ledger   0.7857   Δ -0.214 CI [-0.429, +0.000] BLOCK
exit 1 — blocked: refund_amount_correct, pass_rate, reply_matches_ledger
```

### Scorecard (`lab9.mutation`, spec v2)
```
fixed                expect merge got merge ok
honest_refactor      expect merge got merge ok
seeded_regression    expect block got block ok   refund_amount_correct, pass_rate, pass_hat_5, reply_matches_ledger, slice:denial/pass_rate, slice:money_movement/pass_rate, slice:adversarial/pass_rate
slice_regression     expect block got block ok   slice:money_movement/pass_rate
flaky_regression     expect block got block ok   pass_rate, pass_hat_5, slice:money_movement/pass_rate
mutation score 3/3 · false alarms 0
```

### A/A (`--aa 66,77,88,99,110`)
Δ = +0.0000 ở mọi metric (MockLLM, seed cố định). `pass_hat_5` = 0.8929 ở cả hai bộ seed, nên sàn 0.85 nằm dưới baseline và trên `flaky_regression` (0.5714).

### 4 trap công khai (`lab9.traps`) — đều bị chặn (exit 1)
```
trap evaluator_errors_as_nan  blocked
trap dropped_failing_rows     blocked
trap cherry_picked_seeds      blocked
trap loosened_spec            blocked
exit 0 — the gate blocked every public trap
```

### Giới hạn
FM-09 chưa quan sát được trace lỗi (host chặn). Trap ẩn của giảng viên có thể khác 4 trap công khai.
