from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models import PachcaMessage, TicketStatusChange
from app.config import AppConfig, get_config
from app.service.event_processing.pachca_events import (
    process_subscribe,
    process_unsubscribe,
)
from app.service.event_processing.tracker_events import process_ticket_status_change
from app.service.orm.sessionmaker import get_session

router = APIRouter()


@router.post("/subscribe")
async def subscribe(
    message: PachcaMessage,
    config: AppConfig = Depends(get_config),
    session: AsyncSession = Depends(get_session),
):
    await process_subscribe(
        message=message,
        tracker_queue_key=config.tracker_queue_key,
        session=session,
    )


@router.post("/unsubscribe")
async def unsubscribe(
    message: PachcaMessage,
    config: AppConfig = Depends(get_config),
    session: AsyncSession = Depends(get_session),
):
    await process_unsubscribe(
        message=message,
        tracker_queue_key=config.tracker_queue_key,
        session=session,
    )


@router.post("/ticket_status_change")
async def ticket_status_change(
    ticket_event: TicketStatusChange,
    config: AppConfig = Depends(get_config),
    session: AsyncSession = Depends(get_session),
):
    await process_ticket_status_change(
        ticket_event=ticket_event,
        tracker_status_list=config.tracker_status_list,
        session=session,
    )
