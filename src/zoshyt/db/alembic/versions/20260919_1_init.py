"""init: schools, teachers, school_members, events (схема V1, крок 4 плану)

Чернетка — autogenerate; прочитана і дописана руками:
- REVOKE UPDATE, DELETE ON events FROM zoshyt_app — autogenerate грантів не бачить;
- порядок таблиць і явні імена обмежень.

Revision ID: 20260919_1
Revises:
Create Date: 2026-09-19 17:04:26.701507

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260919_1"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schools",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("tz", sa.Text(), server_default="Europe/Kyiv", nullable=False),
        # Лічильник журналу: seq видає journal через UPDATE ... RETURNING last_seq.
        sa.Column("last_seq", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "teachers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tg_user_id", name="teachers_tg_user_id_key"),
    )
    op.create_table(
        "school_members",
        sa.Column("school_id", sa.Uuid(), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.CheckConstraint("role in ('owner', 'teacher')", name="school_members_role_check"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"]),
        sa.PrimaryKeyConstraint("school_id", "teacher_id"),
    )
    # Рівно один owner на школу — частковий унікальний індекс.
    op.create_index(
        "one_owner_per_school",
        "school_members",
        ["school_id"],
        unique=True,
        postgresql_where=sa.text("role = 'owner'"),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("school_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("actor_teacher_id", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        # Канонічний порядок журналу; єдиний додатковий індекс V1.
        sa.UniqueConstraint("school_id", "seq", name="events_school_id_seq_key"),
    )
    # Append-only гарантує БД, не код (ADR-0003). Default privileges з
    # ops/db/init.sh уже видали zoshyt_app повний набір — тому саме REVOKE.
    # TRUNCATE app не має взагалі (default privileges його не дають).
    op.execute("REVOKE UPDATE, DELETE ON events FROM zoshyt_app")


def downgrade() -> None:
    op.drop_table("events")
    op.drop_index(
        "one_owner_per_school",
        table_name="school_members",
        postgresql_where=sa.text("role = 'owner'"),
    )
    op.drop_table("school_members")
    op.drop_table("teachers")
    op.drop_table("schools")
