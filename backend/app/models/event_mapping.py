from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class EventMapping(Base):
    """Idempotenz-Tabelle: Quell-Event <-> gespiegeltes Ziel-Event pro Paar.

    UNIQUE(sync_pair_id, source_event_id) verhindert Duplikate: ein Update
    trifft immer dasselbe Ziel-Event.
    """

    __tablename__ = "event_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_pair_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sync_pairs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_event_id: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_ical_uid: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_recurring_event_id: Mapped[str | None] = mapped_column(
        String(1024), nullable=True
    )
    target_event_id: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_updated: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # "active" = gespiegelt vorhanden; "deleted" = Ziel entfernt.
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    pair = relationship("SyncPair", back_populates="mappings")

    __table_args__ = (
        UniqueConstraint(
            "sync_pair_id", "source_event_id", name="uq_mapping_pair_source"
        ),
    )
