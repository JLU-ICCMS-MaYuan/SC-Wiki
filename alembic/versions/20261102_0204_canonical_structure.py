"""#204：规范结构承接来源与派生表示，当前工作稿退出根候选容器。"""
from alembic import op
import sqlalchemy as sa

revision = '20261102_0204'
down_revision = '20261102_0203'
branch_labels = None
depends_on = None


def upgrade():
    from backend.services.form_contract_migration import require_explicit_migration
    from alembic import op as migration_op
    require_explicit_migration(migration_op.get_bind())
    from backend.services.form_contract_migration import prepare_changes, apply_changes
    bind = op.get_bind()
    changes = prepare_changes(bind, structures=True)
    columns = {column['name'] for column in sa.inspect(bind).get_columns('structure_models')}
    if 'metadata_json' not in columns:
        op.add_column('structure_models', sa.Column('metadata_json', sa.JSON(), nullable=True))
    from backend.services.structure_candidates import validate_structure_text, read_atoms, export_representations
    table = sa.Table('structure_models', sa.MetaData(), autoload_with=bind)
    papers = sa.Table('papers', sa.MetaData(), autoload_with=bind)
    rows = bind.execute(sa.select(table).join(papers, sa.and_(
        table.c.paper_id == papers.c.id, table.c.paper_revision == papers.c.content_revision))).mappings().all()
    for row in rows:
        if row['metadata_json'] is None:
            metadata = {'validation': validate_structure_text(row['structure_format'], row['structure_text']),
                        'representations': export_representations(read_atoms(row['structure_format'], row['structure_text']))}
            from backend.ingest.canonical_structure import structure_metadata
            bind.execute(table.update().where(table.c.id == row['id']).values(metadata_json=structure_metadata(metadata)))
    apply_changes(bind, changes)


def downgrade():
    raise RuntimeError('结构来源与派生表示需要迁移前备份恢复，不执行有损回退')
