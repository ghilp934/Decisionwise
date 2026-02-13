"""align_schema_add_missing_constraints_p0a

Revision ID: b705342a947d
Revises: b18c1ac4fa84
Create Date: 2026-02-13 18:29:44.512298

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b705342a947d'
down_revision = 'b18c1ac4fa84'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # P0-A: Add missing unique constraint for idempotency key
    op.create_unique_constraint('uq_runs_tenant_idempotency', 'runs', ['tenant_id', 'idempotency_key'])

    # P0-A: Keep BIGINT for autoincrement IDs (safer for production scale)
    # No type changes needed - DB already has BIGINT, models.py will be updated to match


def downgrade() -> None:
    # P0-A: Remove unique constraint
    op.drop_constraint('uq_runs_tenant_idempotency', 'runs', type_='unique')
