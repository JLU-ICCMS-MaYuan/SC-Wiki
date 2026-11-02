"""#203：合并两个已存在的迁移头，不修改旧迁移。"""
revision = '20261102_0203_merge'
down_revision = ('20261020_0049', '20261101_0198')
branch_labels = None
depends_on = None


def upgrade():
    from backend.services.form_contract_migration import require_explicit_migration
    from alembic import op as migration_op
    require_explicit_migration(migration_op.get_bind())
    pass


def downgrade():
    pass
