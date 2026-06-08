"""AgencyOS WorkPipe CRM routes."""

from fastapi import APIRouter, Depends

from ..services.workpipe import WorkPipeService

router = APIRouter(prefix="/api/agencyos/workpipe", tags=["agencyos-workpipe"])

_workpipe = WorkPipeService()


def get_workpipe_service() -> WorkPipeService:
    """Dependency provider for singleton WorkPipe service."""
    return _workpipe


@router.get("/contacts")
async def get_contacts(
    sub_account_id: str,
    limit: int = 50,
    offset: int = 0,
    service: WorkPipeService = Depends(get_workpipe_service),
):
    return await service.get_contacts(sub_account_id=sub_account_id, limit=limit, offset=offset)


@router.get("/contacts/search")
async def search_contacts(
    sub_account_id: str,
    q: str,
    limit: int = 20,
    service: WorkPipeService = Depends(get_workpipe_service),
):
    return await service.search_contacts(sub_account_id=sub_account_id, query=q, limit=limit)


@router.get("/contacts/{contact_id}")
async def get_contact(
    contact_id: str,
    service: WorkPipeService = Depends(get_workpipe_service),
):
    return await service.get_contact(contact_id=contact_id)


@router.get("/pipelines")
async def get_pipelines(
    sub_account_id: str,
    service: WorkPipeService = Depends(get_workpipe_service),
):
    return await service.get_pipelines(sub_account_id=sub_account_id)


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline_detail(
    pipeline_id: str,
    service: WorkPipeService = Depends(get_workpipe_service),
):
    return await service.get_pipeline_detail(pipeline_id=pipeline_id)


@router.get("/pipelines/{pipeline_id}/lanes/{lane_id}/tickets")
async def get_lane_tickets(
    pipeline_id: str,
    lane_id: str,
    limit: int = 50,
    service: WorkPipeService = Depends(get_workpipe_service),
):
    _ = pipeline_id  # path consistency and future validation hook
    return await service.get_tickets_in_lane(lane_id=lane_id, limit=limit)


@router.get("/deals/summary")
async def get_deals_summary(
    sub_account_id: str,
    service: WorkPipeService = Depends(get_workpipe_service),
):
    return await service.get_deal_summary(sub_account_id=sub_account_id)


@router.get("/invoices")
async def get_invoices(
    sub_account_id: str,
    limit: int = 50,
    service: WorkPipeService = Depends(get_workpipe_service),
):
    return await service.get_invoices(sub_account_id=sub_account_id, limit=limit)


@router.get("/invoices/summary")
async def get_invoice_summary(
    sub_account_id: str,
    service: WorkPipeService = Depends(get_workpipe_service),
):
    return await service.get_invoice_summary(sub_account_id=sub_account_id)


@router.get("/calendar/upcoming")
async def get_calendar_upcoming(
    sub_account_id: str,
    limit: int = 10,
    service: WorkPipeService = Depends(get_workpipe_service),
):
    return await service.get_upcoming_events(sub_account_id=sub_account_id, limit=limit)


@router.get("/health")
async def workpipe_health(service: WorkPipeService = Depends(get_workpipe_service)):
    return {
        "status": "ok" if service.is_connected else "degraded",
        "connected": service.is_connected,
        "service": "workpipe",
    }
