from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class SyncLock(Base):
    """DB-gestuetzter Lauf-Lock pro User (ein aktiver Sync gleichzeitig).

    Ersetzt den prozess-lokalen In-Memory-Guard -> korrekt auch bei mehreren
    Worker-Prozessen. `locked_at` erlaubt Stale-Erkennung, falls ein Prozess
    abstuerzt, ohne den Lock freizugeben.
    """

    __tablename__ = "sync_locks"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    locked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
