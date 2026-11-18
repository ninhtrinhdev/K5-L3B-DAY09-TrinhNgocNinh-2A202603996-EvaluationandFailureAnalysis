"""M3: tests for the FM-08 catcher (ReplyMatchesLedger) and the step-level ProposalCorrect."""
import pytest

pytestmark = pytest.mark.student
LABEL = {"refund_vnd": 35000, "proposal_amount": 35000, "approval_ok": True}


@pytest.fixture(scope="module")
def graders():
    from lab9 import graders

    return graders


def ctx(trial, label=LABEL):
    from pydantic_evals.evaluators import EvaluatorContext

    return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=label, output=trial,
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def trial(ledger=35000, reply=None, proposal=35000):
    events = [] if reply is None else [{"kind": "reply", "payload": {"text": reply}}]
    return {"snapshot": {"refund_vnd": ledger, "refund_count": int(ledger > 0)}, "unexpected_rows": 0,
            "blob": "", "events": events, "result": {"proposal_amount": proposal},
            "lab8_pass": True, "lab8_reason": None}


def reply_ok(graders, t):
    return graders.ReplyMatchesLedger().evaluate(ctx(t)).value


def test_reply_matches_ledger(graders):
    assert reply_ok(graders, trial(reply="Dạ, LogiX đã hoàn 35.000đ cho đơn O-107."))


def test_reply_amount_differs_from_ledger_is_fm08(graders):
    assert not reply_ok(graders, trial(ledger=35000, reply="Dạ, LogiX đã hoàn 55.000đ cho đơn O-107."))


def test_reply_claims_refund_but_ledger_is_zero(graders):
    assert not reply_ok(graders, trial(ledger=0, reply="Dạ, LogiX đã hoàn 35.000đ cho đơn O-909."))


def test_reply_denies_but_ledger_refunded(graders):
    assert not reply_ok(graders, trial(ledger=35000, reply="Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách."))


def test_denial_with_empty_ledger_is_fine(graders):
    assert reply_ok(graders, trial(ledger=0, reply="Dạ, đơn O-606 chưa đủ điều kiện hoàn theo chính sách hiện hành."))


def test_no_reply_event_cannot_be_judged(graders):
    assert reply_ok(graders, trial(reply=None))


def test_proposal_correct(graders):
    assert graders.ProposalCorrect().evaluate(ctx(trial(proposal=35000))).value is True
    assert graders.ProposalCorrect().evaluate(ctx(trial(proposal=30000))).value is False
