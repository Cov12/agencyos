"""
AgencyOS Department Routes

CRUD for departments + department-scoped chat routing.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional

from ..models.department import Department, DepartmentCreate, DepartmentKnowledge
from ..services.orchestrator import Orchestrator

router = APIRouter(prefix="/api/agencyos/departments", tags=["agencyos-departments"])

# Singleton orchestrator (will be dependency-injected properly later)
_orchestrator = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


@router.get("/")
async def list_departments(
    org_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """List all departments for an organization."""
    # TODO: Filter by org_id from database
    # TODO: Check user permissions
    return {
        "departments": list(orchestrator.departments.keys()),
        "org_id": org_id,
    }


@router.get("/{department_slug}")
async def get_department(
    department_slug: str,
    org_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """Get department details."""
    dept = orchestrator.departments.get(department_slug)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return {"department": dept, "slug": department_slug, "org_id": org_id}


@router.post("/{department_slug}/chat")
async def department_chat(
    department_slug: str,
    org_id: str,
    message: str,
    user_id: str,
    chat_id: Optional[str] = None,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    Send a message to a department's AI.
    The orchestrator routes it with proper scoping.
    """
    result = await orchestrator.route_message(
        message=message,
        org_id=org_id,
        user_id=user_id,
        department_slug=department_slug,
        chat_id=chat_id,
    )
    return result


@router.post("/chief/chat")
async def chief_chat(
    org_id: str,
    message: str,
    user_id: str,
    chat_id: Optional[str] = None,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    Send a message to the Chief AI.
    Handles cross-department reasoning and delegation.
    """
    result = await orchestrator.route_message(
        message=message,
        org_id=org_id,
        user_id=user_id,
        department_slug=None,  # Chief handles routing
        chat_id=chat_id,
    )
    return result
