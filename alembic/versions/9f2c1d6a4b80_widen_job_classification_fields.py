"""Widen job classification fields.

Revision ID: 9f2c1d6a4b80
Revises: c7ac7ebee24c
Create Date: 2026-10-16 17:48:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "9f2c1d6a4b80"
down_revision: Union[str, Sequence[str], None] = "c7ac7ebee24c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.alter_column(
            "employment_type",
            existing_type=sa.String(length=50),
            type_=sa.String(length=100),
            existing_nullable=True,
        )
        batch.alter_column(
            "experience_level",
            existing_type=sa.String(length=50),
            type_=sa.String(length=100),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.alter_column(
            "experience_level",
            existing_type=sa.String(length=100),
            type_=sa.String(length=50),
            existing_nullable=True,
        )
        batch.alter_column(
            "employment_type",
            existing_type=sa.String(length=100),
            type_=sa.String(length=50),
            existing_nullable=True,
        )
