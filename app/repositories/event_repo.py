from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import EventCreate
from app.domain.models import Event


class EventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_batch(self, events: list[EventCreate]) -> int:
        db_events = [
            Event(user_id=e.user_id, event_type=e.event_type, payload=e.payload) 
            for e in events
        ]
        self.session.add_all(db_events)
        await self.session.commit()
        return len(db_events)
