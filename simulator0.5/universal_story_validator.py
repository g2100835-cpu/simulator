"""
通用常识与逻辑检测器 v2.0
==========================

独立于任何社会理论的、纯常识和逻辑层面的判断标准。
适用于任何虚构人生故事的质量检测，不依赖特定社会结构知识。

检测维度（共11个）：
  L - 逻辑一致性 (Logic Consistency)
  T - 时间现实性 (Temporal Plausibility)
  P - 心理常识性 (Psychological Common Sense)
  R - 资源常识性 (Resource Common Sense)
  N - 叙事常识性 (Narrative Common Sense)
  G - 地理空间常识性 (Geographic/Spatial Common Sense)
  H - 生理健康常识性 (Biological/Health Common Sense)
  C - 人物关系连续性 (Character Relationship Continuity)
  E - 事件序列逻辑性 (Event Sequence Logic)
  K - 知识与文化常识性 (Knowledge & Cultural Common Sense)
  D - 故事节奏与密度 (Story Pacing & Density)

严重程度：
  FATAL   - 致命，故事不可信，必须修改
  SERIOUS - 严重，故事可信度受损，建议修改
  MINOR   - 轻微，故事略显生硬，可优化
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


# =====================================================================
# 基础数据结构
# =====================================================================

class Severity(Enum):
    FATAL = "FATAL"
    SERIOUS = "SERIOUS"
    MINOR = "MINOR"


@dataclass
class Issue:
    code: str
    severity: Severity
    message: str
    event_index: Optional[int] = None
    character_id: Optional[str] = None
    suggestion: Optional[str] = None
    # 附加上下文：方便自动修复系统定位问题
    context: Optional[Dict[str, Any]] = None


@dataclass
class DetectionResult:
    issues: List[Issue] = field(default_factory=list)

    @property
    def fatal_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.FATAL)

    @property
    def serious_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.SERIOUS)

    @property
    def minor_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.MINOR)

    @property
    def passed(self) -> bool:
        return self.fatal_count == 0

    def issues_by_dimension(self) -> Dict[str, List[Issue]]:
        """按维度分组"""
        groups: Dict[str, List[Issue]] = {}
        for issue in self.issues:
            dim = issue.code.split("-")[0]  # 如 "L1" → "L1"
            dim_letter = dim[0]             # → "L"
            groups.setdefault(dim_letter, []).append(issue)
        return groups

    def report(self) -> str:
        lines = [
            "=" * 60,
            "【通用检测 v2.0】人生故事常识与逻辑检测报告",
            "=" * 60,
            f"",
            f"总问题数：{len(self.issues)}",
            f"  致命(FATAL)：{self.fatal_count}",
            f"  严重(SERIOUS)：{self.serious_count}",
            f"  轻微(MINOR)：{self.minor_count}",
            f"",
            f"总体判定：{'通过' if self.passed else '不通过（存在致命问题）'}",
            f"",
        ]

        # 按维度分组输出
        by_dim = self.issues_by_dimension()
        dim_names = {
            "L": "逻辑一致性", "T": "时间现实性", "P": "心理常识性",
            "R": "资源常识性", "N": "叙事常识性", "G": "地理空间常识性",
            "H": "生理健康常识性", "C": "人物关系连续性", "E": "事件序列逻辑性",
            "K": "知识与文化常识性", "D": "故事节奏与密度",
        }

        for dim_letter in ["L", "T", "P", "R", "N", "G", "H", "C", "E", "K", "D"]:
            if dim_letter in by_dim:
                dim_name = dim_names.get(dim_letter, dim_letter)
                issues = sorted(by_dim[dim_letter], key=lambda x: x.code)
                lines.append(f"--- {dim_letter}. {dim_name} ({len(issues)}个问题) ---")
                for issue in issues:
                    tag = {"FATAL": "🔴", "SERIOUS": "🟡", "MINOR": "🟢"}[issue.severity.value]
                    loc = f"[事件{issue.event_index}]" if issue.event_index is not None else ""
                    lines.append(f"  {tag} {issue.code} {loc} {issue.message}")
                    if issue.suggestion:
                        lines.append(f"     └─ 建议：{issue.suggestion}")
                lines.append("")

        if not self.issues:
            lines.append("✅ 未发现明显常识或逻辑问题")

        return "\n".join(lines)


# =====================================================================
# 人物与事件数据模型
# =====================================================================

@dataclass
class Character:
    id: str
    name: str
    birth_year: int
    death_year: Optional[int] = None
    gender: str = ""
    attributes: Dict[str, float] = field(default_factory=dict)
    # 可选：人物已知技能列表（用于知识/技能合理性检测）
    skills: List[str] = field(default_factory=list)


@dataclass
class Relationship:
    """人物关系"""
    character_id_a: str
    character_id_b: str
    relation_type: str  # "父亲", "配偶", "朋友", "同事" 等
    start_year: int
    end_year: Optional[int] = None  # 关系结束年份（死亡/离婚/失联）
    end_reason: str = ""  # 结束原因


@dataclass
class LifeEvent:
    index: int
    year: int
    age: int
    character_id: str
    event_type: str
    tags: List[str] = field(default_factory=list)
    description: str = ""
    causes: List[int] = field(default_factory=list)
    attribute_changes: Dict[str, float] = field(default_factory=dict)
    location: str = ""
    # v2.0 新增字段
    season: str = ""              # "春/夏/秋/冬"（可选，用于季节检测）
    duration_days: int = 0        # 事件持续天数（可选，用于间隔检测）
    involved_characters: List[str] = field(default_factory=list)  # 涉及的其他人物ID
    skill_required: List[str] = field(default_factory=list)       # 事件需要的技能（可选）


@dataclass
class LifeStory:
    character: Character
    events: List[LifeEvent] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)
    # v2.0 新增：已知其他人物列表（用于关系检测）
    other_characters: List[Character] = field(default_factory=list)

    def get_event(self, index: int) -> Optional[LifeEvent]:
        for e in self.events:
            if e.index == index:
                return e
        return None

    def get_character(self, character_id: str) -> Optional[Character]:
        if self.character.id == character_id:
            return self.character
        for c in self.other_characters:
            if c.id == character_id:
                return c
        return None

    def events_between(self, start_year: int, end_year: int) -> List[LifeEvent]:
        return [e for e in self.events if start_year <= e.year <= end_year]

    def events_at_age(self, age: int) -> List[LifeEvent]:
        return [e for e in self.events if e.age == age]

    def relationship_at(self, character_id: str, year: int) -> List[Relationship]:
        """查询某年份仍有效的关系"""
        return [
            r for r in self.relationships
            if (r.character_id_a == character_id or r.character_id_b == character_id)
            and r.start_year <= year
            and (r.end_year is None or r.end_year >= year)
        ]


# =====================================================================
# 维度一：逻辑一致性（Logic Consistency）
# =====================================================================

class LogicCommonSenseDetector:
    """
    通用逻辑一致性检测

    检测项：
      L1-001 - 因果时间线颠倒（原因发生在结果之后）
      L1-002 - 人物死亡后仍出现事件
      L1-003 - 属性自我矛盾（前后描述不一致）
      L1-004 - 循环因果（A导致B，B又导致A）
      L2-001 - 因果重量不匹配（小因大果 / 大因小果）
      L2-002 - 无因之果（重大事件缺乏触发事件）
      L3-001 - 连续低概率事件（概率异常累积）
      L3-002 - 全知视角泄露（人物不应知道的信息）
    """

    CAUSE_WEIGHT = {
        "死亡（直系亲属）": 5, "死亡（本人）": 5, "严重疾病": 4,
        "重伤": 4, "天灾": 4, "战争": 5, "饥荒": 5,
        "失业": 3, "失学": 3, "离婚": 3, "结婚": 3, "生子": 3,
        "获奖": 2, "升职": 2, "批评": 1, "日常摩擦": 1, "偶遇": 1, "天气": 1,
    }

    EFFECT_WEIGHT = {
        "彻底改变职业": 4, "跨省迁移": 4, "自杀": 5,
        "信仰彻底转变": 3, "重大经济变化": 3, "彻底改变性格": 4,
        "与所有亲人断绝关系": 4, "离婚": 3, "结婚": 3,
        "日常决定": 1, "情绪波动": 1,
    }

    LOW_PROB_EVENTS = {
        "获巨额遗产": 0.01, "被富豪收养": 0.005, "创业成功（首次）": 0.03,
        "中大奖": 0.001, "遇险生还（极端）": 0.02, "被贵人一眼看中": 0.02,
    }

    # v2.0: 全知视角泄露关键词（人物不应知道的事）
    OMNISCIENCE_INDICATORS = [
        "他不知道的是", "她并不知情，但实际上", "此时远方",
        "他不可能知道", "她无从得知，然而",
    ]

    def __init__(self):
        self.issues: List[Issue] = []

    def detect(self, story: LifeStory) -> DetectionResult:
        self.issues = []
        self._check_timeline_contradiction(story)
        self._check_state_contradiction(story)
        self._check_circular_causality(story)
        self._check_causal_adequacy(story)
        self._check_probability_anomaly(story)
        self._check_omniscience_leak(story)
        return DetectionResult(issues=self.issues)

    def _check_timeline_contradiction(self, story: LifeStory):
        for e in story.events:
            for cause_idx in e.causes:
                cause_event = story.get_event(cause_idx)
                if cause_event is None:
                    self.issues.append(Issue(
                        code="L1-001", severity=Severity.FATAL,
                        message=f"事件#{e.index}的cause指向不存在的事件#{cause_idx}",
                        event_index=e.index,
                        suggestion="检查causes字段，移除不存在的事件索引"
                    ))
                    continue
                if cause_event.year > e.year:
                    self.issues.append(Issue(
                        code="L1-001", severity=Severity.FATAL,
                        message=f"事件#{e.index}({e.year}年：{e.event_type})的原因事件"
                                f"#{cause_idx}({cause_event.year}年)发生在其后",
                        event_index=e.index,
                        suggestion="检查并修正事件年份，或调整causes字段"
                    ))

    def _check_state_contradiction(self, story: LifeStory):
        death_event = next((e for e in story.events if e.event_type == "死亡"), None)
        if not death_event:
            return
        for e in story.events:
            if e.index <= death_event.index:
                continue
            if e.event_type in ("死亡追忆", "身后事", "遗产处理"):
                continue
            self.issues.append(Issue(
                code="L1-002", severity=Severity.FATAL,
                message=f"人物在事件#{death_event.index}({death_event.year}年死亡)之后，"
                        f"仍发生了事件#{e.index}({e.year}年：{e.event_type})",
                event_index=e.index,
                suggestion="检查死亡事件的时间位置，或将后续事件标记为'身后事'"
            ))

    def _check_circular_causality(self, story: LifeStory):
        """L1-004：检测循环因果（A导致B，B又标记A为原因）"""
        for e in story.events:
            for cause_idx in e.causes:
                cause_event = story.get_event(cause_idx)
                if cause_event and e.index in cause_event.causes:
                    self.issues.append(Issue(
                        code="L1-004", severity=Severity.FATAL,
                        message=f"事件#{e.index}与事件#{cause_idx}形成循环因果："
                                f"互为对方的原因",
                        event_index=e.index,
                        suggestion="打破循环：确定哪个事件先发生，移除反向的causes引用"
                    ))

    def _check_causal_adequacy(self, story: LifeStory):
        for e in story.events:
            max_cause_weight = 0
            for cause_idx in e.causes:
                cause_event = story.get_event(cause_idx)
                if cause_event:
                    weight = self._estimate_weight(
                        cause_event.event_type + " " + cause_event.description,
                        self.CAUSE_WEIGHT
                    )
                    max_cause_weight = max(max_cause_weight, weight)

            if max_cause_weight == 0:
                nearby = [ev for ev in story.events
                          if ev != e and abs(ev.year - e.year) <= 2]
                for ev in nearby:
                    weight = self._estimate_weight(
                        ev.event_type + " " + ev.description, self.CAUSE_WEIGHT)
                    max_cause_weight = max(max_cause_weight, weight)

            effect_weight = self._estimate_weight(
                e.event_type + " " + e.description, self.EFFECT_WEIGHT)

            if effect_weight >= 3 and max_cause_weight == 0:
                self.issues.append(Issue(
                    code="L2-002", severity=Severity.SERIOUS,
                    message=f"事件#{e.index}({e.year}年：{e.event_type})是重大转折，"
                            f"但缺乏任何前置触发事件",
                    event_index=e.index,
                    suggestion="增加触发事件（如家庭变故、关键人物出现、突发事件等）"
                ))
            elif effect_weight > max_cause_weight + 1 and max_cause_weight > 0:
                self.issues.append(Issue(
                    code="L2-001", severity=Severity.SERIOUS,
                    message=f"事件#{e.index}({e.year}年：{e.event_type})的效果重量({effect_weight})"
                            f"显著超过原因重量({max_cause_weight})",
                    event_index=e.index,
                    suggestion="增加前置事件的严重性，或降低此事件的反转幅度"
                ))

    def _estimate_weight(self, text: str, weight_map: Dict[str, int]) -> int:
        max_weight = 0
        for key, weight in weight_map.items():
            if key in text:
                max_weight = max(max_weight, weight)
        return max_weight

    def _check_probability_anomaly(self, story: LifeStory):
        consecutive_low_prob = 0
        low_prob_keys = set(self.LOW_PROB_EVENTS.keys())
        for e in story.events:
            event_text = e.event_type + " " + e.description
            is_low_prob = any(k in event_text for k in low_prob_keys)
            if is_low_prob:
                consecutive_low_prob += 1
            else:
                consecutive_low_prob = 0
            if consecutive_low_prob >= 3:
                self.issues.append(Issue(
                    code="L3-001", severity=Severity.SERIOUS,
                    message=f"事件#{e.index}之前已连续发生{consecutive_low_prob}个低概率事件，"
                            f"累积概率极低",
                    event_index=e.index,
                    suggestion="在连续好运/厄运之间插入平淡事件，或为主角提供特殊性解释"
                ))
                consecutive_low_prob = 0

    def _check_omniscience_leak(self, story: LifeStory):
        """L3-002：检测全知视角泄露（人物不应知道的信息被当作已知）"""
        for e in story.events:
            for indicator in self.OMNISCIENCE_INDICATORS:
                if indicator in e.description:
                    self.issues.append(Issue(
                        code="L3-002", severity=Severity.SERIOUS,
                        message=f"事件#{e.index}({e.year}年)叙述中出现了全知视角泄露："
                                f"'{indicator}'，暗示人物知道不应知道的信息",
                        event_index=e.index,
                        suggestion="改为人物视角的限制性叙述，或增加信息获取的途径说明"
                    ))


# =====================================================================
# 维度二：时间现实性（Temporal Plausibility）
# =====================================================================

class TemporalCommonSenseDetector:
    """
    通用时间现实性检测

    检测项：
      T1-001 - 事件发生在生物上不可能的年龄段
      T1-002 - 事件间隔过短（变化需要最低时间积累）
      T1-003 - 人物年龄计算错误
      T1-004 - 时间线大段空白
      T1-005 - 季节/时令矛盾
      T1-006 - 同一日期多个冲突事件
    """

    BIOLOGICAL_AGE_CONSTRAINTS = [
        ("出生", 0, 0, Severity.FATAL),
        ("走路", 1, 3, Severity.MINOR),
        ("说话", 1, 4, Severity.MINOR),
        ("入学", 5, 10, Severity.MINOR),
        ("青春期", 10, 20, Severity.MINOR),
        ("初恋", 10, 25, Severity.MINOR),
        ("结婚", 16, 80, Severity.SERIOUS),
        ("生子", 14, 55, Severity.SERIOUS),
        ("生子（首次）", 16, 45, Severity.SERIOUS),
        ("当兵", 16, 35, Severity.MINOR),
        ("退休", 50, 80, Severity.MINOR),
        ("死亡（自然）", 0, 120, Severity.MINOR),
        ("自杀", 8, 120, Severity.MINOR),
        ("创业", 16, 75, Severity.MINOR),
        ("首次独立居住", 14, 50, Severity.MINOR),
    ]

    MIN_INTERVALS = {
        ("结婚", "生子"): 270,
        ("生病", "康复"): 14,
        ("重伤", "康复"): 180,
        ("入学", "毕业"): 180,
        ("入职", "晋升"): 180,
        ("文盲", "识字"): 90,
        ("开始学艺", "出师"): 365,
        ("结婚", "离婚"): 30,
        ("移民", "完全适应"): 365,
        ("怀孕", "生子"): 240,
        ("骨折", "康复"): 90,
        ("入职", "辞职"): 30,
        ("出生", "走路"): 300,
    }

    # 季节-活动约束（月份范围：3-5春，6-8夏，9-11秋，12-2冬）
    SEASON_CONSTRAINTS = {
        "春耕": ("春", None, Severity.MINOR),
        "秋收": ("秋", None, Severity.MINOR),
        "夏收": ("夏", None, Severity.MINOR),
        "播种": ("春", None, Severity.MINOR),
        "洪水": ("夏", None, Severity.MINOR),
        "雪灾": ("冬", None, Severity.SERIOUS),
        "台风": ("夏", "秋", Severity.MINOR),
        "高考": ("夏", None, Severity.MINOR),
        "春节": ("冬", None, Severity.SERIOUS),
    }

    def __init__(self):
        self.issues: List[Issue] = []

    def detect(self, story: LifeStory) -> DetectionResult:
        self.issues = []
        self._check_biological_age(story)
        self._check_age_calculation(story)
        self._check_event_intervals(story)
        self._check_timeline_gaps(story)
        self._check_season_consistency(story)
        self._check_same_date_conflicts(story)
        return DetectionResult(issues=self.issues)

    def _check_biological_age(self, story: LifeStory):
        for e in story.events:
            age = e.age
            if age < 0:
                continue
            for (kw, min_a, max_a, sev) in self.BIOLOGICAL_AGE_CONSTRAINTS:
                if kw in e.event_type or kw in e.description:
                    if age < min_a:
                        self.issues.append(Issue(
                            code="T1-001", severity=sev,
                            message=f"事件#{e.index}(年龄{age}岁：{e.event_type})"
                                    f"低于最低合理年龄({min_a}岁)",
                            event_index=e.index,
                            suggestion=f"将此事件移至{min_a}岁之后，或提供特殊解释"
                        ))
                    elif age > max_a and sev == Severity.SERIOUS:
                        self.issues.append(Issue(
                            code="T1-001", severity=sev,
                            message=f"事件#{e.index}(年龄{age}岁：{e.event_type})"
                                    f"超出最高合理年龄({max_a}岁)",
                            event_index=e.index,
                            suggestion="检查年龄计算是否正确，或提供特殊解释"
                        ))

    def _check_age_calculation(self, story: LifeStory):
        birth_year = story.character.birth_year
        for e in story.events:
            expected_age = e.year - birth_year
            if e.age >= 0 and abs(e.age - expected_age) > 1:
                self.issues.append(Issue(
                    code="T1-003", severity=Severity.SERIOUS,
                    message=f"事件#{e.index}({e.year}年)记录年龄{e.age}岁，"
                            f"但按出生年份{birth_year}计算应为{expected_age}岁",
                    event_index=e.index,
                    suggestion="统一年龄计算方式"
                ))

    def _check_event_intervals(self, story: LifeStory):
        sorted_events = sorted(story.events, key=lambda e: (e.year, e.index))
        for i in range(1, len(sorted_events)):
            prev = sorted_events[i - 1]
            curr = sorted_events[i]
            interval_days = (date(curr.year, 1, 1) - date(prev.year, 1, 1)).days
            for (start_kw, end_kw), min_days in self.MIN_INTERVALS.items():
                if (start_kw in prev.event_type or start_kw in prev.description) and \
                   (end_kw in curr.event_type or end_kw in curr.description):
                    if 0 < interval_days < min_days:
                        self.issues.append(Issue(
                            code="T1-002", severity=Severity.SERIOUS,
                            message=f"从'{prev.event_type}'({prev.year}年)到"
                                    f"'{curr.event_type}'({curr.year}年)间隔仅"
                                    f"{interval_days // 30}个月，不足以完成此变化",
                            event_index=curr.index,
                            suggestion=f"增加间隔至至少{min_days // 30}个月"
                        ))

    def _check_timeline_gaps(self, story: LifeStory):
        if len(story.events) < 3:
            return
        sorted_events = sorted(story.events, key=lambda e: e.year)
        for i in range(1, len(sorted_events)):
            prev = sorted_events[i - 1]
            curr = sorted_events[i]
            gap_years = curr.year - prev.year
            avg_age = (prev.age + curr.age) / 2
            # 成年后间隔>10年可疑；未成年间隔>5年可疑
            threshold = 10 if avg_age >= 18 else 5
            if gap_years > threshold:
                self.issues.append(Issue(
                    code="T1-004", severity=Severity.MINOR,
                    message=f"事件#{prev.index}({prev.year}年)与"
                            f"事件#{curr.index}({curr.year}年)间隔{gap_years}年，"
                            f"时间线有较大空白",
                    event_index=curr.index,
                    suggestion="考虑增加此期间的重要事件"
                ))

    def _check_season_consistency(self, story: LifeStory):
        """T1-005：检测季节/时令矛盾"""
        for e in story.events:
            if not e.season:
                continue
            for kw, (req_season, alt_season, sev) in self.SEASON_CONSTRAINTS.items():
                if kw in e.event_type or kw in e.description:
                    if e.season != req_season and (alt_season is None or e.season != alt_season):
                        self.issues.append(Issue(
                            code="T1-005", severity=sev,
                            message=f"事件#{e.index}({e.year}年：{e.event_type})标记为"
                                    f"'{e.season}'季，但'{kw}'通常发生在{req_season}季"
                                    + (f"或{alt_season}季" if alt_season else ""),
                            event_index=e.index,
                            suggestion=f"将季节改为{req_season}季"
                                        + (f"或{alt_season}季" if alt_season else "")
                        ))

    def _check_same_date_conflicts(self, story: LifeStory):
        """T1-006：同一日期多个冲突事件（同一年份、互斥的事件）"""
        from collections import defaultdict
        events_by_year = defaultdict(list)
        for e in story.events:
            events_by_year[e.year].append(e)

        mutually_exclusive = [
            ("入学", "退休"),
            ("结婚", "出家"),
            ("出生", "死亡"),
            ("入职", "失业"),  # 同年入职又失业需要解释
        ]

        for year, events in events_by_year.items():
            event_types = [e.event_type for e in events]
            for type_a, type_b in mutually_exclusive:
                if type_a in event_types and type_b in event_types:
                    if type_a == "入职" and type_b == "失业":
                        # 同年入职又失业：轻微问题，可能但需要解释
                        self.issues.append(Issue(
                            code="T1-006", severity=Severity.MINOR,
                            message=f"{year}年同时出现'入职'和'失业'，需要解释",
                            suggestion="说明是短暂就业或试工期被辞退"
                        ))
                    else:
                        self.issues.append(Issue(
                            code="T1-006", severity=Severity.SERIOUS,
                            message=f"{year}年同时出现'{type_a}'和'{type_b}'，互斥事件",
                            suggestion="检查事件时间是否准确"
                        ))


# =====================================================================
# 维度三：心理常识性（Psychological Common Sense）
# =====================================================================

class PsychologicalCommonSenseDetector:
    """
    通用心理常识性检测

    检测项：
      P1-001 - 性格/特质剧烈变化无充分触发
      P1-002 - 人物行为与已有性格设定持续矛盾
      P1-003 - 反应模式过于单一（对不同事件始终相同反应）
      P2-001 - 极端事件无相应情绪反应描写
      P2-002 - 人物动机缺失（行为无理由）
      P2-003 - 创伤无持续性影响
      P3-001 - 完全无选择的人生（过度决定）
      P3-002 - 人物对同一事件反复做出相同决定但期待不同结果
    """

    UNIVERSAL_EMOTION_INTENSITY = {
        "本人死亡": 10, "直系亲属死亡": 9, "本人重伤/重病": 8,
        "子女重伤/重病": 8, "配偶死亡": 8, "失业（唯一收入）": 7,
        "离婚": 6, "严重财产损失": 6, "结婚": 5, "生子": 5,
        "获奖/被认可": 4, "与朋友争吵": 3, "日常挫折": 2,
    }

    TRAUMA_KEYWORDS = [
        "死亡", "丧", "重伤", "重病", "性侵", "暴力", "战争",
        "灾", "破产", "入狱", "绑架", "车祸", "失明", "瘫痪",
    ]

    def __init__(self):
        self.issues: List[Issue] = []

    def detect(self, story: LifeStory) -> DetectionResult:
        self.issues = []
        self._check_trait_continuity(story)
        self._check_emotion_adequacy(story)
        self._check_motivation_adequacy(story)
        self._check_trauma_persistence(story)
        self._check_reaction_diversity(story)
        self._check_repeated_failed_choices(story)
        return DetectionResult(issues=self.issues)

    def _check_trait_continuity(self, story: LifeStory):
        init_attrs = story.character.attributes
        prev_attrs = dict(init_attrs)
        for e in story.events:
            for attr_name, change in e.attribute_changes.items():
                prev_val = prev_attrs.get(attr_name, 0)
                new_val = prev_val + change
                if abs(change) > 40:
                    is_extreme = any(
                        kw in e.event_type or kw in e.description
                        for kw in ["死亡", "重伤", "瘫痪", "破产", "入狱", "战争", "天灾"]
                    )
                    if not is_extreme:
                        self.issues.append(Issue(
                            code="P1-001", severity=Severity.SERIOUS,
                            message=f"事件#{e.index}({e.year}年：{e.event_type})导致"
                                    f"属性'{attr_name}'剧烈变化({prev_val}→{new_val})，"
                                    f"变化幅度{abs(change)}分，但事件强度不足以支撑",
                            event_index=e.index,
                            suggestion="减小单次属性变化幅度，或增加过渡事件"
                        ))
                prev_attrs[attr_name] = new_val

    def _check_emotion_adequacy(self, story: LifeStory):
        for e in story.events:
            expected_intensity = 0
            matched_key = ""
            for key, intensity in self.UNIVERSAL_EMOTION_INTENSITY.items():
                if key in e.event_type or key in e.description:
                    if intensity > expected_intensity:
                        expected_intensity = intensity
                        matched_key = key
            if expected_intensity >= 6:
                has_emotion = any(
                    kw in e.description for kw in [
                        "难过", "痛苦", "悲伤", "哭泣", "绝望", "愤怒", "暴怒",
                        "震惊", "恐惧", "害怕", "焦虑", "担心", "高兴", "激动",
                        "喜悦", "兴奋", "失落", "沮丧", "心如死灰", "不知所措",
                        "无法接受", "一夜白头", "沉默", "发呆", "失眠", "噩梦",
                    ]
                )
                if not has_emotion:
                    self.issues.append(Issue(
                        code="P2-001", severity=Severity.SERIOUS,
                        message=f"事件#{e.index}({e.year}年：{e.event_type})"
                                f"涉及'{matched_key}'，预期情绪强度高({expected_intensity}/10)，"
                                f"但叙述中缺乏情绪反应描写",
                        event_index=e.index,
                        suggestion="增加人物在此事件中的情绪反应和行为变化描写"
                    ))

    def _check_motivation_adequacy(self, story: LifeStory):
        major_decision_keywords = ["决定", "选择", "毅然", "突然", "从此"]
        for e in story.events:
            is_major = any(kw in e.description for kw in major_decision_keywords)
            if not is_major:
                continue
            has_motivation = any(
                kw in e.description for kw in [
                    "因为", "由于", "为了", "希望", "想要", "不想", "害怕",
                    "觉得", "认为", "听说", "看到", "被", "受到", "经历",
                ]
            )
            if not has_motivation and not e.causes:
                self.issues.append(Issue(
                    code="P2-002", severity=Severity.MINOR,
                    message=f"事件#{e.index}({e.year}年：{e.event_type})中"
                            f"人物做了重大决定，但缺乏动机说明",
                    event_index=e.index,
                    suggestion="在叙述中增加'因为...所以...'的动机说明"
                ))

    def _check_trauma_persistence(self, story: LifeStory):
        """P2-003：检测创伤是否有持续性影响"""
        trauma_events = []
        for e in story.events:
            if any(kw in e.event_type or kw in e.description for kw in self.TRAUMA_KEYWORDS):
                trauma_events.append(e)

        for trauma in trauma_events:
            # 检查此后3年内是否有"创伤影响"的描写
            later_events = [ev for ev in story.events
                            if trauma.year < ev.year <= trauma.year + 3]
            has_lasting_effect = any(
                any(kw in ev.description for kw in [
                    "阴影", "梦", "怕", "不敢", "回避", "想起", "触景",
                    "失眠", "抑郁", "焦虑", "恍惚", "闪回", "回避",
                    "后遗症", "创伤", "影响", "至今",
                ])
                for ev in later_events
            )
            # 只对最严重的创伤检查
            trauma_text = trauma.event_type + trauma.description
            is_severe = any(kw in trauma_text for kw in
                            ["死亡", "重伤", "性侵", "战争", "灾", "入狱", "瘫痪"])
            if is_severe and not has_lasting_effect and later_events:
                self.issues.append(Issue(
                    code="P2-003", severity=Severity.SERIOUS,
                    message=f"事件#{trauma.index}({trauma.year}年：{trauma.event_type})"
                            f"是严重创伤事件，但此后3年内无持续性影响描写",
                    event_index=trauma.index,
                    suggestion="增加创伤后1-3个事件中的持续性影响描写（如噩梦、回避、焦虑）"
                ))

    def _check_reaction_diversity(self, story: LifeStory):
        """P1-003：检测人物是否对所有事件做出相同类型的反应"""
        if len(story.events) < 6:
            return

        # 收集每个事件的反应类型
        reaction_keywords = {
            "沉默/忍受": ["沉默", "忍受", "咬牙", "算了", "没说什么"],
            "愤怒/反抗": ["愤怒", "反抗", "争吵", "怒", "骂", "摔"],
            "悲伤/哭泣": ["哭", "泪", "悲", "伤心", "难过"],
            "逃避/离开": ["逃", "走", "离开", "躲", "出走"],
            "接受/适应": ["接受", "适应", "习惯", "随它"],
        }

        reaction_counts: Dict[str, int] = {k: 0 for k in reaction_keywords}
        for e in story.events:
            for cat, kws in reaction_keywords.items():
                if any(kw in e.description for kw in kws):
                    reaction_counts[cat] += 1

        total_reactions = sum(reaction_counts.values())
        if total_reactions >= 5:
            dominant_cat = max(reaction_counts, key=reaction_counts.get)
            dominant_ratio = reaction_counts[dominant_cat] / total_reactions
            if dominant_ratio > 0.8:
                self.issues.append(Issue(
                    code="P1-003", severity=Severity.MINOR,
                    message=f"人物对不同事件的反应过于单一："
                            f"'{dominant_cat}'占{dominant_ratio * 100:.0f}%的反应",
                    suggestion="增加反应的多样性，让不同事件引发不同类型的情绪和行为"
                ))

    def _check_repeated_failed_choices(self, story: LifeStory):
        """P3-002：检测人物是否反复做出相同选择但期待不同结果"""
        choice_events = [e for e in story.events
                         if "选择" in e.event_type or "决定" in e.event_type]
        if len(choice_events) < 3:
            return

        # 检测相似的选择模式反复出现且都失败
        similar_choices: Dict[str, List[LifeEvent]] = {}
        for e in choice_events:
            # 简化：按event_type分组
            similar_choices.setdefault(e.event_type, []).append(e)

        for choice_type, events in similar_choices.items():
            if len(events) >= 3:
                # 检查是否都是负面结果
                negative_count = sum(
                    1 for e in events
                    if any(kw in e.description for kw in ["失败", "又", "还是", "仍然"])
                )
                if negative_count >= 3:
                    self.issues.append(Issue(
                        code="P3-002", severity=Severity.MINOR,
                        message=f"人物在'{choice_type}'上反复做出相同选择但结果类似，"
                                f"但故事未描写人物对此的反思或调整",
                        suggestion="增加人物对失败原因的反思，或描写尝试不同策略的过程"
                    ))


# =====================================================================
# 维度四：资源常识性（Resource Common Sense）
# =====================================================================

class ResourceCommonSenseDetector:
    """
    通用资源常识性检测

    检测项：
      R1-001 - 资源枯竭后仍维持高消费（无源支出）
      R1-002 - 一次性获得远超合理范围的资源
      R1-003 - 技能出现无训练/学习过程
      R2-001 - 贫困期消费水平与收入来源不匹配
      R2-002 - 关键资源在需要时突然出现（Deus Ex Machina资源版）
    """

    WEALTH_KEYWORDS = ["继承", "中奖", "获赠", "发现宝藏", "意外之财", "巨额"]
    POVERTY_KEYWORDS = ["贫穷", "贫困", "负债", "无业", "失业", "破产"]
    CONSUMPTION_KEYWORDS = ["买", "请客", "送礼", "旅游", "装修", "购置", "花"]

    def __init__(self):
        self.issues: List[Issue] = []

    def detect(self, story: LifeStory) -> DetectionResult:
        self.issues = []
        self._check_sudden_wealth(story)
        self._check_unexplained_resources(story)
        self._check_skill_acquisition(story)
        self._check_deus_ex_resource(story)
        return DetectionResult(issues=self.issues)

    def _check_sudden_wealth(self, story: LifeStory):
        for e in story.events:
            if any(kw in e.description or kw in e.event_type for kw in self.WEALTH_KEYWORDS):
                has_source = any(
                    kw in e.description for kw in
                    ["来自", "原因是", "因为", "亲戚", "父亲", "祖上", "保险"]
                )
                if not has_source:
                    self.issues.append(Issue(
                        code="R1-002", severity=Severity.SERIOUS,
                        message=f"事件#{e.index}({e.year}年：{e.event_type})中"
                                f"人物突然获得大量资源，但来源未说明",
                        event_index=e.index,
                        suggestion="说明资源的合法来源"
                    ))

    def _check_unexplained_resources(self, story: LifeStory):
        for i, e in enumerate(story.events):
            if any(kw in e.tags or kw in e.description for kw in self.POVERTY_KEYWORDS):
                for j in range(i + 1, min(i + 4, len(story.events))):
                    next_e = story.events[j]
                    if any(kw in next_e.description for kw in self.CONSUMPTION_KEYWORDS):
                        has_income = any(
                            "收入" in ev.event_type or "赚钱" in ev.description
                            or "工资" in ev.description or "找到工作" in ev.event_type
                            for ev in story.events[i:j + 1]
                        )
                        if not has_income:
                            self.issues.append(Issue(
                                code="R1-001", severity=Severity.SERIOUS,
                                message=f"事件#{e.index}显示人物贫穷/无业，"
                                        f"但事件#{next_e.index}中有消费行为，期间无收入来源",
                                event_index=next_e.index,
                                suggestion="增加收入来源事件，或降低此期间的消费描写"
                            ))
                        break

    def _check_skill_acquisition(self, story: LifeStory):
        """R1-003：检测技能是否凭空出现"""
        # 检查事件需要的技能是否在人物技能列表中
        known_skills = set(story.character.skills)
        skill_learning_events = set()

        for e in story.events:
            # 记录学习事件
            if any(kw in e.event_type for kw in ["学会", "学会", "学习", "掌握", "培训"]):
                for skill in e.skill_required:
                    skill_learning_events.add(skill)

            # 检查使用技能的事件
            if e.skill_required:
                for skill in e.skill_required:
                    if skill not in known_skills and skill not in skill_learning_events:
                        # 检查此前是否有学习该技能的事件
                        has_learning = any(
                            skill in prev_e.description or skill in prev_e.event_type
                            for prev_e in story.events
                            if prev_e.index < e.index and
                               any(kw in prev_e.event_type for kw in ["学会", "学习", "掌握", "培训"])
                        )
                        if not has_learning:
                            self.issues.append(Issue(
                                code="R1-003", severity=Severity.SERIOUS,
                                message=f"事件#{e.index}({e.year}年：{e.event_type})"
                                        f"需要技能'{skill}'，但人物此前无学习该技能的经历",
                                event_index=e.index,
                                suggestion=f"增加学习'{skill}'的事件，或去掉此技能需求"
                            ))

    def _check_deus_ex_resource(self, story: LifeStory):
        """R2-002：关键资源在需要时突然出现（无铺垫）"""
        for i, e in enumerate(story.events):
            # 检测"急需X，然后恰好获得X"模式
            need_keywords = ["急需", "需要", "没有钱", "缺", "付不起"]
            has_need = any(kw in e.description for kw in need_keywords)
            if not has_need:
                continue

            # 检查此后1-2个事件内是否恰好解决问题
            for j in range(i + 1, min(i + 3, len(story.events))):
                next_e = story.events[j]
                solve_keywords = ["恰好", "正好", "刚好", "碰巧", "没想到"]
                has_solve = any(kw in next_e.description for kw in solve_keywords)
                if has_solve:
                    # 检查此前是否有铺垫
                    has_foreshadowing = any(
                        any(kw in prev_e.description for kw in
                            ["听说", "联系", "约好", "安排", "计划"])
                        for prev_e in story.events[:i]
                    )
                    if not has_foreshadowing:
                        self.issues.append(Issue(
                            code="R2-002", severity=Severity.MINOR,
                            message=f"事件#{next_e.index}({next_e.year}年)中，"
                                    f"人物急需资源时恰好获得解决，缺乏铺垫",
                            event_index=next_e.index,
                            suggestion="在前文增加资源获取的铺垫（如提前联系、有计划安排）"
                        ))


# =====================================================================
# 维度五：叙事常识性（Narrative Common Sense）
# =====================================================================

class NarrativeCommonSenseDetector:
    """
    通用叙事常识性检测

    检测项：
      N1-001 - 重大转折无铺垫（伏笔不足）
      N1-002 - 人物核心特征完全逆转无过程
      N1-003 - 过多巧合推动剧情
      N2-001 - 叙述视角不一致
      N2-002 - 结局与过程脱节（过于突兀的happy/bad ending）
    """

    MAJOR_TURN_KEYWORDS = [
        "彻底改变", "从此", "再也不", "突然决定",
        "离婚", "分手", "断绝关系",
        "自杀", "企图自杀", "离家出走",
        "彻底失望", "信仰崩塌", "人生观改变",
    ]

    COINCIDENCE_KEYWORDS = [
        "正好", "刚好", "碰巧", "偶然", "没想到", "居然", "竟然",
        "路上遇到", "偶然听说", "碰巧看见", "刚好路过",
    ]

    FORESHADOW_KEYWORDS = [
        "不满", "犹豫", "困惑", "压力", "矛盾", "冲突",
        "问题", "困难", "越来越", "逐渐", "开始觉得",
        "第一次", "隐隐", "似乎", "不再", "很少",
    ]

    def __init__(self):
        self.issues: List[Issue] = []

    def detect(self, story: LifeStory) -> DetectionResult:
        self.issues = []
        self._check_turn_foreshadowing(story)
        self._check_character_reversal(story)
        self._check_excessive_coincidence(story)
        self._check_perspective_consistency(story)
        self._check_ending_abruptness(story)
        return DetectionResult(issues=self.issues)

    def _check_turn_foreshadowing(self, story: LifeStory):
        for i, e in enumerate(story.events):
            is_major = any(kw in e.event_type or kw in e.description
                           for kw in self.MAJOR_TURN_KEYWORDS)
            if not is_major:
                continue
            prev_events = story.events[max(0, i - 3):i]
            has_foreshadowing = any(
                any(kw in prev_e.description for kw in self.FORESHADOW_KEYWORDS)
                for prev_e in prev_events
            )
            if not has_foreshadowing and i >= 1:
                self.issues.append(Issue(
                    code="N1-001", severity=Severity.SERIOUS,
                    message=f"事件#{e.index}({e.year}年：{e.event_type})是重大转折，"
                            f"但此前事件中缺乏铺垫和暗示",
                    event_index=e.index,
                    suggestion="在转折前增加1-2个暗示性事件或情绪积累描写"
                ))

    def _check_character_reversal(self, story: LifeStory):
        reversal_attrs = {}
        for e in story.events:
            for attr, change in e.attribute_changes.items():
                if attr not in reversal_attrs:
                    reversal_attrs[attr] = []
                reversal_attrs[attr].append((e.index, e.year, change))

        for attr, changes in reversal_attrs.items():
            if len(changes) >= 3:
                total_span = max(y for _, y, _ in changes) - min(y for _, y, _ in changes)
                if total_span < 5:
                    total_change = sum(c for _, _, c in changes)
                    if abs(total_change) > 30:
                        self.issues.append(Issue(
                            code="N1-002", severity=Severity.MINOR,
                            message=f"属性'{attr}'在{total_span}年内剧烈波动"
                                    f"（总变化{total_change:+}），人物特征缺乏稳定性",
                            suggestion="减少属性的双向剧烈波动，使人物特征更稳定可辨"
                        ))

    def _check_excessive_coincidence(self, story: LifeStory):
        coincidence_count = sum(
            1 for e in story.events
            if any(kw in e.description for kw in self.COINCIDENCE_KEYWORDS)
        )
        total = len(story.events)
        if total > 0:
            ratio = coincidence_count / total
            if ratio > 0.3:
                self.issues.append(Issue(
                    code="N1-003", severity=Severity.SERIOUS,
                    message=f"故事中{coincidence_count}/{total}个事件"
                            f"({ratio * 100:.0f}%)依赖巧合推动剧情，比例偏高",
                    suggestion="将部分'巧合'改为由人物主动行为或已有关系网络推动"
                ))

    def _check_perspective_consistency(self, story: LifeStory):
        """N2-001：检测叙述视角是否一致"""
        first_person_indicators = ["我", "我的", "我们"]
        third_person_indicators = ["他", "她", "他们", "其"]

        first_person_count = 0
        third_person_count = 0
        for e in story.events:
            if any(kw in e.description for kw in first_person_indicators):
                first_person_count += 1
            if any(kw in e.description for kw in third_person_indicators):
                third_person_count += 1

        total = first_person_count + third_person_count
        if total >= 5:
            first_ratio = first_person_count / total
            third_ratio = third_person_count / total
            # 如果两种视角交替出现（都不是主导，且都有相当比例）
            if 0.3 < first_ratio < 0.7 and 0.3 < third_ratio < 0.7:
                self.issues.append(Issue(
                    code="N2-001", severity=Severity.MINOR,
                    message=f"叙述视角在第一人称({first_person_count}次)和"
                            f"第三人称({third_person_count}次)之间频繁切换",
                    suggestion="统一叙述视角，或明确标注视角切换的位置"
                ))

    def _check_ending_abruptness(self, story: LifeStory):
        """N2-002：检测结局是否过于突兀"""
        if len(story.events) < 5:
            return

        last_event = story.events[-1]
        is_final = last_event.event_type in ("死亡", "结局", "终章", "尾声")

        if is_final:
            # 检查最后3个事件是否有收束感
            last_3 = story.events[-3:]
            has_closure = any(
                any(kw in e.description for kw in
                    ["总结", "回顾", "一生", "终于", "最后", "不再", "从此",
                     "安详", "平静", "满足", "遗憾", "释然"])
                for e in last_3
            )
            if not has_closure:
                self.issues.append(Issue(
                    code="N2-002", severity=Severity.MINOR,
                    message=f"故事结局（事件#{last_event.index}）缺乏收束感，"
                            f"最后几个事件没有总结或反思的叙述",
                    event_index=last_event.index,
                    suggestion="在结尾增加人物对一生的回顾、反思或总结性叙述"
                ))


# =====================================================================
# 维度六：地理空间常识性（Geographic/Spatial Common Sense）★ NEW
# =====================================================================

class GeographicCommonSenseDetector:
    """
    通用地理空间常识性检测

    检测项：
      G1-001 - 同日不可能距离（人在同一天出现在相距过远的两地）
      G1-002 - 无触发的大规模迁移（无原因地搬家/出国）
      G1-003 - 地理知识超前（人物知道不该知道的地理信息）
      G1-004 - 环境-行为矛盾（如在无河流的地方游泳、在沙漠种水稻）
    """

    # 中国城市间大致距离（公里），用于同日移动检测
    # 仅列主要城市对，实际可扩展
    CITY_DISTANCES = {
        ("北京", "上海"): 1200,
        ("北京", "广州"): 2200,
        ("北京", "乌鲁木齐"): 3300,
        ("上海", "广州"): 1500,
        ("上海", "成都"): 2000,
        ("广州", "成都"): 1500,
    }

    # 不同年代的日移动极限（公里/天）
    MOBILITY_LIMITS = {
        (0, 1900): 80,       # 马车/步行
        (1900, 1950): 300,   # 火车
        (1950, 1980): 800,   # 火车+飞机（极少人坐飞机）
        (1980, 2000): 1500,  # 火车+飞机（普及）
        (2000, 2100): 5000,  # 高铁+飞机
    }

    # 迁移触发的常见原因
    MIGRATION_TRIGGERS = [
        "工作", "就业", "升职", "调任", "婚姻", "结婚", "上学", "考学",
        "逃难", "逃荒", "战乱", "迫害", "饥荒", "探亲", "投靠",
        "拆迁", "征地", "政策", "安排",
    ]

    def __init__(self):
        self.issues: List[Issue] = []

    def detect(self, story: LifeStory) -> DetectionResult:
        self.issues = []
        self._check_impossible_movement(story)
        self._check_unmotivated_migration(story)
        self._check_environment_behavior(story)
        return DetectionResult(issues=self.issues)

    def _get_mobility_limit(self, year: int) -> int:
        for (start, end), limit in self.MOBILITY_LIMITS.items():
            if start <= year < end:
                return limit
        return 80

    def _check_impossible_movement(self, story: LifeStory):
        """G1-001：同日不可能距离"""
        from collections import defaultdict
        events_by_year = defaultdict(list)
        for e in story.events:
            if e.location:
                events_by_year[e.year].append(e)

        for year, events in events_by_year.items():
            if len(events) < 2:
                continue
            limit = self._get_mobility_limit(year)
            # 检查同一年份中不同地点的事件
            locations = [(e.index, e.location) for e in events if e.location]
            for i in range(len(locations)):
                for j in range(i + 1, len(locations)):
                    idx_a, loc_a = locations[i]
                    idx_b, loc_b = locations[j]
                    # 简化：检查已知城市对
                    for (city_a, city_b), dist in self.CITY_DISTANCES.items():
                        if (city_a in loc_a and city_b in loc_b) or \
                           (city_b in loc_a and city_a in loc_b):
                            if dist > limit * 2:  # 同年多次往返
                                self.issues.append(Issue(
                                    code="G1-001", severity=Severity.SERIOUS,
                                    message=f"事件#{idx_a}和#{idx_b}({year}年)分别发生在"
                                            f"'{loc_a}'和'{loc_b}'，距离约{dist}公里，"
                                            f"但{year}年代日移动极限约{limit}公里/天",
                                    event_index=idx_b,
                                    suggestion="增加旅行时间描写，或减少同年的远距离移动"
                                ))

    def _check_unmotivated_migration(self, story: LifeStory):
        """G1-002：无触发的大规模迁移"""
        prev_location = ""
        for e in story.events:
            if not e.location:
                continue
            if prev_location and e.location != prev_location:
                # 检查是否有迁移原因
                has_trigger = any(
                    kw in e.event_type or kw in e.description
                    for kw in self.MIGRATION_TRIGGERS
                )
                # 检查是否跨省/跨城（简化：地点字符串完全不同）
                is_major_move = prev_location not in e.location and e.location not in prev_location
                if is_major_move and not has_trigger:
                    self.issues.append(Issue(
                        code="G1-002", severity=Severity.MINOR,
                        message=f"事件#{e.index}({e.year}年)人物从'{prev_location}'"
                                f"移至'{e.location}'，但缺乏迁移原因说明",
                        event_index=e.index,
                        suggestion="增加迁移的原因（如工作调动、婚姻、升学等）"
                    ))
            prev_location = e.location

    def _check_environment_behavior(self, story: LifeStory):
        """G1-004：环境-行为矛盾"""
        # 环境-行为不匹配的示例
        ENV_BEHAVIOR_MISMATCH = [
            ("沙漠", ["游泳", "捕鱼", "种水稻", "划船"], Severity.MINOR),
            ("高原", ["潜水", "深海"], Severity.MINOR),
            ("内陆", ["出海", "远航", "打渔"], Severity.MINOR),
            ("热带", ["滑雪", "冰钓", "溜冰"], Severity.MINOR),
            ("极寒", ["游泳", "日光浴"], Severity.MINOR),
        ]
        for e in story.events:
            if not e.location:
                continue
            for env, behaviors, sev in ENV_BEHAVIOR_MISMATCH:
                if env in e.location:
                    for behavior in behaviors:
                        if behavior in e.description:
                            self.issues.append(Issue(
                                code="G1-004", severity=sev,
                                message=f"事件#{e.index}({e.year}年)发生在'{e.location}'"
                                        f"（{env}地区），但描写了'{behavior}'",
                                event_index=e.index,
                                suggestion=f"'{env}'地区通常不适合'{behavior}'，请修正地点或行为"
                            ))


# =====================================================================
# 维度七：生理健康常识性（Biological/Health Common Sense）★ NEW
# =====================================================================

class HealthCommonSenseDetector:
    """
    通用生理健康常识性检测

    检测项：
      H1-001 - 疾病进展时间不合理（如感冒持续3年/癌症1天治愈）
      H1-002 - 严重伤病无治疗即康复
      H1-003 - 生理能力超出人体极限
      H1-004 - 慢性病/残疾突然消失无解释
      H1-005 - 年龄-体能矛盾（如80岁跑马拉松）
      H1-006 - 生育相关生理矛盾
    """

    # 疾病-最短持续期/最长持续期（天）
    DISEASE_DURATION = {
        "感冒": (3, 30),
        "骨折": (30, 365),
        "肺炎": (7, 90),
        "癌症": (90, 99999),  # 通常不会"治愈"后短期复发再治愈
        "心脏病": (7, 99999),  # 慢性
        "糖尿病": (365, 99999),
        "高血压": (365, 99999),
        "肺结核": (90, 730),
        "阑尾炎": (1, 30),
        "肝炎": (30, 99999),
        "中风": (7, 99999),
        "骨折": (30, 365),
        "烧伤": (14, 365),
        "失明": (365, 99999),
        "瘫痪": (365, 99999),
    }

    # 严重伤病需要的治疗/恢复条件
    SEVERE_CONDITIONS_REQUIRING_TREATMENT = [
        "骨折", "癌症", "心脏病", "中风", "烧伤", "阑尾炎",
        "肺炎", "肺结核", "肝炎", "失明", "瘫痪",
    ]

    # 年龄-体能活动极限
    AGE_PHYSICAL_LIMITS = [
        ("跑马拉松", 80, Severity.MINOR),
        ("登山", 75, Severity.MINOR),
        ("重体力劳动", 70, Severity.SERIOUS),
        ("长时间熬夜", 65, Severity.MINOR),
        ("生育（女性）", 50, Severity.SERIOUS),
    ]

    def __init__(self):
        self.issues: List[Issue] = []

    def detect(self, story: LifeStory) -> DetectionResult:
        self.issues = []
        self._check_disease_duration(story)
        self._check_treatment_requirement(story)
        self._check_chronic_condition_disappearance(story)
        self._check_age_physical_limits(story)
        self._check_fertility_contradiction(story)
        return DetectionResult(issues=self.issues)

    def _check_disease_duration(self, story: LifeStory):
        """H1-001：疾病进展时间不合理"""
        illness_events = {}  # 疾病名 → (发病事件, 康复事件)
        for e in story.events:
            for disease in self.DISEASE_DURATION:
                if disease in e.event_type or disease in e.description:
                    if e.event_type in ("生病", "确诊", "患病") or "确诊" in e.description:
                        illness_events[disease] = {"start": e, "end": None}

            # 检查康复事件
            for disease, events in illness_events.items():
                if events["end"] is None:
                    if "康复" in e.event_type or "痊愈" in e.description or \
                       "治好" in e.description:
                        if disease in e.description or disease in events["start"].description:
                            events["end"] = e

        for disease, events in illness_events.items():
            if events["end"] and events["start"]:
                interval_days = (date(events["end"].year, 1, 1) -
                                date(events["start"].year, 1, 1)).days
                min_dur, max_dur = self.DISEASE_DURATION[disease]
                if interval_days < min_dur:
                    self.issues.append(Issue(
                        code="H1-001", severity=Severity.SERIOUS,
                        message=f"'{disease}'从发病到康复仅{interval_days}天，"
                                f"但通常至少需要{min_dur}天",
                        event_index=events["end"].index,
                        suggestion=f"延长康复时间至至少{min_dur}天，或说明特殊治疗"
                    ))

    def _check_treatment_requirement(self, story: LifeStory):
        """H1-002：严重伤病无治疗即康复"""
        for e in story.events:
            for condition in self.SEVERE_CONDITIONS_REQUIRING_TREATMENT:
                if condition in e.event_type or condition in e.description:
                    if e.event_type in ("康复", "痊愈") or "康复" in e.description:
                        # 检查发病和康复之间是否有治疗事件
                        start_events = [
                            ev for ev in story.events
                            if ev.index < e.index and condition in ev.description
                        ]
                        if start_events:
                            has_treatment = any(
                                "治疗" in ev.description or "手术" in ev.description
                                or "住院" in ev.description or "吃药" in ev.description
                                or "看医生" in ev.description or "医院" in ev.description
                                for ev in story.events
                                if start_events[0].index <= ev.index <= e.index
                            )
                            if not has_treatment:
                                self.issues.append(Issue(
                                    code="H1-002", severity=Severity.SERIOUS,
                                    message=f"'{condition}'康复（事件#{e.index}）但无治疗过程描写",
                                    event_index=e.index,
                                    suggestion=f"增加'{condition}'的治疗/就医事件"
                                ))

    def _check_chronic_condition_disappearance(self, story: LifeStory):
        """H1-004：慢性病/残疾突然消失无解释"""
        chronic_conditions = ["失明", "瘫痪", "截肢", "聋", "哑", "糖尿病", "高血压"]
        active_conditions = set()

        for e in story.events:
            # 记录出现的慢性病/残疾
            for cond in chronic_conditions:
                if cond in e.description and e.event_type not in ("康复", "痊愈"):
                    active_conditions.add(cond)

                # 检查消失
                if cond in active_conditions and \
                   ("康复" in e.event_type or "好了" in e.description or
                    "恢复" in e.description):
                    has_explanation = any(
                        kw in e.description for kw in
                        ["手术", "移植", "奇迹", "治疗", "康复训练", "义肢", "植入"]
                    )
                    if not has_explanation:
                        self.issues.append(Issue(
                            code="H1-004", severity=Severity.SERIOUS,
                            message=f"慢性病/残疾'{cond}'在事件#{e.index}中消失，"
                                    f"但无医疗解释",
                            event_index=e.index,
                            suggestion=f"增加'{cond}'消失的医疗解释（如手术、义肢等）"
                        ))
                    active_conditions.discard(cond)

    def _check_age_physical_limits(self, story: LifeStory):
        """H1-005：年龄-体能矛盾"""
        for e in story.events:
            for activity, max_age, sev in self.AGE_PHYSICAL_LIMITS:
                if activity in e.description and e.age > max_age:
                    self.issues.append(Issue(
                        code="H1-005", severity=sev,
                        message=f"事件#{e.index}({e.year}年，年龄{e.age}岁)中"
                                f"人物进行了'{activity}'，超出年龄合理范围({max_age}岁以下)",
                        event_index=e.index,
                        suggestion=f"降低活动强度，或提供特殊的身体条件说明"
                    ))

    def _check_fertility_contradiction(self, story: LifeStory):
        """H1-006：生育相关生理矛盾"""
        if story.character.gender == "女":
            for e in story.events:
                if "生子" in e.event_type or "怀孕" in e.event_type:
                    if e.age > 50 or e.age < 12:
                        self.issues.append(Issue(
                            code="H1-006", severity=Severity.SERIOUS,
                            message=f"事件#{e.index}({e.year}年，年龄{e.age}岁)中"
                                    f"女性人物{'生子' if '生子' in e.event_type else '怀孕'}，"
                                    f"但年龄在生理上{'偏高' if e.age > 50 else '偏低'}",
                            event_index=e.index,
                            suggestion="提供特殊医学解释（如试管婴儿、早产等）"
                        ))
                # 怀孕到生子的时间
                if "生子" in e.event_type:
                    # 检查此前是否有怀孕事件
                    pregnancy_events = [
                        ev for ev in story.events
                        if ev.index < e.index and "怀孕" in ev.event_type
                    ]
                    if pregnancy_events:
                        last_pregnancy = pregnancy_events[-1]
                        interval = (date(e.year, 1, 1) - date(last_pregnancy.year, 1, 1)).days
                        if interval < 180:  # 不足6个月
                            self.issues.append(Issue(
                                code="H1-006", severity=Severity.SERIOUS,
                                message=f"从怀孕(事件#{last_pregnancy.index}，{last_pregnancy.year}年)"
                                        f"到生子(事件#{e.index}，{e.year}年)间隔仅约{interval // 30}个月，"
                                        f"不足正常孕期",
                                event_index=e.index,
                                suggestion="增加间隔至至少9个月，或说明早产"
                            ))


# =====================================================================
# 维度八：人物关系连续性（Character Relationship Continuity）★ NEW
# =====================================================================

class RelationshipContinuityDetector:
    """
    通用人物关系连续性检测

    检测项：
      C1-001 - 关键关系人物无引入（突然出现且被当作熟人）
      C1-002 - 世代矛盾（子女年龄≥父母年龄）
      C1-003 - 关系断裂无解释（重要人物消失）
      C1-004 - 关系过于频繁地建立和断裂（关系不稳定）
      C1-005 - 核心亲属关系的长期缺席
    """

    # 核心亲属关系（不应长期缺席）
    CORE_FAMILY = {"父亲", "母亲"}

    # 关系建立事件
    RELATIONSHIP_START_KEYWORDS = ["结婚", "认识", "成为朋友", "成为同事", "拜师"]

    # 关系断裂事件
    RELATIONSHIP_END_KEYWORDS = ["离婚", "分手", "断绝关系", "失联", "绝交"]

    def __init__(self):
        self.issues: List[Issue] = []

    def detect(self, story: LifeStory) -> DetectionResult:
        self.issues = []
        self._check_relationship_introduction(story)
        self._check_generational_consistency(story)
        self._check_disappeared_relationships(story)
        self._check_relationship_instability(story)
        self._check_core_family_presence(story)
        return DetectionResult(issues=self.issues)

    def _check_relationship_introduction(self, story: LifeStory):
        """C1-001：关键关系人物无引入"""
        introduced_characters = {story.character.id}
        for e in story.events:
            # 记录被引入的人物
            for char_id in e.involved_characters:
                introduced_characters.add(char_id)

            # 检查是否出现了未引入的人物
            for char_id in e.involved_characters:
                if char_id not in introduced_characters:
                    # 检查是否有介绍性描述
                    has_intro = any(
                        kw in e.description for kw in
                        ["认识", "第一次见", "新来的", "初次", "介绍", "遇到"]
                    )
                    if not has_intro:
                        self.issues.append(Issue(
                            code="C1-001", severity=Severity.MINOR,
                            message=f"事件#{e.index}({e.year}年)中人物'{char_id}'突然出现"
                                    f"但此前无引入/介绍",
                            event_index=e.index,
                            suggestion=f"增加'{char_id}'的首次出现或介绍性叙述"
                        ))
                    introduced_characters.add(char_id)

    def _check_generational_consistency(self, story: LifeStory):
        """C1-002：世代矛盾"""
        for r in story.relationships:
            if r.relation_type in ("父亲", "母亲", "父母"):
                parent = story.get_character(r.character_id_a)
                child = story.get_character(r.character_id_b)
                if parent and child:
                    # 父母应至少比子女大15岁
                    if parent.birth_year >= child.birth_year - 14:
                        self.issues.append(Issue(
                            code="C1-002", severity=Severity.SERIOUS,
                            message=f"人物'{parent.name}'(出生{parent.birth_year})是"
                                    f"'{child.name}'(出生{child.birth_year})的{r.relation_type}，"
                                    f"但年龄差不足15岁",
                            suggestion="修正出生年份，或检查关系类型是否正确"
                        ))

    def _check_disappeared_relationships(self, story: LifeStory):
        """C1-003：关系断裂无解释"""
        for r in story.relationships:
            if r.end_year and r.relation_type in ("配偶", "朋友", "同事"):
                if not r.end_reason:
                    self.issues.append(Issue(
                        code="C1-003", severity=Severity.MINOR,
                        message=f"人物'{r.character_id_a}'与'{r.character_id_b}'的"
                                f"'{r.relation_type}'关系在{r.end_year}年结束，"
                                f"但无结束原因",
                        suggestion="说明关系结束的原因（如离婚、搬家、去世等）"
                    ))

    def _check_relationship_instability(self, story: LifeStory):
        """C1-004：关系过于频繁地建立和断裂"""
        start_count = 0
        end_count = 0
        for e in story.events:
            if any(kw in e.event_type for kw in self.RELATIONSHIP_START_KEYWORDS):
                start_count += 1
            if any(kw in e.event_type for kw in self.RELATIONSHIP_END_KEYWORDS):
                end_count += 1

        # 如果建立+断裂次数过多（相对于故事长度）
        total = start_count + end_count
        if total > 8 and len(story.events) > 0:
            ratio = total / len(story.events)
            if ratio > 0.5:
                self.issues.append(Issue(
                    code="C1-004", severity=Severity.MINOR,
                    message=f"故事中关系建立({start_count}次)和断裂({end_count}次)频繁，"
                            f"人物关系极不稳定",
                    suggestion="减少关系的建立/断裂次数，使核心关系更持久"
                ))

    def _check_core_family_presence(self, story: LifeStory):
        """C1-005：核心亲属关系的长期缺席"""
        if not story.relationships:
            # 如果没有关系数据，从事件中检测
            for family_role in self.CORE_FAMILY:
                family_mentions = [
                    (e.year, e.index) for e in story.events
                    if family_role in e.description
                ]
                if not family_mentions:
                    # 整个故事从未提及父亲或母亲
                    self.issues.append(Issue(
                        code="C1-005", severity=Severity.MINOR,
                        message=f"整个故事中从未提及人物的'{family_role}'",
                        suggestion=f"至少在一个事件中提及'{family_role}'的存在或缺席原因"
                    ))


# =====================================================================
# 维度九：事件序列逻辑性（Event Sequence Logic）★ NEW
# =====================================================================

class EventSequenceDetector:
    """
    通用事件序列逻辑性检测

    检测项：
      E1-001 - 前置事件缺失（如毕业前无入学、晋升前无入职）
      E1-002 - 互斥事件共存（如同时在职和退休）
      E1-003 - 状态前置条件违反（如从未入职就离职）
      E1-004 - 身份状态不连续（如已婚→未婚→已婚但无离婚/再婚）
    """

    # 事件前置条件：(后续事件, 前置事件列表, 允许替代关键词)
    PREREQUISITES = [
        ("毕业", ["入学", "上学", "考入"], None),
        ("晋升", ["入职", "参加工作", "就业"], None),
        ("退休", ["入职", "参加工作", "就业", "当兵"], None),
        ("离职", ["入职", "参加工作", "就业"], None),
        ("离婚", ["结婚"], None),
        ("再婚", ["离婚", "丧偶"], None),
        ("生子", ["结婚", "怀孕"], "非婚生"),  # 允许"非婚生"作为替代
        ("出师", ["拜师", "学艺", "学徒"], None),
        ("退休金", ["退休"], None),
        ("遗产", ["死亡"], None),  # 遗产需要有人死亡
    ]

    # 互斥状态对
    MUTUALLY_EXCLUSIVE = [
        ("在职", "退休"),
        ("在职", "失业"),
        ("已婚", "未婚"),
        ("入学", "毕业"),
        ("活着", "死亡"),
    ]

    def __init__(self):
        self.issues: List[Issue] = []

    def detect(self, story: LifeStory) -> DetectionResult:
        self.issues = []
        self._check_prerequisites(story)
        self._check_state_continuity(story)
        return DetectionResult(issues=self.issues)

    def _check_prerequisites(self, story: LifeStory):
        """E1-001：前置事件缺失"""
        for e in story.events:
            for (later_event, prereqs, alt_kw) in self.PREREQUISITES:
                if later_event in e.event_type or later_event in e.description:
                    # 检查是否有前置事件
                    has_prereq = any(
                        any(p in prev_e.event_type or p in prev_e.description
                            for p in prereqs)
                        for prev_e in story.events
                        if prev_e.index < e.index
                    )
                    # 检查替代关键词
                    has_alt = False
                    if alt_kw and alt_kw in e.description:
                        has_alt = True

                    if not has_prereq and not has_alt:
                        self.issues.append(Issue(
                            code="E1-001", severity=Severity.SERIOUS,
                            message=f"事件#{e.index}({e.year}年：{e.event_type})"
                                    f"发生，但此前无前置事件{prereqs}",
                            event_index=e.index,
                            suggestion=f"在{e.year}年前增加{prereqs[0]}事件"
                        ))

    def _check_state_continuity(self, story: LifeStory):
        """E1-004：身份状态不连续"""
        # 跟踪婚姻状态
        marriage_status = "未婚"
        last_marriage_change = None

        for e in story.events:
            if "结婚" in e.event_type and marriage_status != "已婚":
                marriage_status = "已婚"
                last_marriage_change = e
            elif "离婚" in e.event_type and marriage_status == "已婚":
                marriage_status = "离异"
                last_marriage_change = e
            elif "丧偶" in e.event_type and marriage_status == "已婚":
                marriage_status = "丧偶"
                last_marriage_change = e
            elif "再婚" in e.event_type and marriage_status in ("离异", "丧偶"):
                marriage_status = "已婚"
                last_marriage_change = e
            elif "结婚" in e.event_type and marriage_status == "已婚":
                # 再次结婚但没有离婚/丧偶
                self.issues.append(Issue(
                    code="E1-004", severity=Severity.SERIOUS,
                    message=f"事件#{e.index}({e.year}年：{e.event_type})中人物再次结婚，"
                            f"但此前的婚姻状态为'{marriage_status}'，无离婚/丧偶记录",
                    event_index=e.index,
                    suggestion="在再婚前增加离婚或丧偶事件"
                ))

        # 跟踪职业状态（简化版）
        employment_status = "无业"
        for e in story.events:
            if e.event_type in ("入职", "参加工作", "就业"):
                employment_status = "在职"
            elif e.event_type == "离职" and employment_status == "在职":
                employment_status = "离职"
            elif e.event_type == "退休" and employment_status == "在职":
                employment_status = "退休"
            elif e.event_type == "退休" and employment_status != "在职":
                self.issues.append(Issue(
                    code="E1-003", severity=Severity.SERIOUS,
                    message=f"事件#{e.index}({e.year}年：退休)中人物退休，"
                            f"但此前的就业状态为'{employment_status}'，无在职记录",
                    event_index=e.index,
                    suggestion="在退休前增加入职/工作事件"
                ))


# =====================================================================
# 维度十：知识与文化常识性（Knowledge & Cultural Common Sense）★ NEW
# =====================================================================

class KnowledgeCulturalDetector:
    """
    通用知识与文化常识性检测

    检测项：
      K1-001 - 时代性知识超前（如1970年使用互联网）
      K1-002 - 专业能力与职业/训练不匹配
      K1-003 - 文化引用时代错误（如引用尚未出版的作品）
      K1-004 - 语言/词汇时代错误
    """

    # 技术/知识出现年份（中文语境为主）
    TECHNOLOGY_TIMELINE = {
        "互联网": 1994,      # 中国接入互联网
        "手机": 1990,        # 大城市开始有手机
        "智能手机": 2010,
        "微信": 2011,
        "支付宝": 2004,
        "高铁": 2008,        # 京津城际
        "网购": 2003,        # 淘宝
        "直播": 2016,
        "短视频": 2017,
        "外卖": 2014,
        "共享单车": 2016,
        "二维码": 2012,      # 大规模使用
        "大数据": 2013,
        "人工智能": 2016,    # AlphaGo后广泛认知
        "电视机": 1980,      # 中国城市普及
        "冰箱": 1985,
        "空调": 1995,
        "电脑": 1995,        # 城市家庭
        "BB机": 1990,
        "固定电话": 1990,    # 城市家庭
        "信用卡": 2000,      # 大规模使用
        "高考恢复": 1977,
    }

    # 文化作品出版年份
    CULTURAL_WORKS = {
        "《哈利波特》": 2000,  # 中文版出版
        "《三体》": 2008,
        "《活着》": 1993,
        "《围城》": 1991,      # 电视剧热播
        "《红楼梦》": 1791,    # 无需检测
        "《西游记》": 1592,
    }

    # 时代性词汇
    PERIOD_VOCABULARY = {
        "内卷": 2020,
        "躺平": 2021,
        "996": 2019,
        "打工人": 2020,
        "社畜": 2019,
        "卷王": 2021,
        "佛系": 2018,
        "YYDS": 2021,
        "绝绝子": 2021,
        "下海": 1990,        # 90年代特有
        "下岗": 1995,        # 90年代特有
        "万元户": 1985,      # 80年代特有
        "粮票": 1955,        # 至1993年
    }

    # 专业-技能匹配
    PROFESSION_SKILLS = {
        "医生": ["医学", "诊断", "手术", "处方", "临床"],
        "教师": ["教学", "备课", "批改", "教育学"],
        "律师": ["法律", "诉讼", "辩护", "法条"],
        "工程师": ["设计", "计算", "工程", "技术"],
        "农民": ["种植", "养殖", "农时", "节气"],
        "商人": ["经营", "销售", "采购", "利润"],
    }

    def __init__(self):
        self.issues: List[Issue] = []

    def detect(self, story: LifeStory) -> DetectionResult:
        self.issues = []
        self._check_technology_anachronism(story)
        self._check_cultural_anachronism(story)
        self._check_vocabulary_anachronism(story)
        self._check_profession_skill_match(story)
        return DetectionResult(issues=self.issues)

    def _check_technology_anachronism(self, story: LifeStory):
        """K1-001：时代性知识超前"""
        for e in story.events:
            for tech, year in self.TECHNOLOGY_TIMELINE.items():
                if tech in e.description and e.year < year:
                    gap = year - e.year
                    if gap > 5:  # 允许5年误差（早期采用者）
                        self.issues.append(Issue(
                            code="K1-001", severity=Severity.SERIOUS,
                            message=f"事件#{e.index}({e.year}年)中出现了'{tech}'，"
                                    f"但该技术/知识在{year}年后才在中国普及（提前{gap}年）",
                            event_index=e.index,
                            suggestion=f"将'{tech}'替换为{e.year}年代更常见的技术/方式"
                        ))
                    elif gap > 2:
                        self.issues.append(Issue(
                            code="K1-001", severity=Severity.MINOR,
                            message=f"事件#{e.index}({e.year}年)中出现'{tech}'，"
                                    f"稍早于其普及年份({year}年)",
                            event_index=e.index,
                            suggestion="如果是早期采用者，需要说明获取途径"
                        ))

    def _check_cultural_anachronism(self, story: LifeStory):
        """K1-003：文化引用时代错误"""
        for e in story.events:
            for work, year in self.CULTURAL_WORKS.items():
                if work in e.description and e.year < year:
                    self.issues.append(Issue(
                        code="K1-003", severity=Severity.SERIOUS,
                        message=f"事件#{e.index}({e.year}年)中引用了{work}，"
                                f"但该作品在{year}年后才出版/发表",
                        event_index=e.index,
                        suggestion=f"替换为{e.year}年代的文化作品引用"
                    ))

    def _check_vocabulary_anachronism(self, story: LifeStory):
        """K1-004：语言/词汇时代错误"""
        for e in story.events:
            for vocab, year in self.PERIOD_VOCABULARY.items():
                if vocab in e.description:
                    # 某些词汇有消亡期（如粮票1993年后不再使用）
                    if e.year < year:
                        self.issues.append(Issue(
                            code="K1-004", severity=Severity.MINOR,
                            message=f"事件#{e.index}({e.year}年)中使用了词汇'{vocab}'，"
                                    f"但该词在{year}年后才出现",
                            event_index=e.index,
                            suggestion=f"替换为{e.year}年代更常见的表达"
                        ))
                    # 粮票特例：1993年后不应出现
                    if vocab == "粮票" and e.year > 1993:
                        self.issues.append(Issue(
                            code="K1-004", severity=Severity.SERIOUS,
                            message=f"事件#{e.index}({e.year}年)中出现了'粮票'，"
                                    f"但粮票在1993年后已取消",
                            event_index=e.index,
                            suggestion="移除粮票相关叙述"
                        ))

    def _check_profession_skill_match(self, story: LifeStory):
        """K1-002：专业能力与职业/训练不匹配"""
        for e in story.events:
            for profession, skills in self.PROFESSION_SKILLS.items():
                if profession in e.event_type or profession in e.description:
                    # 检查人物是否有相关技能
                    if story.character.skills:
                        has_skill = any(
                            any(s in skill.lower() for s in [sk.lower() for sk in skills])
                            for skill in story.character.skills
                        )
                        if not has_skill:
                            # 检查是否有学习/培训事件
                            has_training = any(
                                any(s in prev_e.description for s in skills)
                                for prev_e in story.events if prev_e.index < e.index
                            )
                            if not has_training:
                                self.issues.append(Issue(
                                    code="K1-002", severity=Severity.MINOR,
                                    message=f"事件#{e.index}中人物担任'{profession}'，"
                                            f"但无相关技能或培训经历",
                                    event_index=e.index,
                                    suggestion=f"增加'{profession}'相关的培训或学习经历"
                                ))


# =====================================================================
# 维度十一：故事节奏与密度（Story Pacing & Density）★ NEW
# =====================================================================

class StoryPacingDetector:
    """
    通用故事节奏与密度检测

    检测项：
      D1-001 - 重大事件聚集（短时间过多大事）
      D1-002 - 事件单调性（缺乏事件类型多样性）
      D1-003 - 人生关键阶段覆盖缺失
      D1-004 - 危机疲劳（连续负面事件过多）
      D1-005 - 人生阶段事件密度极度不均
    """

    # 人生关键阶段（必须覆盖）
    LIFE_STAGES = [
        (0, 5, "幼年"),
        (6, 12, "童年/小学"),
        (13, 18, "青春期/中学"),
        (19, 25, "青年初期"),
        (26, 40, "壮年"),
        (41, 55, "中年"),
        (56, 70, "中老年"),
    ]

    # 重大事件类型
    MAJOR_EVENT_TYPES = [
        "死亡", "结婚", "离婚", "生子", "失业", "破产",
        "入学", "毕业", "入职", "晋升", "退休", "迁移",
        "战争", "天灾", "入狱",
    ]

    def __init__(self):
        self.issues: List[Issue] = []

    def detect(self, story: LifeStory) -> DetectionResult:
        self.issues = []
        self._check_event_clustering(story)
        self._check_event_monotony(story)
        self._check_life_stage_coverage(story)
        self._check_crisis_fatigue(story)
        self._check_density_unevenness(story)
        return DetectionResult(issues=self.issues)

    def _check_event_clustering(self, story: LifeStory):
        """D1-001：重大事件聚集"""
        sorted_events = sorted(story.events, key=lambda e: e.year)
        for i in range(len(sorted_events)):
            # 检查此后3年内有多少重大事件
            window_end = sorted_events[i].year + 3
            major_count = 0
            for j in range(i, len(sorted_events)):
                if sorted_events[j].year > window_end:
                    break
                if any(mj in sorted_events[j].event_type for mj in self.MAJOR_EVENT_TYPES):
                    major_count += 1

            if major_count >= 5:  # 3年内5个以上重大事件
                self.issues.append(Issue(
                    code="D1-001", severity=Severity.MINOR,
                    message=f"{sorted_events[i].year}年前后3年内聚集了{major_count}个"
                            f"重大事件，密度偏高",
                    event_index=sorted_events[i].index,
                    suggestion="分散重大事件到更长的时间段，或增加过渡性平淡事件"
                ))
                break  # 只报一次

    def _check_event_monotony(self, story: LifeStory):
        """D1-002：事件单调性"""
        if len(story.events) < 5:
            return

        event_types = [e.event_type for e in story.events]
        unique_types = len(set(event_types))
        total_types = len(event_types)

        # 如果80%以上事件是同一类型
        from collections import Counter
        type_counts = Counter(event_types)
        most_common_type, most_common_count = type_counts.most_common(1)[0]

        if total_types >= 5 and most_common_count / total_types > 0.8:
            self.issues.append(Issue(
                code="D1-002", severity=Severity.MINOR,
                message=f"故事中{most_common_count}/{total_types}个事件是"
                        f"'{most_common_type}'类型，事件类型过于单调",
                suggestion="增加不同类型的事件（如职业、家庭、社交、健康等维度）"
            ))

    def _check_life_stage_coverage(self, story: LifeStory):
        """D1-003：人生关键阶段覆盖缺失"""
        for min_age, max_age, stage_name in self.LIFE_STAGES:
            events_in_stage = [
                e for e in story.events if min_age <= e.age <= max_age
            ]
            if not events_in_stage and story.character.birth_year:
                # 检查人物是否活到了这个阶段
                death_year = story.character.death_year
                birth_year = story.character.birth_year
                stage_end_year = birth_year + max_age
                if death_year and stage_end_year > death_year:
                    continue  # 人物未活到该阶段，不算缺失
                if story.events and stage_end_year < story.events[-1].year:
                    # 故事跨度覆盖了该阶段但无事件
                    self.issues.append(Issue(
                        code="D1-003", severity=Severity.MINOR,
                        message=f"人生阶段'{stage_name}'({min_age}-{max_age}岁)"
                                f"无任何事件记录",
                        suggestion=f"在{min_age}-{max_age}岁阶段增加至少1个关键事件"
                    ))

    def _check_crisis_fatigue(self, story: LifeStory):
        """D1-004：危机疲劳（连续负面事件过多）"""
        NEGATIVE_KEYWORDS = [
            "失业", "离婚", "破产", "死亡", "丧", "受伤", "生病",
            "入狱", "失败", "被骗", "损失", "灾难", "事故", "背叛",
        ]
        POSITIVE_KEYWORDS = [
            "结婚", "生子", "升职", "获奖", "成功", "康复", "团聚",
            "收获", "买到", "实现", "达成",
        ]

        consecutive_negative = 0
        max_consecutive_negative = 0
        total_negative = 0
        total_positive = 0

        for e in story.events:
            is_negative = any(kw in e.event_type or kw in e.description
                             for kw in NEGATIVE_KEYWORDS)
            is_positive = any(kw in e.event_type or kw in e.description
                             for kw in POSITIVE_KEYWORDS)

            if is_negative:
                consecutive_negative += 1
                total_negative += 1
                max_consecutive_negative = max(max_consecutive_negative, consecutive_negative)
            elif is_positive:
                consecutive_negative = 0
                total_positive += 1
            else:
                consecutive_negative = 0

        # 如果连续5个以上负面事件
        if max_consecutive_negative >= 5:
            self.issues.append(Issue(
                code="D1-004", severity=Severity.MINOR,
                message=f"故事中最多连续{max_consecutive_negative}个负面事件，"
                        f"可能造成'危机疲劳'",
                suggestion="在连续负面事件之间插入中性或正面事件作为缓冲"
            ))

        # 如果负面:正面比例过于悬殊
        total = total_negative + total_positive
        if total >= 5:
            neg_ratio = total_negative / total
            if neg_ratio > 0.8:
                self.issues.append(Issue(
                    code="D1-004", severity=Severity.MINOR,
                    message=f"故事中负面事件占比{neg_ratio * 100:.0f}%，"
                            f"正面事件仅{total_positive}个，比例过于悬殊",
                    suggestion="增加1-2个正面事件，使故事节奏更有起伏"
                ))

    def _check_density_unevenness(self, story: LifeStory):
        """D1-005：人生阶段事件密度极度不均"""
        if len(story.events) < 10:
            return

        # 按人生阶段统计事件数
        stage_densities = {}
        for min_age, max_age, stage_name in self.LIFE_STAGES:
            events_in_stage = [
                e for e in story.events if min_age <= e.age <= max_age
            ]
            stage_span = max_age - min_age + 1
            if events_in_stage:
                density = len(events_in_stage) / stage_span
                stage_densities[stage_name] = density

        if len(stage_densities) >= 2:
            max_density = max(stage_densities.values())
            min_density = min(stage_densities.values())
            if max_density > 0 and min_density > 0:
                ratio = max_density / min_density
                if ratio > 10:  # 最密集阶段是最稀疏阶段的10倍以上
                    densest = max(stage_densities, key=stage_densities.get)
                    sparsest = min(stage_densities, key=stage_densities.get)
                    self.issues.append(Issue(
                        code="D1-005", severity=Severity.MINOR,
                        message=f"人生阶段事件密度极度不均：'{densest}'最密集，"
                                f"'{sparsest}'最稀疏，密度比{ratio:.1f}:1",
                        suggestion=f"在'{sparsest}'阶段增加事件，或在'{densest}'阶段精简"
                    ))


# =====================================================================
# 主检测器：串联所有通用检测器
# =====================================================================

class UniversalStoryDetector:
    """
    通用人生故事检测器 v2.0（独立模块）

    不依赖任何特定社会结构理论，
    仅基于逻辑、常识、普遍人性和叙事规律进行检测。
    可作为 story_validator.py 的前置检测模块使用。

    检测维度（11个）：
      L  - 逻辑一致性
      T  - 时间现实性
      P  - 心理常识性
      R  - 资源常识性
      N  - 叙事常识性
      G  - 地理空间常识性     ★ v2.0新增
      H  - 生理健康常识性     ★ v2.0新增
      C  - 人物关系连续性     ★ v2.0新增
      E  - 事件序列逻辑性     ★ v2.0新增
      K  - 知识与文化常识性   ★ v2.0新增
      D  - 故事节奏与密度     ★ v2.0新增
    """

    def __init__(self):
        self.detectors = [
            ("逻辑一致性", LogicCommonSenseDetector()),
            ("时间现实性", TemporalCommonSenseDetector()),
            ("心理常识性", PsychologicalCommonSenseDetector()),
            ("资源常识性", ResourceCommonSenseDetector()),
            ("叙事常识性", NarrativeCommonSenseDetector()),
            ("地理空间常识性", GeographicCommonSenseDetector()),
            ("生理健康常识性", HealthCommonSenseDetector()),
            ("人物关系连续性", RelationshipContinuityDetector()),
            ("事件序列逻辑性", EventSequenceDetector()),
            ("知识与文化常识性", KnowledgeCulturalDetector()),
            ("故事节奏与密度", StoryPacingDetector()),
        ]

    def detect(self, story: LifeStory) -> DetectionResult:
        """运行所有通用检测器，汇总结果"""
        all_issues: List[Issue] = []
        for name, detector in self.detectors:
            if hasattr(detector, 'detect'):
                result = detector.detect(story)
                all_issues.extend(result.issues)
        return DetectionResult(issues=all_issues)

    def detect_and_report(self, story: LifeStory) -> str:
        """检测并生成报告"""
        result = self.detect(story)
        return result.report()

    def detect_by_dimension(self, story: LifeStory, dimension: str) -> DetectionResult:
        """仅运行指定维度的检测器"""
        for name, detector in self.detectors:
            if dimension.lower() in name.lower():
                return detector.detect(story)
        return DetectionResult(issues=[])


# =====================================================================
# 与 story_validator.py 的对接说明
# =====================================================================

"""
对接方式：

