from app.api.reason_policy import reject_custom_reason_changes, DEFAULT_REASON_KEYS
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from typing import Literal

import db
from app.security import current_user_id
from sec_client import KNOWN_CIKS, get_company_facts
from tools import check_reason_status
from xbrl_extract import list_available_tags

router = APIRouter(prefix="/api", tags=["reasons"])


def _with_th_labels(tags: list[dict]) -> list[dict]:
    """Attaches label_th (from the one-time Claude-translated cache, see
    translate_xbrl_tags.py) to each tag dict, when available. A tag with no
    cached translation just has label_th=None -- the frontend falls back to
    the English label rather than showing a partial/guessed translation."""
    translations = db.get_tag_translations([t["tag"] for t in tags])
    for t in tags:
        t["label_th"] = translations.get(t["tag"])
    return tags


@router.get("/xbrl-tags/{ticker}")
def api_xbrl_tags(ticker: str, user_id: int = Depends(current_user_id)):
    """Every XBRL tag this specific company has actually reported -- the
    picker for defining a custom reason draws from this, never free text,
    so a custom reason can never reference a tag that doesn't exist for
    the company."""
    try:
        facts_json = get_company_facts(ticker.upper())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e))
    return _with_th_labels(list_available_tags(facts_json))


@router.get("/xbrl-tags")
def api_xbrl_tags_all(user_id: int = Depends(current_user_id)):
    """Union of every XBRL tag reported by ANY of the pilot companies --
    the picker for a reason that applies to every company (ticker=None),
    not just one. Still never free text: a global reason can only
    reference a tag that at least one real company has actually reported,
    same discipline as the per-ticker picker. Each entry also lists which
    tickers actually have it, so `tickers[0]` gives a safe company to
    preview-evaluate a global reason against before saving it, and the UI
    can show the coverage honestly instead of implying universal support."""
    by_tag: dict[str, dict] = {}
    for ticker in sorted(KNOWN_CIKS.keys()):
        try:
            facts_json = get_company_facts(ticker)
        except Exception:  # noqa: BLE001 -- one company's fetch failing shouldn't break the rest
            continue
        for t in list_available_tags(facts_json):
            entry = by_tag.setdefault(t["tag"], {
                "tag": t["tag"], "label": t["label"],
                "description": t.get("description"), "source": t.get("source"),
                "quarterly": False, "instant": False, "tickers": [],
            })
            entry["quarterly"] = entry["quarterly"] or t["quarterly"]
            entry["instant"] = entry["instant"] or t["instant"]
            entry["tickers"].append(ticker)
    return _with_th_labels(sorted(by_tag.values(), key=lambda t: t["tag"]))


@router.get("/reasons")
def api_list_all_reasons(ticker: str | None = None, user_id: int = Depends(current_user_id)):
    """The three read-only default reasons for new screening and purchases."""
    # Shared system definitions; ignore old personal overrides/hidden preferences.
    rows = db.list_reasons()
    return [r for key in DEFAULT_REASON_KEYS for r in rows if r["reason_key"] == key]


class ReasonIn(BaseModel):
    # None (or omitted) means a global reason -- applies to every company,
    # same as a built-in, but owned by this user (see db.save_reason /
    # db.list_reasons: ticker IS NULL is what makes it global).
    ticker: str | None = None
    metric: str = ""
    comparison: Literal[">", ">=", "<", "<="] = ">="
    threshold: float | None = Field(default=None, allow_inf_nan=False)
    kind: Literal["yoy_growth", "margin_level"] = "yoy_growth"
    description: str = Field(min_length=1, max_length=1000)
    rule_definition: dict | None = None
    original_text: str = Field(default="", max_length=5000)
    denominator_metric: str = ""
    instant: bool = False
    reason_key: str
    # Required only when ticker is None: which real company to
    # preview-evaluate the new reason against before confirming it
    # actually computes something (a global reason has no single "home"
    # ticker to check by default). Never stored -- purely for validation.
    preview_ticker: str | None = None


@router.post("/reasons", dependencies=[Depends(reject_custom_reason_changes)])
def api_create_reason(body: ReasonIn, user_id: int = Depends(current_user_id)):
    if body.reason_key.startswith("personal_builtin_") or body.reason_key in ("revenue_growth", "operating_margin", "debt_growth"):
        raise HTTPException(status_code=400, detail="reason_key collides with a built-in reason")

    ticker = body.ticker.upper() if body.ticker else None
    preview_ticker = (body.preview_ticker or body.ticker or "").upper()
    if not preview_ticker:
        raise HTTPException(status_code=400, detail="preview_ticker is required when ticker is not set")

    try:
        db.save_reason(
            reason_key=body.reason_key, user_id=user_id, ticker=ticker,
            metric=body.metric, comparison=body.comparison, threshold=body.threshold,
            kind=body.kind, description=body.description,
            denominator_metric=body.denominator_metric, instant=body.instant,
            rule_definition=body.rule_definition, original_text=body.original_text,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Confirm it actually computes something before telling the caller it
    # succeeded -- a tag picked from list_available_tags should always work,
    # but a margin reason's denominator could still turn out empty for this
    # specific ticker even though the tag exists company-wide in general.
    check = check_reason_status(preview_ticker, body.reason_key)
    return {"ok": True, "preview": check}


@router.delete("/reasons/{reason_key}", dependencies=[Depends(reject_custom_reason_changes)])
def api_delete_reason(reason_key: str, user_id: int = Depends(current_user_id)):
    try:
        db.delete_reason(reason_key, user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Reason not found")
    return {"ok": True}


class ReasonEditIn(BaseModel):
    description: str = Field(min_length=1, max_length=1000)
    comparison: Literal[">", ">=", "<", "<="] = ">="
    threshold: float | None = Field(default=None, allow_inf_nan=False)
    rule_definition: dict | None = None
    original_text: str | None = Field(default=None, max_length=5000)
    metric: str | None = None
    kind: Literal["yoy_growth", "margin_level"] | None = None
    denominator_metric: str | None = None
    instant: bool | None = None


@router.patch("/reasons/{reason_key}", dependencies=[Depends(reject_custom_reason_changes)])
def api_edit_reason(reason_key: str, body: ReasonEditIn, user_id: int = Depends(current_user_id)):
    original = db.get_reason_if_accessible(reason_key, user_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Reason not found")
    if not body.description.strip():
        raise HTTPException(status_code=400, detail="Description is required")
    # Shared definitions remain unchanged; each account gets one stable personal version.
    target = f"personal_builtin_{user_id}_{reason_key}" if original["is_builtin"] else reason_key
    try:
        db.save_reason(reason_key=target, user_id=user_id, ticker=original["ticker"],
                       metric=body.metric or original["metric"], kind=body.kind or original["kind"],
                       denominator_metric=body.denominator_metric if body.denominator_metric is not None else original.get("denominator_metric") or "",
                       instant=body.instant if body.instant is not None else original["instant"], description=body.description.strip(),
                       comparison=body.comparison, threshold=body.threshold,
                       rule_definition=body.rule_definition if body.rule_definition is not None else original.get("rule_definition"),
                       original_text=body.original_text if body.original_text is not None else original.get("original_text", ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "reason_key": target}
