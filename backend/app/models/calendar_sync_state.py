from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class CalendarSyncState(Base):
    """Inkrement-Cursor pro (User, Quell-Kalender). Mehrere Paare mit derselben
    Quelle teilen sich einen syncToken -> die Quelle wird pro Zyklus nur einmal
    gelesen."""

    __tablename__ = "calendar_sync_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    calendar_id: Mapped[str] = mapped_column(String(1024), nullable=False)

    sync_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_full_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_delta_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "calendar_id", name="uq_sync_state_user_cal"),
    )
