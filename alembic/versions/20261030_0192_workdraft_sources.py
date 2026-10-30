"""当前工作稿和去重来源目录；不改写存量业务记录。"""
from alembic import op
import sqlalchemy as sa

revision = '20261030_0192'
down_revision = '20261029_0181'
branch_labels = None
depends_on = None
OLD_IDENTITY = "(record_type NOT IN ('predicted_tc','measured_tc')) OR (property_code = 'tc' AND method_code IS NOT NULL)"
NEW_IDENTITY = "(record_type NOT IN ('predicted_tc','measured_tc')) OR (property_code = 'tc' AND (method_code IS NOT NULL OR (record_type = 'predicted_tc' AND (JSON_EXTRACT(payload_json, '$.tc_context_ref.version') = 1 AND JSON_EXTRACT(payload_json, '$.tc_context_ref.group_key') IS NOT NULL AND JSON_EXTRACT(payload_json, '$.tc_context_ref.method_key') IS NOT NULL))))"
OLD_CONDITION = "(record_type <> 'predicted_tc' OR (payload_json IS NOT NULL AND JSON_EXTRACT(payload_json, '$.calculation_conditions') IS NOT NULL AND JSON_EXTRACT(payload_json, '$.experimental_conditions') IS NULL)) AND (record_type <> 'measured_tc' OR (payload_json IS NOT NULL AND JSON_EXTRACT(payload_json, '$.experimental_conditions') IS NOT NULL AND JSON_EXTRACT(payload_json, '$.calculation_conditions') IS NULL))"
NEW_CONDITION = "(record_type <> 'predicted_tc' OR (payload_json IS NOT NULL AND (JSON_EXTRACT(payload_json, '$.calculation_conditions') IS NOT NULL OR (JSON_EXTRACT(payload_json, '$.tc_context_ref.version') = 1 AND JSON_EXTRACT(payload_json, '$.tc_context_ref.group_key') IS NOT NULL AND JSON_EXTRACT(payload_json, '$.tc_context_ref.method_key') IS NOT NULL)) AND JSON_EXTRACT(payload_json, '$.experimental_conditions') IS NULL)) AND (record_type <> 'measured_tc' OR (payload_json IS NOT NULL AND JSON_EXTRACT(payload_json, '$.experimental_conditions') IS NOT NULL AND JSON_EXTRACT(payload_json, '$.calculation_conditions') IS NULL))"

def upgrade():
    with op.batch_alter_table('property_records') as batch:
        batch.drop_constraint('ck_property_records_tc_identity',type_='check')
        batch.create_check_constraint('ck_property_records_tc_identity',NEW_IDENTITY)
        batch.drop_constraint('ck_property_records_condition_type',type_='check')
        batch.create_check_constraint('ck_property_records_condition_type',NEW_CONDITION)
    op.create_table('scientific_source_items',
        sa.Column('id',sa.String(64),primary_key=True),
        sa.Column('namespace',sa.String(128),nullable=False),
        sa.Column('payload',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False,server_default=sa.func.now()))
    op.create_index('ix_scientific_source_items_namespace','scientific_source_items',['namespace'])
    op.create_table('scientific_field_source_uses',
        sa.Column('work_key',sa.String(128),primary_key=True),
        sa.Column('item_key',sa.String(64),primary_key=True),
        sa.Column('source_id',sa.String(64),sa.ForeignKey('scientific_source_items.id',ondelete='RESTRICT'),primary_key=True),
        sa.Column('role',sa.String(16),primary_key=True),
        sa.Column('binding_json',sa.JSON(),nullable=False))
    op.create_index('ix_field_source_use_source','scientific_field_source_uses',['source_id'])
    op.create_table('scientific_work_drafts',
        sa.Column('id',sa.String(64),primary_key=True),
        sa.Column('document_key',sa.String(128),nullable=False),
        sa.Column('target',sa.String(16),nullable=False),
        sa.Column('target_id',sa.String(64),nullable=False),
        sa.Column('owner_id',sa.Integer(),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('write_epoch',sa.String(32),nullable=False),
        sa.Column('revision',sa.BigInteger(),nullable=False),
        sa.Column('body',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False,server_default=sa.func.now()),
        sa.Column('updated_at',sa.DateTime(),nullable=False,server_default=sa.func.now()),
        sa.UniqueConstraint('target','target_id',name='uq_work_draft_target'))
    op.create_index('ix_scientific_work_drafts_document_key','scientific_work_drafts',['document_key'])

def downgrade():
    if op.get_context().as_sql:
        raise RuntimeError('工作稿回退需要在线核对')
    connection=op.get_bind()
    if connection.scalar(sa.text("SELECT COUNT(*) FROM property_records WHERE JSON_EXTRACT(payload_json, '$.tc_context_ref.version') = 1")):
        raise RuntimeError('存在Tc共享引用，拒绝有损回退')
    for name in ('scientific_field_source_uses','scientific_work_drafts','scientific_source_items'):
        if connection.scalar(sa.text('SELECT COUNT(*) FROM '+name)):
            raise RuntimeError('存在工作稿或采用来源，拒绝有损回退')
    with op.batch_alter_table('property_records') as batch:
        batch.drop_constraint('ck_property_records_tc_identity',type_='check')
        batch.create_check_constraint('ck_property_records_tc_identity',OLD_IDENTITY)
        batch.drop_constraint('ck_property_records_condition_type',type_='check')
        batch.create_check_constraint('ck_property_records_condition_type',OLD_CONDITION)
    for name in ('scientific_field_source_uses','scientific_work_drafts','scientific_source_items'):
        op.drop_table(name)
