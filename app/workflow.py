from datetime import UTC, datetime


class InvalidTransitionError(ValueError):
    pass


def _review_work_order(current_status: str, actor: str, target_status: str) -> dict[str, str | datetime]:
    """
    Pure state machine transition for reviewing a work order.
    Returns the dictionary of fields to update.
    """
    if current_status != "draft":
        raise InvalidTransitionError(f"Cannot transition from {current_status} to {target_status}")
    if not actor or not actor.strip():
        raise InvalidTransitionError("Review requires a named actor")

    return {
        "status": target_status,
        "reviewed_by": actor.strip(),
        "reviewed_at": datetime.now(UTC),
    }


def approve_work_order(current_status: str, actor: str) -> dict[str, str | datetime]:
    return _review_work_order(current_status, actor, "approved")


def reject_work_order(current_status: str, actor: str) -> dict[str, str | datetime]:
    return _review_work_order(current_status, actor, "rejected")
