"""
人生事件生成引擎 V4
彻底修复：已发生事件概率=0，严格按社会规则
"""
import yaml
import os
import random
from typing import Dict, List, Any, Optional, Set
from .structure_engine import StructureEngine
from .character_gen import CharacterGenerator
from .social_rules import SocialRulesEngine


class LifeGenerator:
    """人生事件生成引擎 V4"""

    # ── 出生地→事件类别兼容性映射 ──────────────────────────────
    # key: 出生地ID (rural/small_town/medium_city/large_city/capital_city)
    # value: 该出生地允许出现的事件类别集合
    # 不在集合中的类别仍可能出现（通用事件），但以下标记为"需要特定背景"的类别
    # 会被限制在对应的出生地范围内
    #
    # 设计原则：
    #   - mechanical_solidarity（机械团结/部落社会）→ 仅限农村/乡镇
    #     理由：大城市2000年后出生的角色不可能经历"部落命名仪式"
    #   - rural_china（乡土中国）→ 仅限农村/乡镇
    #     理由：做三朝/满月酒/媒人说亲等是乡土社会特有仪式
    #   - 其他结构（有机团结/大都市/陌生人/风险社会等）→ 所有出生地均可
    #     理由：这些是现代/后现代社会的特征，各地都可能体验
    _PLACE_CATEGORY_COMPATIBILITY: Dict[str, set] = {
        "rural":       {"mechanical_solidarity", "rural_china"},
        "small_town":  {"mechanical_solidarity", "rural_china"},
        "medium_city": set(),  # 中小城市：不限制任何类别
        "large_city":  set(),  # 大城市：不允许部落/乡土类事件
        "capital_city": set(), # 超大城市：同上
    }

    # 需要特定出生地背景才能触发的类别（即"不兼容城市"的类别）
    _CONTEXT_SENSITIVE_CATEGORIES = {"mechanical_solidarity", "rural_china"}

    # ── 出生地→事件ID级别排除（细粒度） ──────────────────────
    # 某些事件即使类别被允许，也需要进一步根据出生地过滤
    # 例如：rural_china 中的 "rural_birth_feast" 在农村/乡镇合适，
    # 但 mechanical_solidarity 的 "mech_birth_ritual"（部落命名仪式）
    # 即使选了机械团结，也应该用现代化表述而非字面部落意象
    _PLACE_EVENT_EXCLUSIONS: Dict[str, set] = {
        # 大城市/超大城市出生 → 排除字面上的部落/原始社会事件
        "large_city": {
            "mech_birth_ritual",          # 部落命名仪式
            "mech_child_collective_ritual", # 部落集体仪式
            "mech_adult_ritual",          # 成年礼——经受痛苦考验
            "mech_witchcraft_accusation",  # 巫术/异端指控
            "mech_called_to_sacrifice",    # 被征召为集体牺牲
            "mech_elderly_sacrifice",      # 老年人主动自尽
            "mech_cowardice_shame",        # 因怯懦受社会性死亡
            "mech_honor_warrior",          # 为集体荣誉而战(部落战争)
            "mech_exile",                  # 被驱逐出社区(部落驱逐)
            "mech_collective_trial",       # 集体审判大会(部落审判)
        },
        "capital_city": {
            "mech_birth_ritual",
            "mech_child_collective_ritual",
            "mech_adult_ritual",
            "mech_witchcraft_accusation",
            "mech_called_to_sacrifice",
            "mech_elderly_sacrifice",
            "mech_cowardice_shame",
            "mech_honor_warrior",
            "mech_exile",
            "mech_collective_trial",
        },
    }

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        self.data_dir = data_dir
        self.events_data = self._load_events()
        self.structure_engine = StructureEngine(data_dir)
        self.character_gen = CharacterGenerator(data_dir)
        self.social_rules_engine = SocialRulesEngine(data_dir)

    def _load_events(self) -> Dict[str, Any]:
        events_path = os.path.join(self.data_dir, "events.yaml")
        with open(events_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data["life_events"]

    def generate_life_timeline(
        self,
        character: Dict[str, Any],
        selected_structure_ids: List[str],
        seed: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """生成人生时间线"""
        if seed is not None:
            random.seed(seed)

        timeline = []
        current_attrs = character["attributes"].copy()
        birth_year = character["birth_year"]
        birth_place = character.get("birth_place", "small_town")  # 出生地ID

        # 生成社会规则
        social_rules = self.social_rules_engine.generate_social_rules(selected_structure_ids)

        # 已发生事件ID集合
        occurred: Set[str] = set()

        # ── 基于出生地的事件类别过滤 ──────────────────────────
        # 获取该出生地允许的上下文敏感类别
        allowed_context_cats = self._PLACE_CATEGORY_COMPATIBILITY.get(birth_place, set())
        # 获取该出生地排除的具体事件ID
        excluded_event_ids = self._PLACE_EVENT_EXCLUSIONS.get(birth_place, set())

        # 跟踪教育进度（通过已发生事件判断）
        has_primary = False
        has_middle = False
        has_high = False
        has_university = False
        has_unmarried = False
        has_married = False
        has_first_job = False
        has_children = False

        # 按年龄遍历 0-85岁
        last_event_age = -10  # 冷却期追踪：上一次触发事件的年龄
        COOLDOWN_YEARS = 3    # 冷却期：普通事件触发后，接下来N年内只允许必发事件

        for age in range(0, 86):

            current_attrs["age"] = age

            # 收集该年龄可能发生的事件
            candidates = []

            categories = ["education", "career", "family", "social", "critical", "rural_traditional", "rural_china", "mechanical_solidarity", "organic_solidarity", "metropolis", "stranger_status", "risk_society", "rationalization", "disenchantment", "field_pressure_high", "cultural_capital_high", "cultural_capital_low", "disciplinary_power", "panopticism", "modern_urban", "risk_anxiety", "digital_surveillance"]
            for cat in categories:
                if cat not in self.events_data:
                    continue
                for evt in self.events_data[cat].get("events", []):
                    eid = evt.get("id", "")

                    # 跳过已发生事件
                    if eid in occurred:
                        continue

                    # ── 出生地上下文过滤：排除与角色背景不兼容的事件 ──
                    # 1. 类别级别过滤：上下文敏感类别需在允许列表中
                    if cat in self._CONTEXT_SENSITIVE_CATEGORIES and cat not in allowed_context_cats:
                        continue
                    # 2. 事件ID级别过滤：排除具体不兼容的事件
                    if eid in excluded_event_ids:
                        continue

                    # 检查年龄范围
                    age_range = evt.get("age_range", [0, 100])
                    if not (age_range[0] <= age <= age_range[1]):
                        continue

                    # 检查前置条件
                    if not self._check_prerequisites(
                        eid, age, social_rules, occurred,
                        has_primary, has_middle, has_high, has_university, has_unmarried, has_married, has_first_job
                    ):
                        continue

                    # 把category写进事件对象的副本（避免引用覆盖问题）
                    evt_copy = dict(evt)
                    evt_copy["category"] = cat

                    # 计算概率（已发生事件概率为0）
                    prob = self._calc_prob(
                        evt_copy, age, social_rules, occurred,
                        has_primary, has_middle, has_high, has_university, has_unmarried, has_married, has_first_job,
                        selected_structure_ids
                    )

                    if random.random() < prob:
                        candidates.append((eid, evt_copy))

            # 该年龄最多选择1个事件
            if candidates:
                # ---- 冷却期机制：距上次事件不足 COOLDOWN_YEARS 年时，只允许「必发事件」 ----
                in_cooldown = (age - last_event_age) < COOLDOWN_YEARS
                if in_cooldown:
                    # 必发事件 ID 集合（教育链、婚姻、生育、退休等人生里程碑）
                    MANDATORY_IDS = {
                        "enter_primary_school", "primary_school_graduation",
                        "enter_middle_school", "middle_school_graduation",
                        "enter_high_school", "high_school_graduation",
                        "take_college_entrance_exam", "college_enrollment", "college_graduation",
                        "marriage", "arranged_marriage",
                        "first_child_born", "second_child_born",
                        "retirement",
                    }
                    # 乡土中国必发事件链
                    RURAL_MANDATORY = {
                        "rural_wedding_matchmaker", "rural_wedding_ceremony",
                        "rural_birth_feast", "leave_village_work",
                        "return_to_home_village", "family_property_division",
                        "son_becomes_head",
                    }
                    MANDATORY_IDS.update(RURAL_MANDATORY)

                    candidates = [c for c in candidates if c[0] in MANDATORY_IDS]

                if not candidates:
                    continue

                # ---- 结构专属事件优先保障：选中某结构时，优先从该结构事件中选 ----
                struct_candidates = []
                for struct_id in ["rural_china", "mechanical_solidarity", "organic_solidarity", "metropolis", "stranger_status", "risk_society", "rationalization", "disenchantment", "field_pressure_high", "cultural_capital_high", "cultural_capital_low", "disciplinary_power", "panopticism"]:
                    if struct_id in selected_structure_ids:
                        struct_candidates = [c for c in candidates if c[1].get("category") == struct_id]
                        if struct_candidates:
                            break

                # 优先从结构专属事件中选，否则从所有候选事件中选
                if struct_candidates:
                    chosen = random.choice(struct_candidates)
                else:
                    chosen = random.choice(candidates)

                last_event_age = age  # 更新冷却期起始点

                eid, evt = chosen
                event_category = evt.get("category", "unknown")
                event = {
                    "id": eid,
                    "name": evt.get("name", "未知"),
                    "description": evt.get("description", ""),
                    "age": age,
                    "year": birth_year + age,
                    "action_emoji": "📋",
                    "sociological_reading": evt.get("sociological_reading", ""),
                    "outcomes": evt.get("outcomes", {}),
                    "category": event_category
                }
                timeline.append(event)
                occurred.add(eid)

                # 更新属性
                if "outcomes" in evt:
                    current_attrs = self._apply_outcomes(current_attrs, evt["outcomes"])

                # ── 死亡终止检测：一旦触发死亡类事件，立即停止后续事件生成 ──
                _DEATH_ENDING_IDS = {
                    "mech_called_to_sacrifice",    # 被征召为集体牺牲
                    "mech_elderly_sacrifice",       # 老年人主动自尽
                    "org_lonely_death",             # 孤独终老
                }
                if eid in _DEATH_ENDING_IDS:
                    # 标记此事件为"终结事件"
                    event["is_terminal"] = True
                    break

                # 更新教育/婚姻/工作进度
                if eid == "enter_primary_school":
                    has_primary = True
                elif eid == "enter_middle_school":
                    has_middle = True
                elif eid == "enter_high_school":
                    has_high = True
                elif eid == "college_enrollment":
                    has_university = True
                elif eid in ["marriage", "arranged_marriage"]:
                    has_married = True
                elif eid in ["first_job", "first_internship"]:
                    has_first_job = True
                elif eid in ["first_child_born", "second_child_born"]:
                    has_children = True

        # 按年龄排序
        timeline.sort(key=lambda x: x["age"])

        # ---- 保底机制：选中乡土社会时，至少触发一个乡土事件 ----
        if "rural_china" in selected_structure_ids:
            rural_events_in_timeline = [e for e in timeline if e.get("category") == "rural_china"]
            if not rural_events_in_timeline:
                # 强制从乡土事件库中选一个符合条件的插入
                forced_event = self._get_forced_rural_event(timeline, social_rules, occurred)
                if forced_event:
                    timeline.append(forced_event)
                    timeline.sort(key=lambda x: x["age"])

        return timeline

    def _get_forced_rural_event(
        self,
        timeline: List[Dict],
        social_rules: Dict,
        occurred: Set[str]
    ) -> Optional[Dict]:
        """当没有乡土事件时，强制获取一个可插入的乡土事件"""
        import random as rnd
        if not timeline:
            # 时间线为空时回退到默认出生年
            birth_year = 1995
        else:
            birth_year = timeline[0].get("year", 1995) - timeline[0].get("age", 0)

        candidates: List[tuple] = []
        for evt in self.events_data.get("rural_china", {}).get("events", []):
            eid = evt.get("id", "")
            if eid in occurred:
                continue
            # 检查前置条件
            if not self._check_prerequisites(
                eid, 0, social_rules, occurred,
                False, False, False, False, False, False, False
            ):
                continue
            # 取事件定义中第一个合法年龄
            age_range = evt.get("age_range", [20, 60])
            age = rnd.randint(age_range[0], age_range[1])
            candidates.append((eid, evt, age))

        if not candidates:
            return None

        eid, evt, age = rnd.choice(candidates)
        return {
            "id": eid,
            "name": evt.get("name", "未知"),
            "description": evt.get("description", ""),
            "age": age,
            "year": birth_year + age,
            "action_emoji": "📋",
            "sociological_reading": evt.get("sociological_reading", ""),
            "outcomes": evt.get("outcomes", {}),
            "category": "rural_china"
        }

    def _check_prerequisites(
        self,
        eid: str,
        age: int,
        social_rules: Dict,
        occurred: Set[str],
        has_primary: bool,
        has_middle: bool,
        has_high: bool,
        has_university: bool,
        has_unmarried: bool,
        has_married: bool,
        has_first_job: bool
    ) -> bool:
        """检查前置条件"""
        edu = social_rules.get("education", {})
        work = social_rules.get("work", {})
        marriage = social_rules.get("marriage", {})

        # 教育事件前置
        education_chain = {
            "enter_middle_school": has_primary,
            "middle_school_graduation": has_middle,
            "enter_high_school": has_middle,  # 如果middle_years=0，则初中毕业=小学毕业
            "high_school_graduation": has_high,
            "take_college_entrance_exam": has_high,
            "college_enrollment": has_high,  # 高考后录取
            "college_graduation": has_university,
            "enter_graduate_school": has_university,
        }

        if eid in education_chain:
            if not education_chain[eid]:
                return False

        # 高考必须先完成高中
        if eid == "take_college_entrance_exam" and not has_high:
            return False

        # 大学入学必须先参加高考
        if eid == "college_enrollment" and not has_high:
            return False

        # 婚姻事件
        if eid in ["marriage", "arranged_marriage"]:
            legal_age = marriage.get("legal_age", 22)
            if age < legal_age:
                return False

        # 子女事件需要先结婚
        if eid in ["first_child_born", "second_child_born"]:
            if not has_married:
                return False
            legal_age = marriage.get("legal_age", 22)
            if age < legal_age + 2:
                return False

        # 工作事件
        if eid in ["first_job", "first_internship"]:
            min_age = work.get("min_age", 16)
            if age < min_age:
                return False

        # 退休事件
        if eid == "retirement":
            retirement_age = work.get("retirement_age", 60)
            if age < retirement_age:
                return False

        # 同居需要先谈恋爱
        if eid == "cohabitation":
            if "falling_in_love" not in occurred and "first_love" not in occurred:
                return False

        # 孩子上学需要先生育
        if eid == "child_start_school":
            if "first_child_born" not in occurred:
                return False
            # 孩子通常6-7岁上学
            if age < 30:  # 假设30岁前有孩子，上学年龄30+
                return False

        # 孩子高考需要孩子先上学
        if eid == "child_college_entrance":
            if "child_start_school" not in occurred:
                return False

        # 子女离家需要先生育，且子女已长大
        if eid == "children_leave_home":
            if "first_child_born" not in occurred:
                return False
            # 子女通常18-25岁离家
            if age < 45:
                return False

        # 父母去世通常在50岁之后
        if eid == "parents_pass_away":
            if age < 45:
                return False

        # 退休后再就业需要先退休
        if eid == "reemployment_after_retirement":
            if "retirement" not in occurred:
                return False

        # 乡土中国事件前置条件
        # 媒人上门说亲后才能举办婚礼
        if eid == "rural_wedding_ceremony":
            if "rural_wedding_matchmaker" not in occurred:
                return False

        # 举办婚礼后才能考虑分家析产
        if eid == "family_property_division":
            if "rural_wedding_ceremony" not in occurred:
                return False

        # 分家后长子才能当家
        if eid == "son_becomes_head":
            if "family_property_division" not in occurred:
                return False

        # 外出谋生后才能有叶落归根
        if eid == "return_to_home_village":
            if "leave_village_work" not in occurred:
                return False

        # 过继/收养需要先结婚
        if eid == "parents_arrange_adoption":
            if "rural_wedding_ceremony" not in occurred:
                return False

        return True

    def _calc_prob(
        self,
        evt: Dict,
        age: int,
        social_rules: Dict,
        occurred: Set[str],
        has_primary: bool,
        has_middle: bool,
        has_high: bool,
        has_university: bool,
        has_unmarried: bool,
        has_married: bool,
        has_first_job: bool,
        selected_structure_ids: List[str]
    ) -> float:
        """计算事件概率"""
        eid = evt.get("id", "")
        base = evt.get("weight", 0.5)

        # ---- 社会结构亲和性加权 ----
        # 当选中某社会结构时，提高该结构对应事件类别的概率
        cat = evt.get("category", "")
        structure_boost_map = {
            "rural_china":       "rural_china",
            "rural_traditional": "rural_china",
            "mechanical_solidarity": "mechanical_solidarity",
            "organic_solidarity":    "organic_solidarity",
            "rationalization":       "rationalization",
            "disenchantment":         "disenchantment",
            "field_pressure_high":    "field_pressure_high",
            "cultural_capital_high":  "cultural_capital_high",
            "cultural_capital_low":   "cultural_capital_low",
            "disciplinary_power":    "disciplinary_power",
            "panopticism":            "panopticism",
            "rural_china":            "rural_china",
            "metropolis":             "metropolis",
            "stranger_status":        "stranger_status",
            "risk_society":            "risk_society",
        }
        boost_key = structure_boost_map.get(cat, cat)
        if boost_key in selected_structure_ids:
            base *= 3.5   # 选中对应结构时，该类事件概率提升3.5倍
        elif cat in structure_boost_map.values():
            # 该类别是结构专属事件，但选中结构列表中不含对应结构 → 概率归零，完全排除
            return 0.0

        edu = social_rules.get("education", {})
        work = social_rules.get("work", {})
        marriage = social_rules.get("marriage", {})

        # 已发生事件概率为0
        if eid in occurred:
            return 0.0

        # 小学入学：8岁（乡土社会）
        if eid == "enter_primary_school":
            school_start = edu.get("school_start_age", 6)
            if age == school_start:
                return base * 0.95
            elif age < school_start:
                return 0.0
            else:
                return base * 0.05  # 延迟入学

        # 小学毕业
        if eid == "primary_school_graduation":
            school_start = edu.get("school_start_age", 6)
            primary_years = edu.get("primary_years", 6)
            grad_age = school_start + primary_years
            if age == grad_age:
                return base * 0.95
            elif age < grad_age:
                return 0.0
            else:
                return base * 0.02

        # 进入初中（如果没有初中阶段，则跳过）
        if eid == "enter_middle_school":
            middle_years = edu.get("middle_years", 3)
            if middle_years == 0:
                return 0.0  # 没有初中阶段
            school_start = edu.get("school_start_age", 6)
            primary_years = edu.get("primary_years", 6)
            enter_age = school_start + primary_years
            if age == enter_age:
                return base * 0.95
            elif age < enter_age:
                return 0.0
            else:
                return base * 0.02

        # 初中毕业
        if eid == "middle_school_graduation":
            middle_years = edu.get("middle_years", 3)
            if middle_years == 0:
                return 0.0
            school_start = edu.get("school_start_age", 6)
            primary = edu.get("primary_years", 6)
            grad_age = school_start + primary + middle_years
            if age == grad_age:
                return base * 0.95
            elif age < grad_age:
                return 0.0
            else:
                return base * 0.02

        # 进入高中
        if eid == "enter_high_school":
            middle_years = edu.get("middle_years", 3)
            school_start = edu.get("school_start_age", 6)
            primary = edu.get("primary_years", 6)
            enter_age = school_start + primary + middle_years
            if age == enter_age:
                return base * 0.9
            elif age < enter_age:
                return 0.0
            else:
                return base * 0.02

        # 高中毕业/高考
        if eid in ["high_school_graduation", "take_college_entrance_exam"]:
            middle = edu.get("middle_years", 3)
            high = edu.get("high_years", 3)
            school_start = edu.get("school_start_age", 6)
            grad_age = school_start + edu.get("primary_years", 6) + middle + high
            if age == grad_age:
                return base * 0.95
            elif age < grad_age:
                return 0.0
            else:
                return base * 0.02

        # 大学录取
        if eid == "college_enrollment":
            middle = edu.get("middle_years", 3)
            high = edu.get("high_years", 3)
            school_start = edu.get("school_start_age", 6)
            entrance_age = school_start + edu.get("primary_years", 6) + middle + high
            if age == entrance_age:
                return base * 0.7
            elif age < entrance_age:
                return 0.0
            else:
                return base * 0.02

        # 大学入学后毕业
        if eid == "college_graduation":
            if not has_university:
                return 0.0
            university_years = edu.get("university_years", 4)
            middle = edu.get("middle_years", 3)
            high = edu.get("high_years", 3)
            school_start = edu.get("school_start_age", 6)
            grad_age = school_start + edu.get("primary_years", 6) + middle + high + university_years
            if age == grad_age:
                return base * 0.95
            elif age < grad_age:
                return 0.0
            else:
                return base * 0.02

        # 第一份工作
        if eid in ["first_job", "first_internship"]:
            typical = work.get("typical_first_job", 18)
            min_age = work.get("min_age", 16)
            if age >= min_age:
                if age == typical:
                    return base * 0.8
                elif age > typical:
                    return base * 0.2
                else:
                    return base * 0.05
            return 0.0

        # 退休
        if eid == "retirement":
            ret_age = work.get("retirement_age", 60)
            if age == ret_age:
                return base * 0.9
            elif age < ret_age:
                return 0.0
            else:
                return base * 0.3

        # 婚姻
        if eid in ["marriage", "arranged_marriage"]:
            legal = marriage.get("legal_age", 22)
            if age >= legal:
                if age <= legal + 5:
                    return base * 0.4
                elif age <= legal + 15:
                    return base * 0.2
                else:
                    return base * 0.05
            return 0.0

        # 子女出生
        if eid in ["first_child_born", "second_child_born"]:
            legal = marriage.get("legal_age", 22)
            if age >= legal + 2 and age <= legal + 15:
                return base * 0.3
            elif age > legal + 15:
                return base * 0.05
            return 0.0

        # 孩子上学需要先有孩子
        if eid == "child_start_school":
            if "first_child_born" not in occurred:
                return 0.0
            # 孩子6-7岁上学，所以父母通常30-35岁
            if 30 <= age <= 40:
                return base * 0.5
            return 0.0

        # 子女离家
        if eid == "children_leave_home":
            if "first_child_born" not in occurred:
                return 0.0
            # 子女18-25岁离家
            if age >= 45:
                return base * 0.3
            return 0.0

        # ---- 乡土中国事件的特殊概率 ----
        # 做三朝/满月酒：只能在婴儿1岁前发生
        if eid == "rural_birth_feast":
            if age == 0:
                return base * 0.9
            return 0.0

        # 媒人上门说亲 → 婚礼：必须先媒人说亲才能办婚礼
        if eid == "rural_wedding_ceremony":
            if "rural_wedding_matchmaker" in occurred:
                if 16 <= age <= 28:
                    return base * 0.9
            return 0.0

        if eid == "rural_wedding_matchmaker":
            if "rural_wedding_ceremony" in occurred:
                return 0.0  # 婚礼已办过不再重复说亲

        # 分家析产后才轮到长子当家
        if eid == "son_becomes_head":
            if "family_property_division" not in occurred:
                return 0.0
            if 50 <= age <= 70:
                return base * 0.6
            return 0.0

        # 购置田地与卖地互斥（买了不再卖地，或卖了可再买）
        if eid == "land_purchase":
            if age < 25 or age > 50:
                return 0.0
            return base * 0.4

        if eid == "land_sale_under_pressure":
            if age < 25 or age > 60:
                return 0.0
            return base * 0.3

        # 叶落归根：必须先外出谋生才能回乡
        if eid == "return_to_home_village":
            if "leave_village_work" not in occurred:
                return 0.0
            if 45 <= age <= 75:
                return base * 0.5
            return 0.0

        # 外出谋生：年纪大了不再外出
        if eid == "leave_village_work":
            if age < 16 or age > 30:
                return 0.0
            return base * 0.35

        # 默认概率（降低整体概率，减少事件数量）
        return base * 0.15

    def _apply_outcomes(
        self,
        attrs: Dict[str, float],
        outcomes: Dict[str, tuple]
    ) -> Dict[str, float]:
        """应用事件结果"""
        new_attrs = attrs.copy()

        # 键名映射：事件 YAML 中的旧键 → 统一属性名
        key_aliases = {
            "health_level": "health",
        }

        # 0~1 范围属性（百分比型）
        zero_one_attrs = {
            "stress_level", "anomie_level", "field_pressure",
            "surveillance_level", "social_isolation",
            "health", "social_status", "wealth",
            "risk_exposure", "blasé_attitude", "objectification",
            "community_integration", "face_consciousness",
            "guanxi_dependence", "individualization",
            "emotional_stability", "information_overload",
            "impression_management", "field_pressure_high",
        }

        for attr, change_range in outcomes.items():
            # 统一键名
            mapped_attr = key_aliases.get(attr, attr)

            min_c, max_c = change_range
            change = random.uniform(min_c, max_c)
            old_val = new_attrs.get(mapped_attr, 0.0)

            if mapped_attr == "education_level":
                new_attrs[mapped_attr] = max(0.0, min(7.0, old_val + change))
            elif mapped_attr in zero_one_attrs:
                new_attrs[mapped_attr] = max(0.0, min(1.0, old_val + change))
            else:
                new_attrs[mapped_attr] = max(-1.0, min(1.0, old_val + change))

        return new_attrs

    def generate_timeline_with_visualization(
        self,
        character: Dict[str, Any],
        selected_structure_ids: List[str],
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """生成带可视化的时间线"""
        timeline = self.generate_life_timeline(
            character, selected_structure_ids, seed
        )
        return {
            "timeline": timeline,
            "metadata": {"total": len(timeline)}
        }