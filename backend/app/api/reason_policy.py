"""Current product policy: new purchases use only the three system reasons."""
from fastapi import HTTPException

DEFAULT_REASON_KEYS = ("revenue_growth", "operating_margin", "debt_growth")


def reject_custom_reason_changes():
    raise HTTPException(status_code=403, detail="This version uses the three default investment reasons. Custom reason authoring is disabled.")