1. 独立使用（仅检测通用问题）：
   ─────────────────────────────────────────────
   from universal_story_validator import UniversalStoryDetector, LifeStory, LifeEvent
   
   detector = UniversalStoryDetector()
   result = detector.detect(story)
   print(result.report())
   
   # 也可只跑特定维度
   result = detector.detect_by_dimension(story, "地理")
   ─────────────────────────────────────────────

2. 与 story_validator.py 串联使用（先通用后结构）：
   ─────────────────────────────────────────────
   from universal_story_validator import UniversalStoryDetector
   from story_validator import LifeStoryDetector
   
   # 第一步：通用检测
   universal = UniversalStoryDetector()
   universal_result = universal.detect(story)
   
   if not universal_result.passed:
       print("通用检测未通过，请先修改致命问题：")
       print(universal_result.report())
   
   # 第二步：社会结构特异性检测
   structural = LifeStoryDetector()
   structural_result = structural.detect(story)
   print(structural_result.report())
   ─────────────────────────────────────────────

3. 按维度分类汇总：
   ─────────────────────────────────────────────
   result = UniversalStoryDetector().detect(story)
   by_dim = result.issues_by_dimension()
   for dim, issues in by_dim.items():
       print(f"{dim}: {len(issues)}个问题")
   ─────────────────────────────────────────────
