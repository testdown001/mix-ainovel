"""character_states.character_id 放开为可空

原本的 NOT NULL 让角色状态在生产上 100% 写入失败：唯一写入方
MemoryLayerService.update_character_state 不接收 character_id，只能从"上一条状态"
继承，而上一条状态又要写成功才存在 —— 首次写必为 NULL，IntegrityError，永远
bootstrap 不了。全部读路径按 character_name 查，从不读 character_id。

Revision ID: b1c2d3e4f5a6
Revises: 3d0894d473c4
Create Date: 2026-07-31 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = '3d0894d473c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('character_states', schema=None) as batch_op:
        batch_op.alter_column(
            'character_id',
            existing_type=sa.BigInteger(),
            nullable=True,
        )


def downgrade() -> None:
    # 回滚前需先清理 character_id IS NULL 的行，否则 NOT NULL 无法恢复。
    op.execute("DELETE FROM character_states WHERE character_id IS NULL")
    with op.batch_alter_table('character_states', schema=None) as batch_op:
        batch_op.alter_column(
            'character_id',
            existing_type=sa.BigInteger(),
            nullable=False,
        )
