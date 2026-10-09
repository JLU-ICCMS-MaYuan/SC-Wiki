"""#125：按账号保存 RAG 完成会话。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20261009_0125"
down_revision = "20261009_0115"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rag_chat_conversations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("source_local_id", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("owner_user_id", "source_local_id", name="uq_rag_chat_local_import"),
    )
    op.create_index("ix_rag_chat_owner_updated", "rag_chat_conversations", ["owner_user_id", "updated_at"])
    op.create_table(
        "rag_chat_turns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.String(32), sa.ForeignKey("rag_chat_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=False),
        sa.Column("citations_json", sa.JSON(), nullable=False),
        sa.Column("display_meta_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("conversation_id", "sequence", name="uq_rag_chat_turn_sequence"),
        sa.UniqueConstraint("conversation_id", "request_id", name="uq_rag_chat_turn_request"),
    )
    op.create_index("ix_rag_chat_turns_conversation_id", "rag_chat_turns", ["conversation_id"])


def downgrade():
    op.drop_index("ix_rag_chat_turns_conversation_id", table_name="rag_chat_turns")
    op.drop_table("rag_chat_turns")
    op.drop_index("ix_rag_chat_owner_updated", table_name="rag_chat_conversations")
    op.drop_table("rag_chat_conversations")
