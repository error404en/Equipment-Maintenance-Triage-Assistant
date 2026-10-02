import pytest

from app.workflow import InvalidTransitionError, approve_work_order, reject_work_order


def test_approve_work_order_success() -> None:
    updates = approve_work_order("draft", "Alice")
    assert updates["status"] == "approved"
    assert updates["reviewed_by"] == "Alice"
    assert updates["reviewed_at"] is not None


def test_reject_work_order_success() -> None:
    updates = reject_work_order("draft", "Bob")
    assert updates["status"] == "rejected"
    assert updates["reviewed_by"] == "Bob"
    assert updates["reviewed_at"] is not None


def test_approve_non_draft_raises_error() -> None:
    with pytest.raises(InvalidTransitionError, match="Cannot transition from approved to approved"):
        approve_work_order("approved", "Alice")


def test_reject_non_draft_raises_error() -> None:
    with pytest.raises(InvalidTransitionError, match="Cannot transition from rejected to rejected"):
        reject_work_order("rejected", "Bob")


def test_review_requires_actor() -> None:
    with pytest.raises(InvalidTransitionError, match="Review requires a named actor"):
        approve_work_order("draft", "")

    with pytest.raises(InvalidTransitionError, match="Review requires a named actor"):
        approve_work_order("draft", "   ")
