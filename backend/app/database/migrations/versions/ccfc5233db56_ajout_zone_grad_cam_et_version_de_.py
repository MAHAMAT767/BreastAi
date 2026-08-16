"""Ajout zone Grad-CAM et version de pretraitement

Revision ID: ccfc5233db56
Revises: a828d9d55f61
Create Date: 2026-08-07 14:33:12.413286

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'ccfc5233db56'
down_revision: str | None = 'a828d9d55f61'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('analyses', sa.Column('preprocessing_version', sa.String(length=20), nullable=True))
    op.add_column('analyses', sa.Column('region_x', sa.Integer(), nullable=True))
    op.add_column('analyses', sa.Column('region_y', sa.Integer(), nullable=True))
    op.add_column('analyses', sa.Column('region_width', sa.Integer(), nullable=True))
    op.add_column('analyses', sa.Column('region_height', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('analyses', 'region_height')
    op.drop_column('analyses', 'region_width')
    op.drop_column('analyses', 'region_y')
    op.drop_column('analyses', 'region_x')
    op.drop_column('analyses', 'preprocessing_version')
