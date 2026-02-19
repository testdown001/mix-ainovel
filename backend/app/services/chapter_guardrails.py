# AIMETA P=章节护栏_后置一致性检查|R=禁止角色检测_全知视角检测_登场协议检查|NR=不含LLM调用|E=none|X=internal|A=检测_验证|D=re|S=none|RD=./README.ai
"""
ChapterGuardrails: 章节后置一致性检查服务

核心职责：
1. 检测正文中是否出现禁止角色的名字
2. 检测全知视角的 cue 词
3. 检测新角色登场是否符合协议
4. 输出违规列表，供自动修复使用
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass
class Violation:
    """违规记录"""
    type: str  # forbidden_name | omniscient_cue | sudden_familiarity | markdown_marker | trailing_camera
    severity: str  # high | medium | low
    description: str
    position: Optional[int] = None  # 违规位置（字符索引）
    context: Optional[str] = None  # 违规上下文（前后 50 字）


@dataclass
class GuardrailResult:
    """护栏检查结果"""
    passed: bool
    violations: List[Violation] = field(default_factory=list)
    
    def add_violation(self, violation: Violation):
        self.violations.append(violation)
        self.passed = False


class ChapterGuardrails:
    """
    章节护栏检查器。

    检查维度：
    A) ForbiddenNameMention：正文出现 forbidden_characters 中任意名字（高优先级）
    B) OmniscientCue：出现全知视角的 cue 词（中优先级）
    C) SuddenFamiliarity：新角色首次出现前 120 字内没有介绍痕迹（中优先级）
    D) MarkdownMarker：正文包含 Markdown 标签（中优先级）
    E) UnregisteredEntity：出现未注册的实体名称（低优先级）
    F) TrailingCamera：章末出现 POV 角色感知范围外的描写（高优先级）
    """

    # 全知视角 cue 词列表
    OMNISCIENT_CUES = [
        r"与此同时",
        r"另一边",
        r"此时某地",
        r"殊不知",
        r"他并不知道",
        r"她并不知道",
        r"他们并不知道",
        r"如果他知道",
        r"如果她知道",
        r"在他不知道的地方",
        r"在她不知道的地方",
        r"远在.*的.*正在",
        r"而此刻.*却",
    ]

    # 介绍性词汇（用于检测角色登场是否有介绍）
    INTRO_INDICATORS = [
        r"看见",
        r"看到",
        r"注意到",
        r"发现",
        r"出现",
        r"走来",
        r"走进",
        r"站着",
        r"坐着",
        r"一个.*人",
        r"一位",
        r"陌生",
        r"不认识",
        r"第一次见",
        r"从未见过",
        r"身穿",
        r"穿着",
        r"长相",
        r"面容",
        r"身材",
        r"气质",
    ]

    # Markdown 标签（正文禁止）
    MARKDOWN_MARKERS = [
        r"\*\*.+?\*\*",              # 粗体 **text**
        r"^\s*---+\s*$",             # 分隔线 ---
        r"^\s*#{1,6}\s+",            # 标题 # ##
        r"^\s*```",                  # 代码块围栏
        r"^\s*[-*+]\s+\S+",          # 列表项
    ]

    # 滞后镜头检测：POV 角色离开后描写身后画面的模式
    # 分两步检测：1) 先检测"离场动作" 2) 再检测其后的"滞后描写"
    DEPARTURE_CUES = [
        r"转身(?:离开|走|往|朝|向)",
        r"背(?:过身|转身)",
        r"头也不回",
        r"离开了",
        r"走出了",
        r"走远了",
        r"闭上了眼",
        r"失去了意识",
        r"昏了过去",
    ]
    TRAILING_CAMERA_CUES = [
        r"身后[，,]",
        r"在[他她]身后",
        r"在[他她]背后",
        r"[他她]离开后",
        r"[他她]走后",
        r"[他她]走远后",
        r"而[他她](?:已经)?(?:看不到|不知道|没有注意到)",
        r"没有人(?:看到|注意到|发现)",
        r"无人(?:看到|注意到|知道)",
    ]

    def __init__(self):
        self._omniscient_pattern = re.compile(
            "|".join(self.OMNISCIENT_CUES), re.IGNORECASE
        )
        self._intro_pattern = re.compile(
            "|".join(self.INTRO_INDICATORS), re.IGNORECASE
        )
        self._markdown_pattern = re.compile(
            "|".join(self.MARKDOWN_MARKERS), re.IGNORECASE | re.MULTILINE
        )
        self._departure_pattern = re.compile(
            "|".join(self.DEPARTURE_CUES), re.IGNORECASE
        )
        self._trailing_camera_pattern = re.compile(
            "|".join(self.TRAILING_CAMERA_CUES), re.IGNORECASE
        )

    def check(
        self,
        generated_text: str,
        forbidden_characters: List[str],
        allowed_new_characters: Optional[List[str]] = None,
        pov: Optional[str] = None,
        alias_map: Optional[dict] = None,
        omniscient_tolerance: str = "medium",
    ) -> GuardrailResult:
        """
        执行护栏检查。

        Args:
            generated_text: 生成的章节正文
            forbidden_characters: 禁止出现的角色名列表
            allowed_new_characters: 本章允许登场的新角色列表
            pov: 本章视角角色名
            alias_map: 别名→正式名映射表（用于增强角色名匹配）
            omniscient_tolerance: 全知视角容忍度（strict/medium/loose）

        Returns:
            GuardrailResult: 检查结果
        """
        result = GuardrailResult(passed=True)

        # 扩展禁止列表：通过别名映射添加别名
        expanded_forbidden = list(forbidden_characters)
        if alias_map:
            for alias, canonical in alias_map.items():
                if canonical in forbidden_characters and alias not in expanded_forbidden:
                    expanded_forbidden.append(alias)

        # A) 检测禁止角色名
        self._check_forbidden_names(generated_text, expanded_forbidden, result)

        # B) 检测全知视角 cue（根据容忍度调整）
        if omniscient_tolerance != "loose":
            self._check_omniscient_cues(generated_text, result)

        # C) 检测新角色登场协议
        if allowed_new_characters:
            self._check_character_introduction(
                generated_text, allowed_new_characters, result, alias_map=alias_map,
            )

        # D) 检测 Markdown 标签
        self._check_markdown_markers(generated_text, result)

        # F) 检测章末滞后镜头
        self._check_trailing_camera(generated_text, result)

        return result

    def _check_forbidden_names(
        self, text: str, forbidden_characters: List[str], result: GuardrailResult
    ):
        """检测禁止角色名"""
        for name in forbidden_characters:
            if not name:
                continue
            # 使用正则进行精确匹配（避免部分匹配）
            pattern = re.compile(re.escape(name))
            for match in pattern.finditer(text):
                pos = match.start()
                context = self._extract_context(text, pos)
                result.add_violation(
                    Violation(
                        type="forbidden_name",
                        severity="high",
                        description=f"出现了禁止角色「{name}」的名字",
                        position=pos,
                        context=context,
                    )
                )

    def _check_omniscient_cues(self, text: str, result: GuardrailResult):
        """检测全知视角 cue 词"""
        for match in self._omniscient_pattern.finditer(text):
            pos = match.start()
            cue = match.group()
            context = self._extract_context(text, pos)
            result.add_violation(
                Violation(
                    type="omniscient_cue",
                    severity="medium",
                    description=f"出现全知视角 cue 词「{cue}」",
                    position=pos,
                    context=context,
                )
            )

    def _check_character_introduction(
        self, text: str, new_characters: List[str], result: GuardrailResult,
        alias_map: Optional[dict] = None,
    ):
        """检测新角色登场是否有介绍（支持别名匹配）"""
        for name in new_characters:
            if not name:
                continue
            # 构建匹配名称列表：正式名 + 别名
            names_to_check = [name]
            if alias_map:
                for alias, canonical in alias_map.items():
                    if canonical == name and alias != name:
                        names_to_check.append(alias)

            # 找到任一名称的首次出现位置
            first_pos = None
            matched_name = name
            for check_name in names_to_check:
                pattern = re.compile(re.escape(check_name))
                match = pattern.search(text)
                if match and (first_pos is None or match.start() < first_pos):
                    first_pos = match.start()
                    matched_name = check_name

            if first_pos is None:
                continue  # 角色未出现，不算违规

            # 检查前 120 字是否有介绍性词汇
            intro_range = max(0, first_pos - 120)
            intro_text = text[intro_range:first_pos]

            if not self._intro_pattern.search(intro_text):
                context = self._extract_context(text, first_pos)
                result.add_violation(
                    Violation(
                        type="sudden_familiarity",
                        severity="medium",
                        description=f"新角色「{name}」首次出现前缺少介绍性描写"
                            + (f"（以「{matched_name}」出现）" if matched_name != name else ""),
                        position=first_pos,
                        context=context,
                    )
                )

    def _extract_context(self, text: str, pos: int, window: int = 50) -> str:
        """提取违规位置的上下文"""
        start = max(0, pos - window)
        end = min(len(text), pos + window)
        return f"...{text[start:end]}..."

    def _check_markdown_markers(self, text: str, result: GuardrailResult):
        """检测正文中的 Markdown 标签。"""
        for match in self._markdown_pattern.finditer(text):
            pos = match.start()
            marker = match.group().strip()
            context = self._extract_context(text, pos)
            result.add_violation(
                Violation(
                    type="markdown_marker",
                    severity="medium",
                    description=f"正文包含 Markdown 标签「{marker[:20]}」",
                    position=pos,
                    context=context,
                )
            )

    def _check_trailing_camera(self, text: str, result: GuardrailResult):
        """
        检测章末滞后镜头：POV 角色离场后，叙事留在原地描写身后画面。

        检测逻辑：
        1. 取正文最后 500 字作为章末区域
        2. 在章末区域中找"离场动作"（转身离开/走出/闭眼等）
        3. 在离场动作之后找"滞后描写"（身后/他走后/没有人看到等）
        4. 如果两者同时出现且滞后描写在离场动作之后 → 违规
        """
        # 取章末区域
        tail_size = 500
        tail_start = max(0, len(text) - tail_size)
        tail_text = text[tail_start:]

        # 找章末区域中最后一个离场动作
        last_departure = None
        for match in self._departure_pattern.finditer(tail_text):
            last_departure = match

        if last_departure is None:
            return

        # 在离场动作之后找滞后描写
        after_departure = tail_text[last_departure.end():]
        trailing_match = self._trailing_camera_pattern.search(after_departure)

        if trailing_match:
            # 计算在原文中的实际位置
            abs_pos = tail_start + last_departure.end() + trailing_match.start()
            context = self._extract_context(text, abs_pos, window=80)
            result.add_violation(
                Violation(
                    type="trailing_camera",
                    severity="high",
                    description=(
                        f"章末滞后镜头：POV 角色「{last_departure.group()}」后，"
                        f"出现了角色感知范围外的描写「{trailing_match.group()}」"
                    ),
                    position=abs_pos,
                    context=context,
                )
            )

    def format_violations_for_rewrite(self, result: GuardrailResult) -> str:
        """
        将违规列表格式化为可供 rewrite prompt 使用的文本。
        """
        if result.passed:
            return ""
        
        lines = ["检测到以下违规，需要修复："]
        for i, v in enumerate(result.violations, 1):
            lines.append(f"{i}. [{v.severity.upper()}] {v.description}")
            if v.context:
                lines.append(f"   上下文：{v.context}")
        return "\n".join(lines)

    def apply_local_patches(self, text: str, result: GuardrailResult) -> str:
        """
        对常见违规执行本地最小修补，优先避免整章重写。
        """
        if result.passed or not text:
            return text

        patched = text
        stripped_markdown = False
        trimmed_tail = False

        for violation in result.violations:
            if violation.type == "forbidden_name":
                forbidden_name = self._extract_quoted_token(violation.description)
                if forbidden_name:
                    patched = re.sub(re.escape(forbidden_name), "那人", patched)
            elif violation.type == "omniscient_cue":
                cue = self._extract_quoted_token(violation.description)
                if cue:
                    patched = patched.replace(cue, "")
            elif violation.type == "sudden_familiarity":
                role_name = self._extract_quoted_token(violation.description)
                if role_name:
                    first_pos = patched.find(role_name)
                    if first_pos >= 0:
                        patched = f"{patched[:first_pos]}一个陌生人{patched[first_pos:]}"
            elif violation.type == "markdown_marker" and not stripped_markdown:
                patched = self._strip_markdown_markers(patched)
                stripped_markdown = True
            elif (
                violation.type == "trailing_camera"
                and not trimmed_tail
                and violation.position is not None
            ):
                if 0 < violation.position < len(patched):
                    patched = patched[:violation.position].rstrip()
                    trimmed_tail = True

        return patched

    @staticmethod
    def _extract_quoted_token(description: str) -> Optional[str]:
        if not description:
            return None
        match = re.search(r"「(.+?)」", description)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _strip_markdown_markers(text: str) -> str:
        cleaned = text
        cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
        cleaned = re.sub(r"^\s*#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^\s*```.*$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^\s*---+\s*$", "", cleaned, flags=re.MULTILINE)
        return cleaned


default_guardrails = ChapterGuardrails()
