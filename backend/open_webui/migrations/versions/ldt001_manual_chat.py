"""Add manual-chat state without modifying historical chat or identity data."""

from alembic import op
import sqlalchemy as sa

revision = 'ldt001'
down_revision = '9f6c2a8d1b43'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'ldt_principal',
        sa.Column('id', sa.Text, primary_key=True),
        sa.Column('kind', sa.Text, nullable=False),
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('preferences', sa.JSON, nullable=False),
        sa.Column('disabled', sa.Boolean, nullable=False),
        sa.Column('merged_into', sa.Text),
        sa.Column('created_at', sa.BigInteger, nullable=False),
    )
    op.create_table(
        'ldt_session',
        sa.Column('token_hash', sa.Text, primary_key=True),
        sa.Column('principal_id', sa.Text, nullable=False, index=True),
        sa.Column('expires_at', sa.BigInteger, nullable=False),
        sa.Column('revoked', sa.Boolean, nullable=False),
    )
    op.create_table(
        'ldt_admin',
        sa.Column('singleton', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Text, nullable=False, unique=True),
        sa.CheckConstraint('singleton = 1'),
    )
    op.create_table(
        'ldt_conversation',
        sa.Column('id', sa.Text, primary_key=True),
        sa.Column('owner_id', sa.Text, nullable=False, index=True),
        sa.Column('current_round_id', sa.Text),
        sa.Column('next_side', sa.Text, nullable=False),
        sa.Column('turn_version', sa.Integer, nullable=False),
        sa.Column('revision', sa.Integer, nullable=False),
        sa.Column('seq', sa.Integer, nullable=False),
        sa.Column('user_read', sa.Integer, nullable=False),
        sa.Column('admin_read', sa.Integer, nullable=False),
        sa.Column('last_message_at', sa.BigInteger, nullable=False, index=True),
        sa.Column('manual_title', sa.Boolean, nullable=False),
        sa.Column('deleted', sa.Boolean, nullable=False),
    )
    op.create_table(
        'ldt_round',
        sa.Column('id', sa.Text, primary_key=True),
        sa.Column('chat_id', sa.Text, nullable=False, index=True),
        sa.Column('message_id', sa.Text, nullable=False),
        sa.Column('sender_side', sa.Text, nullable=False),
        sa.Column('status', sa.Text, nullable=False),
        sa.CheckConstraint("status IN ('pending', 'completed', 'cancelled')"),
    )
    op.create_table(
        'ldt_message',
        sa.Column('id', sa.Text, primary_key=True),
        sa.Column('chat_id', sa.Text, nullable=False, index=True),
        sa.Column('seq', sa.Integer, nullable=False),
        sa.Column('author_id', sa.Text, nullable=False),
        sa.Column('side', sa.Text, nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('attachments', sa.JSON, nullable=False),
        sa.Column('text_version', sa.Integer, nullable=False),
        sa.Column('locked', sa.Boolean, nullable=False),
        sa.Column('cancelled', sa.Boolean, nullable=False),
        sa.Column('created_at', sa.BigInteger, nullable=False),
        sa.UniqueConstraint('chat_id', 'seq'),
    )
    op.create_table(
        'ldt_request',
        sa.Column('actor_id', sa.Text, primary_key=True),
        sa.Column('key', sa.Text, primary_key=True),
        sa.Column('fingerprint', sa.Text, nullable=False),
        sa.Column('chat_id', sa.Text, nullable=False),
        sa.Column('result', sa.JSON, nullable=False),
    )
    op.create_table(
        'ldt_upload',
        sa.Column('id', sa.Text, primary_key=True),
        sa.Column('owner_id', sa.Text, nullable=False, index=True),
        sa.Column('chat_id', sa.Text, index=True),
        sa.Column('message_id', sa.Text),
        sa.Column('expires_at', sa.BigInteger, nullable=False),
        sa.Column('mime', sa.Text, nullable=False),
        sa.Column('size', sa.Integer, nullable=False),
        sa.Column('revoked', sa.Boolean, nullable=False),
    )
    op.create_table(
        'ldt_title_job',
        sa.Column('chat_id', sa.Text, primary_key=True),
        sa.Column('snapshot', sa.Text, nullable=False),
        sa.Column('attempts', sa.Integer, nullable=False),
        sa.Column('due_at', sa.BigInteger, nullable=False),
        sa.Column('done', sa.Boolean, nullable=False),
    )
    op.create_table(
        'ldt_gc',
        sa.Column('file_id', sa.Text, primary_key=True),
        sa.Column('attempts', sa.Integer, nullable=False),
        sa.Column('due_at', sa.BigInteger, nullable=False),
    )


def downgrade():
    raise RuntimeError('Back up and restore to roll back; manual-chat data must not be dropped implicitly.')
