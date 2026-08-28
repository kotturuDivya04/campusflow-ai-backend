"""additive MVP operational tables (faculty_busy_blocks, queue_entries)

Revision ID: 0001_mvp_operational
Revises:
Create Date: 2026-01-01

Assumes the FINALIZED schema (migrations/001_core_schema.sql) is already
present. This revision ONLY adds the two documented operational tables and the
scheduling rows in system_settings. It never alters a canonical table.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_mvp_operational"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "faculty_busy_blocks",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("faculty_id", sa.BigInteger,
                  sa.ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False),
        sa.Column("block_date", sa.Date, nullable=False),
        sa.Column("academic_slot_id", sa.BigInteger,
                  sa.ForeignKey("academic_slots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("created_by", sa.BigInteger,
                  sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("faculty_id", "block_date", "academic_slot_id",
                            name="uq_faculty_busy"),
    )

    op.create_table(
        "queue_entries",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.BigInteger,
                  sa.ForeignKey("requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("faculty_id", sa.BigInteger,
                  sa.ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.BigInteger,
                  sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("meeting_date", sa.Date, nullable=False),
        sa.Column("academic_slot_id", sa.BigInteger,
                  sa.ForeignKey("academic_slots.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("token_number", sa.Integer, nullable=False),
        sa.Column("access_token_id", sa.BigInteger,
                  sa.ForeignKey("tokens.id", ondelete="SET NULL")),
        sa.Column("priority_class", sa.String(24), nullable=False,
                  server_default=sa.text("'CONFIRMED'")),
        sa.Column("priority_score", sa.Integer, nullable=False,
                  server_default=sa.text("0")),
        sa.Column("state", sa.String(24), nullable=False,
                  server_default=sa.text("'WAITING'")),
        sa.Column("checked_in_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("delay_minutes", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("exchanged_with_id", sa.BigInteger,
                  sa.ForeignKey("queue_entries.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("request_id", name="uq_queue_request"),
        sa.UniqueConstraint("faculty_id", "meeting_date", "academic_slot_id",
                            "token_number", name="uq_queue_token"),
        sa.CheckConstraint(
            "state IN ('WAITING','CHECKED_IN','READY','IN_PROGRESS',"
            "'COMPLETED','NO_SHOW','WITHDRAWN')", name="chk_queue_state"),
    )

    op.execute("""
        INSERT INTO system_settings (setting_key, setting_value, description)
        VALUES
          ('APPOINTMENT_BUFFER_MINUTES', '5', 'Buffer minutes around every meeting.'),
          ('DEFAULT_MEETING_MINUTES', '15', 'Default meeting length used for ETA.'),
          ('QUEUE_BREAK_AFTER', '0', 'Insert a break after N meetings (0 = never).'),
          ('QUEUE_BREAK_MINUTES', '5', 'Length of that break in minutes.')
        ON CONFLICT (setting_key) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM system_settings WHERE setting_key IN
          ('APPOINTMENT_BUFFER_MINUTES','DEFAULT_MEETING_MINUTES',
           'QUEUE_BREAK_AFTER','QUEUE_BREAK_MINUTES');
    """)
    op.drop_table("queue_entries")
    op.drop_table("faculty_busy_blocks")
