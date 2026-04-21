import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import SchedulingConstraint, User
from app.schemas.timetable import ConstraintPayload, ParseInstructionRequest, ParseInstructionResponse
from app.services.gemini_service import GeminiConstraintService
from app.services.audit_service import AuditService

router = APIRouter(prefix="/rules", tags=["rules"])


@router.post("/parse", response_model=ParseInstructionResponse)
async def parse_instruction(payload: ParseInstructionRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await GeminiConstraintService(db).parse(current_user.school_id, payload.text)
    AuditService(db).record("rules_parsed", user=current_user, entity_type="constraint_parse", detail={"provider": result.provider, "constraint_count": len(result.constraints)})
    db.commit()
    return result


@router.post("", response_model=ConstraintPayload)
def create_constraint(payload: ConstraintPayload, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    row = SchedulingConstraint(
        school_id=current_user.school_id,
        rule_type=payload.rule_type,
        target_type=payload.target_type,
        target_values=json.dumps(payload.target_values),
        day_scope=json.dumps(payload.day_scope),
        period_scope=json.dumps(payload.period_scope),
        priority=payload.priority,
        description=payload.parsed_description,
        confidence_score=payload.confidence_score,
    )
    db.add(row)
    db.flush()
    AuditService(db).record("rule_created", user=current_user, entity_type="scheduling_constraint", entity_id=row.id, detail={"rule_type": row.rule_type, "priority": row.priority})
    db.commit()
    db.refresh(row)
    return payload


@router.get("")
def list_constraints(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = db.scalars(select(SchedulingConstraint).where(SchedulingConstraint.school_id == current_user.school_id).order_by(SchedulingConstraint.id.desc())).all()
    return [
        {
            "id": row.id,
            "rule_type": row.rule_type,
            "target_type": row.target_type,
            "target_values": json.loads(row.target_values or "[]"),
            "day_scope": json.loads(row.day_scope or "[]"),
            "period_scope": json.loads(row.period_scope or "[]"),
            "priority": row.priority,
            "parsed_description": row.description,
            "confidence_score": row.confidence_score,
            "is_active": row.is_active,
        }
        for row in rows
    ]
