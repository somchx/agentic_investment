from app.api.reason_policy import reject_custom_reason_changes
"""Authenticated natural-thesis interpretation, confirmation, versioning and investigations."""
import logging
import uuid
import time
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
import requests
import db
from app.security import current_user_id
from app.rate_limit import limiter
from app.api.language import ui_language
from app.db.models import ThesisInvestigation,ThesisClarification
from natural_thesis import proposal, confirm_proposal, resolve_version, history
from thesis_evidence import investigate
from sec_client import is_supported_ticker, SecDataUnavailableError

router=APIRouter(prefix='/api/theses',tags=['natural-theses'])
logger=logging.getLogger(__name__)

class InterpretIn(BaseModel):
    ticker: str = Field(min_length=1,max_length=10)
    original_text: str = Field(min_length=10,max_length=5000)

class ConfirmIn(BaseModel):
    confirmation_token: str = Field(max_length=100000)
    confirmed: bool
    reason_key: str | None = None
    expected_version_id: str | None = None
    clarifications: dict[str,str] = Field(default_factory=dict)

class InvestigateIn(BaseModel):
    evaluation_date: date
    period_start: date
    period_end: date
    thesis_version_id: str | None = None
    purchase_id: int | None = None
    acknowledge_cost: bool = False

class ClarifyIn(BaseModel):
    revision:int=Field(ge=0)
    action:str=Field(pattern='^(retry|answer|explain|explore|rewind)$')
    answer:str=Field(default='',max_length=1000)
    question_key:str|None=None
    keep_answers:int|None=None

@router.post('/clarifications', dependencies=[Depends(reject_custom_reason_changes)])
@limiter.limit('10/minute')
def start_clarification(body:InterpretIn,request:Request,user_id:int=Depends(current_user_id)):
    from thesis_clarification import start
    ticker=body.ticker.upper()
    if not is_supported_ticker(ticker):raise HTTPException(400,'Unsupported company')
    return start(body.original_text.strip(),ticker,user_id,ui_language(request) or 'en')

@router.get('/clarifications/{draft_id}')
def read_clarification(draft_id:str,user_id:int=Depends(current_user_id)):
    from thesis_clarification import get_draft
    try:return get_draft(draft_id,user_id)
    except ValueError as exc:raise HTTPException(404,str(exc))

@router.post('/clarifications/{draft_id}', dependencies=[Depends(reject_custom_reason_changes)])
@limiter.limit('15/minute')
def continue_clarification(draft_id:str,body:ClarifyIn,request:Request,user_id:int=Depends(current_user_id)):
    from thesis_clarification import advance
    try:return advance(draft_id,user_id,body.revision,body.action,body.answer,body.question_key,body.keep_answers)
    except ValueError as exc:raise HTTPException(409,str(exc))
    except (RuntimeError,requests.RequestException):raise HTTPException(503,'Clarification unavailable. Your saved draft can be retried.')

@router.post('/interpret', dependencies=[Depends(reject_custom_reason_changes)])
@limiter.limit('10/minute')
def interpret(body:InterpretIn,request:Request,user_id:int=Depends(current_user_id)):
    ticker=body.ticker.upper()
    if not is_supported_ticker(ticker):raise HTTPException(400,'Unsupported company')
    try:return proposal(body.original_text.strip(),ticker,user_id,ui_language(request) or 'en')
    except ValueError as exc:raise HTTPException(422,str(exc))
    except (RuntimeError,requests.RequestException) as exc:
        logger.warning('Interpretation unavailable: %s',type(exc).__name__)
        raise HTTPException(503,'Interpretation unavailable. Check LLM configuration or retry.')

@router.post('/confirm', dependencies=[Depends(reject_custom_reason_changes)])
def confirm(body:ConfirmIn,user_id:int=Depends(current_user_id)):
    if not body.confirmed:raise HTTPException(400,'Explicit user confirmation required')
    if len(body.clarifications)>6 or any(len(v)>1000 for v in body.clarifications.values()):
        raise HTTPException(422,'Clarifications too long')
    try:return confirm_proposal(body.confirmation_token,user_id,body.reason_key,body.clarifications,body.expected_version_id)
    except ValueError as exc:raise HTTPException(409,str(exc))

@router.get('/{reason_key}/versions')
def versions(reason_key:str,user_id:int=Depends(current_user_id)):
    return history(user_id,reason_key)

@router.post('/{reason_key}/investigate')
@limiter.limit('5/minute')
def run(reason_key:str,body:InvestigateIn,request:Request,user_id:int=Depends(current_user_id)):
    if not body.acknowledge_cost:raise HTTPException(400,'Acknowledge LLM cost before investigation')
    draft_id=None
    computed=False
    try:
        version=resolve_version(user_id,reason_key,body.thesis_version_id,body.purchase_id)
        from thesis_clarification import require_investigable
        require_investigable(version['definition'])
        draft_id=version['definition'].get('clarification_id')
        if draft_id:
            with db.SessionLocal() as session:
                draft=session.scalar(select(ThesisClarification).where(ThesisClarification.id==draft_id,ThesisClarification.user_id==user_id).with_for_update())
                if draft:
                    if draft.state=='INVESTIGATING' and time.time()-draft.payload.get('investigating_at',0)<600:
                        draft_id=None
                        raise ValueError('Investigation already running; wait for completion')
                    draft.state='INVESTIGATING';draft.payload={**draft.payload,'investigating_at':time.time()};session.commit()
        result=investigate(version,body.evaluation_date.isoformat(),body.period_start.isoformat(),body.period_end.isoformat(),language=ui_language(request) or 'en')
        computed=True
    except ValueError as exc:raise HTTPException(422,str(exc))
    except (RuntimeError,SecDataUnavailableError,requests.RequestException) as exc:
        logger.warning('Natural investigation unavailable: %s',type(exc).__name__)
        raise HTTPException(503,'Evidence investigation unavailable; no completed result was saved.')
    finally:
        if draft_id and not computed:
            with db.SessionLocal() as session:
                draft=session.get(ThesisClarification,draft_id)
                if draft:draft.state='CONFIRMED';session.commit()
    record_id=uuid.uuid4().hex
    with db.SessionLocal() as session:
        session.add(ThesisInvestigation(id=record_id,user_id=user_id,reason_key=reason_key,thesis_version_id=version['id'],
            purchase_id=body.purchase_id,evaluation_date=body.evaluation_date.isoformat(),result=result))
        if draft_id:
            draft=session.get(ThesisClarification,draft_id)
            if draft:draft.state='COMPLETED'
        session.commit()
    return {'id':record_id,**result}

@router.get('/{reason_key}/investigations')
def investigations(reason_key:str,thesis_version_id:str|None=None,purchase_id:int|None=None,user_id:int=Depends(current_user_id)):
    with db.SessionLocal() as session:
        stmt=select(ThesisInvestigation).where(ThesisInvestigation.user_id==user_id,ThesisInvestigation.reason_key==reason_key)
        if thesis_version_id:stmt=stmt.where(ThesisInvestigation.thesis_version_id==thesis_version_id)
        if purchase_id is not None:stmt=stmt.where(ThesisInvestigation.purchase_id==purchase_id)
        return [db._row_to_dict(r) for r in session.scalars(stmt.order_by(ThesisInvestigation.created_at.desc()).limit(30))]
