# AIMETA P=线团编织服务_三线团节奏模型|R=Quest_Fire_Constellation分配_偏差检测|NR=不含LLM调用|E=StrandWeaveService|X=internal|A=节奏控制|D=none|S=none|RD=./README.ai
"""
Strand Weave 线团编织服务

实现 Quest / Fire / Constellation 三线编织模型：
- Quest（主线）：目标递进、冲突升级、里程碑
- Fire（热线）：敌人威胁、压力场景、危机
- Constellation（星座线）：世界观补充、配角刻画、反思

核心功能：
1. 三线团分配规划
2. 章节 strand 获取
3. 分布偏差检测与告警
4. 与题材 pacing_config 联动
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class StrandInfo:
    """章节线团信息"""
    strand_type: str  # quest / fire / constellation
    strand_weight: float  # 0.0 - 1.0
    description: str
    writing_focus: str
    emotion_range: str  # "中-高" / "高" / "低-中"


@dataclass
class StrandBalance:
    """线团分布平衡分析"""
    quest_actual: float
    fire_actual: float
    constellation_actual: float
    quest_target: float
    fire_target: float
    constellation_target: float
    is_balanced: bool
    warnings: List[str]


# 线团定义
STRAND_DEFINITIONS = {
    "quest": {
        "name": "Quest（主线）",
        "description": "目标递进、冲突升级、里程碑",
        "emotion_range": "中-高",
        "writing_focus": "聚焦主角目标推进，每章至少一个里程碑事件或冲突升级",
    },
    "fire": {
        "name": "Fire（热线）",
        "description": "敌人威胁、压力场景、危机",
        "emotion_range": "高",
        "writing_focus": "制造高压场景，突出威胁感和紧迫性，短句快节奏",
    },
    "constellation": {
        "name": "Constellation（星座线）",
        "description": "世界观补充、配角刻画、反思",
        "emotion_range": "低-中",
        "writing_focus": "丰富世界观细节，深化配角形象，留出角色反思空间",
    },
}


class StrandWeaveService:
    """三线团编织服务。"""

    def __init__(
        self,
        total_chapters: int,
        quest_ratio: float = 0.60,
        fire_ratio: float = 0.25,
        constellation_ratio: float = 0.15,
        interleave_interval: int = 4,
    ):
        self.total_chapters = max(total_chapters, 1)
        self.quest_ratio = quest_ratio
        self.fire_ratio = fire_ratio
        self.constellation_ratio = constellation_ratio
        self.interleave_interval = max(interleave_interval, 1)
        self._plan: List[StrandInfo] = []

    def plan_strands(self) -> List[StrandInfo]:
        """规划全书的线团分配。"""
        plan: List[StrandInfo] = []

        for chapter in range(1, self.total_chapters + 1):
            progress = chapter / self.total_chapters
            strand_type, weight = self._assign_strand(chapter, progress)
            definition = STRAND_DEFINITIONS[strand_type]

            plan.append(StrandInfo(
                strand_type=strand_type,
                strand_weight=weight,
                description=definition["description"],
                writing_focus=definition["writing_focus"],
                emotion_range=definition["emotion_range"],
            ))

        self._plan = plan
        return plan

    def get_chapter_strand(self, chapter_number: int) -> StrandInfo:
        """获取指定章节的线团信息。"""
        if not self._plan:
            self.plan_strands()

        if chapter_number < 1 or chapter_number > self.total_chapters:
            # 返回默认 Quest
            return StrandInfo(
                strand_type="quest",
                strand_weight=1.0,
                description=STRAND_DEFINITIONS["quest"]["description"],
                writing_focus=STRAND_DEFINITIONS["quest"]["writing_focus"],
                emotion_range=STRAND_DEFINITIONS["quest"]["emotion_range"],
            )

        return self._plan[chapter_number - 1]

    def analyze_balance(
        self,
        completed_strands: Optional[List[str]] = None,
    ) -> StrandBalance:
        """分析已完成章节的线团分布平衡。"""
        if not completed_strands:
            return StrandBalance(
                quest_actual=0, fire_actual=0, constellation_actual=0,
                quest_target=self.quest_ratio,
                fire_target=self.fire_ratio,
                constellation_target=self.constellation_ratio,
                is_balanced=True,
                warnings=[],
            )

        total = len(completed_strands)
        quest_count = sum(1 for s in completed_strands if s == "quest")
        fire_count = sum(1 for s in completed_strands if s == "fire")
        constellation_count = sum(1 for s in completed_strands if s == "constellation")

        quest_actual = quest_count / total
        fire_actual = fire_count / total
        constellation_actual = constellation_count / total

        warnings: List[str] = []
        is_balanced = True

        # 检查偏差
        if quest_actual > self.quest_ratio + 0.20:
            warnings.append(
                f"Quest 线团占比过高（{quest_actual:.0%}，目标 {self.quest_ratio:.0%}），"
                f"建议在后续章节增加 Fire 或 Constellation 线团"
            )
            is_balanced = False

        if fire_actual < self.fire_ratio - 0.15 and total >= 5:
            warnings.append(
                f"Fire 线团占比偏低（{fire_actual:.0%}，目标 {self.fire_ratio:.0%}），"
                f"缺少高压场景可能导致节奏平淡"
            )
            is_balanced = False

        if constellation_actual < 0.05 and total >= 10:
            warnings.append(
                f"Constellation 线团占比过低（{constellation_actual:.0%}），"
                f"世界观和配角刻画不足，建议安排反思/补充章节"
            )
            is_balanced = False

        # 检查连续性
        consecutive_quest = 0
        max_consecutive_quest = 0
        last_fire_idx = -1

        for i, strand in enumerate(completed_strands):
            if strand == "quest":
                consecutive_quest += 1
                max_consecutive_quest = max(max_consecutive_quest, consecutive_quest)
            else:
                consecutive_quest = 0
            if strand == "fire":
                last_fire_idx = i

        if max_consecutive_quest > 5:
            warnings.append(
                f"Quest 线团连续 {max_consecutive_quest} 章，超过建议上限 5 章，"
                f"读者可能产生疲劳感"
            )
            is_balanced = False

        fire_gap = total - 1 - last_fire_idx if last_fire_idx >= 0 else total
        if fire_gap > 10:
            warnings.append(
                f"距离上次 Fire 线团已有 {fire_gap} 章，超过建议间隔 10 章，"
                f"缺少压力场景可能降低紧张感"
            )
            is_balanced = False

        return StrandBalance(
            quest_actual=quest_actual,
            fire_actual=fire_actual,
            constellation_actual=constellation_actual,
            quest_target=self.quest_ratio,
            fire_target=self.fire_ratio,
            constellation_target=self.constellation_ratio,
            is_balanced=is_balanced,
            warnings=warnings,
        )

    def _assign_strand(self, chapter: int, progress: float) -> Tuple[str, float]:
        """为章节分配线团类型和权重。"""
        # 高潮区（75%+）：Quest + Fire 密集交替
        if progress >= 0.90:
            # 结局区：Quest 收束 + Constellation 回归
            cycle = (chapter - 1) % 3
            if cycle == 0:
                return "quest", 0.8
            elif cycle == 1:
                return "constellation", 0.6
            else:
                return "quest", 0.7

        if progress >= 0.75:
            # 高潮区
            if chapter % 2 == 0:
                return "fire", 0.9
            else:
                return "quest", 0.8

        # 中盘（30%-75%）：按间隔交织
        if progress >= 0.30:
            cycle_pos = (chapter - 1) % self.interleave_interval
            if cycle_pos == 0:
                return "fire", 0.7
            elif cycle_pos == self.interleave_interval - 1:
                return "constellation", 0.6
            else:
                return "quest", 0.7

        # 开盘（0-30%）：以 Quest 为主，间插 Constellation 建立世界观
        if chapter <= 2:
            return "quest", 0.8
        if chapter % 4 == 0:
            return "constellation", 0.6
        if chapter % 5 == 0:
            return "fire", 0.5
        return "quest", 0.7

    @staticmethod
    def build_strand_prompt(strand_info: StrandInfo) -> str:
        """将线团信息转化为可注入 prompt 的文本。"""
        definition = STRAND_DEFINITIONS.get(strand_info.strand_type, {})
        name = definition.get("name", strand_info.strand_type)

        lines = [
            f"[线团约束：{name}，权重={strand_info.strand_weight:.0%}]",
            f"- 线团内容：{strand_info.description}",
            f"- 情绪强度范围：{strand_info.emotion_range}",
            f"- 写作要求：{strand_info.writing_focus}",
        ]
        return "\n".join(lines)
