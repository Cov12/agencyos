"""
AgencyOS Department Routes

Department listing + department-scoped chat routing.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from ..middleware.tenant import get_tenant_session
from ..models.db import AgencyOSDepartment
from ..services.orchestrator import Orchestrator

router = APIRouter(prefix="/api/agencyos/departments", tags=["agencyos-departments"])

# Singleton orchestrator
_orchestrator = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


class ChatRequest(BaseModel):
    message: str
    chat_id: Optional[str] = None
    conversation_history: list[dict] = []  # Previous messages for context


@router.get("/")
async def list_departments(
    org_id: str,
    db: Session = Depends(get_tenant_session),
):
    """List all departments for an organization."""
    departments = db.query(AgencyOSDepartment).filter_by(org_id=org_id, is_active=True).all()
    return {
        "departments": [
            {
                "id": d.id,
                "slug": d.slug,
                "name": d.name,
                "description": d.description,
                "model_tier": d.model_tier,
                "capabilities": d.capabilities,
            }
            for d in departments
        ],
        "total": len(departments),
    }


@router.get("/{department_id}")
async def get_department(
    department_id: str,
    org_id: str,
    db: Session = Depends(get_tenant_session),
):
    """Get department details."""
    dept = db.query(AgencyOSDepartment).filter_by(id=department_id, org_id=org_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return {
        "id": dept.id,
        "slug": dept.slug,
        "name": dept.name,
        "description": dept.description,
        "model_tier": dept.model_tier,
        "capabilities": dept.capabilities,
        "workpipe_modules": dept.workpipe_modules,
        "system_prompt": dept.system_prompt,
    }


@router.post("/{department_slug}/chat")
async def department_chat(
    department_slug: str,
    org_id: str,
    data: ChatRequest,
    request: Request,
    db: Session = Depends(get_tenant_session),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """Send a message to a department's AI."""
    result = await orchestrator.route_message(
        message=data.message,
        org_id=org_id,
        user_id=getattr(request.state, "user_id", "unknown"),
        department_slug=department_slug,
        chat_id=data.chat_id,
        db=db,
        conversation_history=data.conversation_history,
    )
    return result


@router.post("/chief/chat")
async def chief_chat(
    org_id: str,
    data: ChatRequest,
    request: Request,
    db: Session = Depends(get_tenant_session),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """Send a message to the Chief AI (cross-department reasoning)."""
    result = await orchestrator.route_message(
        message=data.message,
        org_id=org_id,
        user_id=getattr(request.state, "user_id", "unknown"),
        department_slug=None,
        chat_id=data.chat_id,
        db=db,
        conversation_history=data.conversation_history,
    )
    return result
