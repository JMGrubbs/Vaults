"""add authentication event audit log

Revision ID: b2a5d7e3c901
Revises: 63bc040c9c18
Create Date: 2026-10-26 19:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2a5d7e3c901"
down_revision: Union[str, Sequence[str], None] = "63bc040c9c18"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS auth")
    op.create_table(
        "auth_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("token_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("email_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("method", sa.String(length=16), nullable=True),
        sa.Column("path", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="auth",
    )
    for name, column in (
        ("event_type", "event_type"),
        ("user_id", "user_id"),
        ("occurred_at", "occurred_at"),
        ("token_fingerprint", "token_fingerprint"),
        ("email_fingerprint", "email_fingerprint"),
    ):
        op.create_index(
            f"ix_auth_auth_events_{name}",
            "auth_events",
            [column],
            schema="auth",
        )


def downgrade() -> None:
    for name in (
        "email_fingerprint",
        "token_fingerprint",
        "occurred_at",
        "user_id",
        "event_type",
    ):
        op.drop_index(
            f"ix_auth_auth_events_{name}",
            table_name="auth_events",
            schema="auth",
        )
    op.drop_table("auth_events", schema="auth")
