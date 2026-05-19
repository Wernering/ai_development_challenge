from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class LogEntry(Base):
    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    level: Mapped[str] = mapped_column(String(16))
    service: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    log_metadata: Mapped[str] = mapped_column("metadata", Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"<LogEntry id={self.id} level={self.level} service={self.service}>"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    severity: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text)
    error_count: Mapped[int] = mapped_column(Integer)
    threshold: Mapped[int] = mapped_column(Integer)
    window_seconds: Mapped[int] = mapped_column(Integer)
    source_service: Mapped[str] = mapped_column(String(64))
    ai_classification: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"<Alert id={self.id} severity={self.severity} service={self.source_service}>"
