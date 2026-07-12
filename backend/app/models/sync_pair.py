from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class SyncPair(Base):
    """Ein gerichtetes Sync-Paar: Quell-Kalender -> Ziel-Kalender.

    Zwei Richtungen = zwei Zeilen. Laeuft unter dem Token des `owner`.
    """

    __tablename__ = "sync_pairs"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    source_calendar_id: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_calendar_label: Mapped[str | None] = mapped_column(String(512), nullable=True)
    target_calendar_id: Mapped[str] = mapped_column(String(1024), nullable=False)
    target_calendar_label: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # "busy" = generischer Zeitblock ohne Details; "full" = Titel/Ort/Beschreibung.
    detail_level: Mapped[str] = mapped_column(String(16), nullable=False, default="busy")
    busy_title: Mapped[str] = mapped_column(String(255), nullable=False, default="Belegt")
    # Frei waehlbares Praefix vor jedem gespiegelten Titel, z.B. "(P)" -> zeigt
    # die Herkunft im Ziel-Kalender an. Leer = kein Praefix.
    title_prefix: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(16), nullable=False, default="never")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    owner = relationship("User", back_populates="sync_pairs")
    mappings = relationship(
        "EventMapping", back_populates="pair", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_sync_pairs_owner_active", "owner_user_id", "active"),)
