"""drop_redundant_indexes_and_enable_rls

Supabase Finalization Patch:
- Drop redundant indexes (ix_* auto-generated + idx_runs_idem duplicate)
- Enable RLS on all public tables (defense-in-depth, default deny)

Revision ID: d98c8258a72a
Revises: b705342a947d
Create Date: 2026-02-17 09:02:37.471588

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd98c8258a72a'
down_revision = 'b705342a947d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ====================================================================
    # Part 1: Drop redundant indexes (idempotent - IF EXISTS)
    # ====================================================================
    # Redundant: SQLAlchemy auto-generated ix_* indexes (index=True creates these)
    # We keep canonical idx_* indexes defined in __table_args__

    # api_keys: Keep idx_api_keys_tenant, drop auto-generated ix_api_keys_tenant_id
    op.execute("DROP INDEX IF EXISTS public.ix_api_keys_tenant_id;")

    # runs: Keep idx_runs_tenant_created, idx_runs_status_lease
    #       Drop auto-generated ix_runs_tenant_id
    #       Drop idx_runs_idem (redundant with uq_runs_tenant_idempotency unique constraint)
    op.execute("DROP INDEX IF EXISTS public.ix_runs_tenant_id;")
    op.execute("DROP INDEX IF EXISTS public.idx_runs_idem;")

    # tenant_plans: Keep idx_tenant_plans_tenant_status, idx_tenant_plans_effective
    #               Drop auto-generated ix_tenant_plans_tenant_id
    op.execute("DROP INDEX IF EXISTS public.ix_tenant_plans_tenant_id;")

    # tenant_usage_daily: Keep idx_tenant_usage_daily_tenant_date (unique)
    #                     Drop auto-generated ix_tenant_usage_daily_tenant_id
    op.execute("DROP INDEX IF EXISTS public.ix_tenant_usage_daily_tenant_id;")

    # ====================================================================
    # Part 2: Enable RLS on all Decisionproof tables (defense-in-depth)
    # ====================================================================
    # RLS default: DENY (no policies added intentionally)
    # Server-side connections (owner role) bypass RLS by default (not FORCE RLS)
    # This protects against anon/authenticated Supabase roles accessing data

    op.execute("ALTER TABLE public.tenants ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.runs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.plans ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.tenant_plans ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.tenant_usage_daily ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    # ====================================================================
    # Downgrade: Disable RLS (weakens security - not recommended)
    # ====================================================================
    op.execute("ALTER TABLE public.tenant_usage_daily DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.tenant_plans DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.plans DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.runs DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.api_keys DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.tenants DISABLE ROW LEVEL SECURITY;")

    # ====================================================================
    # Downgrade: Recreate dropped indexes (optional - for rollback safety)
    # ====================================================================
    # Note: Recreating these is optional. They are redundant by design.
    # Uncomment if you want full rollback capability:

    # op.execute("CREATE INDEX ix_api_keys_tenant_id ON public.api_keys (tenant_id);")
    # op.execute("CREATE INDEX ix_runs_tenant_id ON public.runs (tenant_id);")
    # op.execute("CREATE INDEX idx_runs_idem ON public.runs (tenant_id, idempotency_key);")
    # op.execute("CREATE INDEX ix_tenant_plans_tenant_id ON public.tenant_plans (tenant_id);")
    # op.execute("CREATE INDEX ix_tenant_usage_daily_tenant_id ON public.tenant_usage_daily (tenant_id);")
