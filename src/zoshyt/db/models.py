"""Моделі SQLAlchemy — схема V1 (крок 4 плану; рішення закриті в арх-чаті 2026-09-14).

Лише «як зберігається»; сенс даних і правила — у journal. Імпорт цього
модуля реєструє таблиці в Base.metadata (потрібно alembic --autogenerate).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from zoshyt.db.base import Base


class School(Base):
    """Тенант. Власник — роль у school_members, не колонка тут (без циклу FK)."""

    __tablename__ = "schools"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    # Показ часу — за tz школи; у БД усе UTC.
    tz: Mapped[str] = mapped_column(Text, server_default="Europe/Kyiv")
    # Лічильник журналу: journal видає seq через
    # UPDATE schools SET last_seq = last_seq + 1 ... RETURNING last_seq
    # (row lock серіалізує команди одного тенанта).
    last_seq: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Teacher(Base):
    """Користувач. Ключ усюди — id (uuid); tg_user_id знає лише auth-адаптер."""

    __tablename__ = "teachers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    # NULL — під майбутній не-Telegram вхід (ADR-0001).
    tg_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    # Акаунтні дані самого користувача, не PII у сенсі ADR-0009.
    display_name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Оновлює auth-адаптер ліниво (~раз на годину).
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SchoolMember(Base):
    __tablename__ = "school_members"
    __table_args__ = (
        CheckConstraint("role in ('owner', 'teacher')", name="school_members_role_check"),
        # Частковий унікальний індекс: рівно один owner на школу.
        Index(
            "one_owner_per_school",
            "school_id",
            unique=True,
            postgresql_where=text("role = 'owner'"),
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"), primary_key=True)
    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teachers.id"), primary_key=True)
    role: Mapped[str] = mapped_column(Text)


class Event(Base):
    """Append-only журнал (ADR-0003). НІКОЛИ UPDATE/DELETE — і БД це гарантує:
    ревізія init робить REVOKE UPDATE, DELETE для ролі zoshyt_app.
    """

    __tablename__ = "events"
    __table_args__ = (
        # Канонічний порядок журналу; ним же сортується експорт CSV (ADR-0011).
        UniqueConstraint("school_id", "seq", name="events_school_id_seq_key"),
    )

    # Глобальний і з дірками (sequence не відкочується) — НЕ порядок журналу.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    school_id: Mapped[uuid.UUID] = mapped_column()  # тенант + стрім
    seq: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(Text)
    event_version: Mapped[int] = mapped_column(Integer)
    # PII живе тут (ADR-0009): у prod payload цілком не логувати.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    actor_teacher_id: Mapped[uuid.UUID | None] = mapped_column()
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