"""


# =====================================================================
# 使用示例
# =====================================================================

def example_usage():
    character = Character(
        id="char_001", name="测试人物", birth_year=1970,
        gender="女", skills=["种植", "做饭"],
    )

    events = [
        LifeEvent(
            index=0, year=1970, age=0, character_id="char_001",
            event_type="出生", description="人物出生。",
        ),
        LifeEvent(
            index=1, year=1975, age=5, character_id="char_001",
            event_type="入学", description="上了小学。",
        ),
        LifeEvent(
            index=2, year=1985, age=15, character_id="char_001",
            event_type="结婚", description="突然决定结婚，因为觉得自己想结。",
            # 问题：15岁结婚偏低；"突然决定"缺乏动机
        ),
        LifeEvent(
            index=3, year=1985, age=15, character_id="char_001",
            event_type="生子", description="当年就生了孩子。",
            # 问题：结婚到生子间隔为0
        ),
        LifeEvent(
            index=4, year=1990, age=20, character_id="char_001",
            event_type="退休", description="退休了。",
            # 问题：20岁退休不合理
        ),
        LifeEvent(
            index=5, year=1992, age=22, character_id="char_001",
            event_type="上网", description="用微信和朋友聊天。",
            # 问题：1992年中国还没有互联网和微信
        ),
        LifeEvent(
            index=6, year=1995, age=25, character_id="char_001",
            event_type="生子", description="又生了一个孩子。",
            # 问题：此前结婚→离婚→再婚？无离婚记录直接再婚
        ),
    ]

    story = LifeStory(character=character, events=events)

    detector = UniversalStoryDetector()
    report = detector.detect_and_report(story)
    print(report)


if __name__ == "__main__":
    example_usage()
