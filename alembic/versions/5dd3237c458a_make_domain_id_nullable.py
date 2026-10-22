"""make domain_id nullable

Revision ID: 5dd3237c458a
Revises: ae63067c55a9
Create Date: 2026-10-22 11:47:02.657123

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5dd3237c458a'
down_revision: Union[str, None] = 'ae63067c55a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('created_campaigns') as batch_op:
        batch_op.alter_column('domain_id',
                   existing_type=sa.INTEGER(),
                   nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('created_campaigns') as batch_op:
        batch_op.alter_column('domain_id',
                   existing_type=sa.INTEGER(),
                   nullable=False)
