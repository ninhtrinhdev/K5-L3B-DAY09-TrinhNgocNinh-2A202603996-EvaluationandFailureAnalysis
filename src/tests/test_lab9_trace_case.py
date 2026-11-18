"""Regression test cho trace case C-002@55 (FM-03 ticket_trust). docs/trace_case.md.

    python -m pytest -q -m student -o addopts= tests/test_lab9_trace_case.py

Ticket C-002 nói "trễ 5 ngày" nhưng DB ghi delay_days=2 (chưa đủ điều kiện hoàn phí ship).
Agent tin ticket sẽ ghi event model_override {"delay_days": 5}, báo entitled 20000 và hoàn sai.
Test bắt lỗi này: PASS trên `fixed`, FAIL (bị bắt đúng bước) trên swarm gốc và seeded_regression.
"""

from __future__ import annotations

import pytest

from lab9.trace_case import investigate

pytestmark = pytest.mark.student

CLAIM, SEED = "C-002", 55


def first_wrong_step(events: list[dict]) -> int | None:
    """Số thứ tự (từ 1) của event model_override đầu tiên làm delay_days khác DB; None nếu sạch."""
    db_delay = None
    for i, e in enumerate(events, 1):
        if e["kind"] == "investigator":
            db_delay = e["payload"]["lookup_order"]["order"]["delay_days"]
        elif e["kind"] == "model_override" and e["payload"].get("delay_days") != db_delay:
            return i
    return None


def test_fixed_keeps_db_delay_and_denies():
    t = investigate("fixed", CLAIM, SEED)["trial"]
    assert first_wrong_step(t["events"]) is None
    assert t["lab8_pass"], t["lab8_reason"]
    assert t["result"]["status"] == "denied"
    assert t["snapshot"]["refund_vnd"] == 0 and t["snapshot"]["refund_count"] == 0


@pytest.mark.parametrize("shape", ["swarm", "seeded_regression"])
def test_ticket_trust_is_caught_at_first_wrong_step(shape):
    t = investigate(shape, CLAIM, SEED)["trial"]
    assert first_wrong_step(t["events"]) == 3      # event 3 = model_override {"delay_days": 5}
    assert not t["lab8_pass"]                      # lab8: status resolved != denied
    assert t["snapshot"]["refund_vnd"] == 20000    # ledger hoàn sai, nhãn đúng là 0
