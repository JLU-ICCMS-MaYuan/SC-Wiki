"""取消结构优化独立详情，仅处理当前工作稿，不改原文及不可变交接快照。"""
from alembic import op
import sqlalchemy as sa

revision = '20261101_0198'
down_revision = '20261030_0192'
branch_labels = None
depends_on = None


def clean(value):
    if isinstance(value, list):
        return [clean(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {key: ('unknown' if key == 'structure_optimization' and item == 'anharmonic_quantum' else clean(item))
            for key, item in value.items() if key != 'structure_optimization_details'
            and not key.startswith('structure_optimization_details.')}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'material_states' in inspector.get_table_names():
        if any(c['name'] == 'structure_optimization_details' for c in inspector.get_columns('material_states')):
            with op.batch_alter_table('material_states') as batch:
                batch.drop_column('structure_optimization_details')
        bind.execute(sa.text("UPDATE material_states SET structure_optimization='unknown' WHERE structure_optimization='anharmonic_quantum'"))
    for name, columns in [('scientific_work_drafts', ['body']), ('scientific_upload_drafts', ['draft', 'state']),
                          ('paper_revision_drafts', ['draft']), ('scientific_review_drafts', ['draft'])]:
        if name not in inspector.get_table_names():
            continue
        table = sa.Table(name, sa.MetaData(), autoload_with=bind)
        keys = list(table.primary_key.columns)
        for column in columns:
            if column not in table.c:
                continue
            for row in bind.execute(sa.select(*keys, table.c[column])).mappings():
                before = row[column]
                if before is None:
                    continue
                after = clean(before)
                if after != before:
                    bind.execute(table.update().where(sa.and_(*(key == row[key.name] for key in keys))).values({column: after}))


def downgrade():
    raise RuntimeError('已取消的结构优化详情不能凭空恢复；请使用迁移前备份回滚')
