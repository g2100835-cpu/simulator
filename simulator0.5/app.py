"""
社会学人生模拟器 v4 - 主应用
基于经典社会学理论的互动人生模拟游戏

v4 更新：
- 修复选双结构报错（空时间线防护 + 预设ID解析加固）
- 健康状况/社会地位/财富动态计算（随事件推进实时变化）
- 嵌入 structure_network.html 交互关系图
"""
import os
import sys
import random
from datetime import date

import streamlit as st
import yaml

# ── 路径设置 ─────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

sys.path.insert(0, BASE_DIR)
from modules.structure_engine import StructureEngine
from modules.character_gen import CharacterGenerator
from modules.life_generator import LifeGenerator
from modules.timeline import TimelineRenderer
from modules.social_rules import SocialRulesEngine

import requests as _req

# =====================================================================
# DeepSeek 故事生成（最便宜模型 deepseek-v3-flash）
# =====================================================================
# API Key 安全读取优先级：
#   1. 环境变量 DEEPSEEK_API_KEY
#   2. 项目根目录 .env 文件中的 DEEPSEEK_API_KEY=xxx
#   3. Streamlit secrets（st.secrets["DEEPSEEK_API_KEY"]）
# 请勿将 Key 硬编码在源码中。

def _load_api_key() -> str:
    # 1. 环境变量
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        return key
    # 2. .env 文件（简单解析，无需 python-dotenv）
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as _f:
            for line in _f:
                line = line.strip()
                if line.startswith("DEEPSEEK_API_KEY"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        return parts[1].strip().strip('"').strip("'")
    # 3. Streamlit secrets
    try:
        return st.secrets.get("DEEPSEEK_API_KEY", "")
    except Exception:
        return ""

_DEEPSEEK_BASE  = "https://api.deepseek.com"
_DEEPSEEK_MODEL = "deepseek-v4-flash"   # 最便宜的模型


def _call_deepseek(system_prompt: str, user_prompt: str, max_tokens: int = 2000, temperature: float = 0.7) -> str:
    """通用 DeepSeek API 调用，返回文本内容。失败时返回 None。"""
    api_key = _load_api_key()
    if not api_key:
        return None
    try:
        payload = {
            "model": _DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            # 禁用 thinking 模式，否则所有 token 都花在推理上，content 为空
            "thinking": {"type": "disabled"},
        }
        resp = _req.post(
            f"{_DEEPSEEK_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"].get("content", "")
        # 如果 content 为空但 reasoning_content 不为空（thinking 模式意外开启）
        if not content:
            reasoning = data["choices"][0]["message"].get("reasoning_content", "")
            if reasoning:
                content = reasoning
        return content.strip() if content else None
    except Exception as e:
        st.warning(f"LLM 调用出错：{e}")
        return None


def optimize_events_with_llm(character: dict, timeline: list, structures: list) -> list:
    """
    用 DeepSeek 优化事件列表：让事件描述更连贯、更自然、更符合社会学逻辑。
    返回优化后的事件列表（原地修改 description 字段）。
    """
    if not timeline:
        return timeline

    struct_names = "、".join([s.get("name", s) if isinstance(s, dict) else str(s) for s in structures]) if structures else "无"

    events_text = ""
    for i, e in enumerate(sorted(timeline, key=lambda x: x.get("age", 0))):
        age = e.get("age", "?")
        name = e.get("name", "")
        desc = e.get("description", "")
        events_text += f"  [{i}] {age}岁：{name} — {desc}\n"

    system_prompt = (
        "你是社会学叙事优化师。优化人生事件列表的描述，使其更连贯自然。\n\n"
        "【原则】\n"
        "1. 保持事件核心含义和年龄不变\n"
        "2. 让因果链条更清晰\n"
        "3. 修复明显不合逻辑的描述\n"
        "4. 每个描述不超过50字\n\n"
        "【格式】每行：[序号] 优化后描述 | 优化后社会学解读"
    )

    user_prompt = (
        f"角色：{character.get('name', '')}，{character.get('gender', '')}，"
        f"出生于{character.get('birth_year', '')}年，结构：{struct_names}\n\n"
        f"事件：\n{events_text}\n请优化。"
    )

    result_text = _call_deepseek(system_prompt, user_prompt, max_tokens=2000, temperature=0.5)
    if not result_text:
        return timeline

    # 解析 LLM 返回的优化结果
    optimized_map = {}  # index -> (desc, reading)
    for line in result_text.split("\n"):
        line = line.strip()
        if not line or not line.startswith("["):
            continue
        try:
            bracket_end = line.index("]")
            idx = int(line[1:bracket_end])
            rest = line[bracket_end + 1:].strip()
            if "|" in rest:
                desc_part, reading_part = rest.split("|", 1)
                optimized_map[idx] = (desc_part.strip(), reading_part.strip())
            else:
                optimized_map[idx] = (rest.strip(), "")
        except (ValueError, IndexError):
            continue

    # 将优化结果应用到 timeline
    sorted_timeline = sorted(timeline, key=lambda x: x.get("age", 0))
    for idx, (desc, reading) in optimized_map.items():
        if 0 <= idx < len(sorted_timeline):
            if desc:
                sorted_timeline[idx]["description"] = desc
            if reading:
                sorted_timeline[idx]["sociological_reading"] = reading

    return timeline


def check_story_logic(character: dict, timeline: list) -> tuple:
    """
    用 DeepSeek 基于12个维度检查人生事件是否符合逻辑和常识。
    重点关注事件之间的因果衔接和前后连贯性，避免事件过于跳跃。
    第12维度(X)重点关注事件与角色背景（出生地/时代）的上下文一致性。
    返回 (is_logical: bool, issues: str, suggestions: str)
    """
    if not timeline:
        return True, "", ""

    # ── 本地快速预检：死亡后事件（无需等LLM，直接拦截） ─────
    sorted_tl = sorted(timeline, key=lambda x: x.get("age", 0))
    _DEATH_KEYWORDS_LOCAL = ["自尽", "自杀", "牺牲", "孤独终老", "社会性死亡"]
    _DEATH_IDS_LOCAL = {
        "mech_called_to_sacrifice", "mech_elderly_sacrifice", "org_lonely_death",
    }
    death_found = False
    for i, evt in enumerate(sorted_tl):
        if death_found:
            eid = evt.get("id", "")
            name = evt.get("name", "")
            # 发现死亡后的事件，立即返回不通过
            fatal = (
                f"致命逻辑错误：人物在{sorted_tl[i-1].get('age','?')}岁"
                f"发生[{sorted_tl[i-1].get('name','?')}]后，"
                f"{evt.get('age','?')}岁仍有事件[{name}]。"
                f"死亡/终结后不可能再有新事件。"
            )
            return False, fatal, "移除死亡后的所有后续事件"
        if (evt.get("id", "") in _DEATH_IDS_LOCAL or
            any(kw in evt.get("name", "") for kw in _DEATH_KEYWORDS_LOCAL)):
            death_found = True

    # ── 本地快速预检2：出生地与事件上下文不匹配 ──────────────
    birth_place = character.get("birth_place", "small_town")
    _TRIBAL_EVENT_KEYWORDS = ["部落", "巫术", "献祭", "长老行使", "集体审判大会", "被驱逐出社区"]
    _TRIBAL_EVENT_IDS = {
        "mech_birth_ritual", "mech_child_collective_ritual", "mech_adult_ritual",
        "mech_witchcraft_accusation", "mech_called_to_sacrifice",
        "mech_elderly_sacrifice", "mech_cowardice_shame", "mech_honor_warrior",
        "mech_exile", "mech_collective_trial",
    }
    # 大城市/超大城市出生 → 不允许出现部落/原始社会事件
    _URBAN_PLACES = {"large_city", "capital_city", "medium_city"}
    if birth_place in _URBAN_PLACES:
        for evt in sorted_tl:
            eid = evt.get("id", "")
            name = evt.get("name", "")
            if eid in _TRIBAL_EVENT_IDS or any(kw in name for kw in _TRIBAL_EVENT_KEYWORDS):
                fatal = (
                    f"致命逻辑错误：角色出生于{character.get('birth_place_display', birth_place)}，"
                    f"但{evt.get('age','?')}岁出现了[{name}]——"
                    f"现代社会城市出生的人不可能经历部落/原始社会特有事件。"
                )
                return False, fatal, "移除与角色出生地不兼容的部落/原始社会事件"

    events_text = ""
    for i, e in enumerate(sorted(timeline, key=lambda x: x.get("age", 0))):
        age = e.get("age", "?")
        name = e.get("name", "")
        desc = e.get("description", "")
        events_text += f"[{i}] {age}岁：{name}—{desc}\n"

    system_prompt = (
        "你是社会学人生模拟器的逻辑审查员，需要基于以下12个维度检查事件序列的逻辑连贯性，"
        "重点关注事件之间的因果关系和前后衔接，避免事件之间太过跳跃、缺乏过渡。\n\n"
        "【12个审查维度】\n"
        "L.逻辑一致性：因果是否颠倒？**死亡/自尽/牺牲/终老后是否还有事件？（这是最严重的错误，一旦发现必须不通过）** "
        "属性是否自相矛盾？是否存在循环因果？\n"
        "T.时间现实性：事件是否发生在不合理年龄段（入学6岁、工作>=16岁、退休>=55岁）？间隔是否过短？"
        "时间线是否有大段空白？\n"
        "P.心理常识性：性格变化是否有触发事件？行为是否有动机？创伤是否有持续影响？"
        "人物对极端事件是否无反应？\n"
        "R.资源常识性：资源枯竭后是否仍高消费？技能是否凭空出现？穷人是否突然暴富？"
        "无学历是否任高管？关键资源是否突然出现？\n"
        "N.叙事常识性：重大转折是否有铺垫？人物特征是否突然逆转？巧合是否过多？"
        "结局是否过于突兀？\n"
        "G.地理空间常识性：地理移动是否合理？空间距离是否被忽视？城乡转换是否自然？\n"
        "H.生理健康常识性：生理变化是否合理？疾病是否有后续影响？生育年龄是否合理（<=50岁）？"
        "健康变化是否有原因？\n"
        "C.人物关系连续性：关系变化是否有过程？重要人物是否突然消失或出现？"
        "婚姻/离婚/生育是否有前置条件？\n"
        "E.事件序列逻辑性：事件先后顺序是否合理？前置条件是否满足？"
        "入职后才能升职？结婚后才能离婚？教育阶段是否连贯？\n"
        "K.知识与文化常识性：文化背景是否正确？知识获取路径是否合理？时代背景是否有误？\n"
        "D.故事节奏与密度：事件密度是否合理？是否有大段时间空白？事件是否过于密集或稀疏？\n"
        "X.上下文一致性（最关键维度之一）：事件的社会学意象是否与角色背景严格匹配？\n"
        "  - 大城市/超大城市出生的角色是否出现了部落/原始社会特有事件？（如「部落命名仪式」「巫术指控」「被征召为集体牺牲」等）\n"
        "  - 现代社会（2000年后出生）是否出现了前现代社会特有事件？（如部落长老、献祭、割礼等）\n"
        "  - 选中的社会结构事件是否以符合角色背景的方式呈现？（同一理论可用不同方式体验）\n"
        "  - 出生在农村但已进城的人是否在后期仍有纯乡土事件？\n\n"
        "【⚠️ 致命问题（发现任一即判不通过）】\n"
        "1. 死亡/自尽/牺牲/孤独终老之后仍有其他事件（人物已死不可能再经历事件）\n"
        "2. 入学年龄严重偏差（<5岁或>8岁才上小学）\n"
        "3. 生理不可能（如>50岁生育、<10岁结婚）\n"
        "4. 事件顺序根本颠倒（先离婚后结婚、先毕业再入学）\n"
        "5. 事件之间过于跳跃，完全缺乏因果衔接\n"
        "6. 大城市/超大城市出生的现代人出现部落/原始社会特有事件（如部落命名仪式、巫术指控、集体献祭等）——这是社会学意象与角色背景的根本冲突\n\n"
        "【判断标准】\n"
        "- 有任何致命问题 → 不通过\n"
        "- X维度有严重不一致也判不通过（上下文不匹配是最严重的逻辑缺陷之一）\n"
        "- P/R/C维度有严重不一致也判不通过\n"
        "- N/G/K/D维度问题仅记录，不影响通过判定\n"
        "- 轻微不一致忽略\n\n"
        "输出格式（严格三行）：\n"
        "结果：通过/不通过\n"
        "致命问题：[逐条简述；无写'无']\n"
        "其他问题：[逐条简述；无写'无']"
    )

    user_prompt = (
        f"角色：{character.get('name', '')}，{character.get('gender', '')}，"
        f"出生于{character.get('birth_year', '')}年，"
        f"出生地：{character.get('birth_place_display', character.get('birth_place', ''))}\n"
        f"事件序列：\n{events_text}\n"
        f"请按12维度逐一审查。**特别关注X维度（上下文一致性）**：如果角色出生在大城市/超大城市，"
        f"则不应出现部落命名仪式、巫术指控、集体献祭等原始社会特有事件。"
        f"同一社会学理论（如涂尔干的机械团结）可以通过不同的社会现象来体现，"
        f"不一定非要用字面的部落意象。重点检查事件之间的因果衔接和逻辑连贯性。"
    )

    result_text = _call_deepseek(system_prompt, user_prompt, max_tokens=800, temperature=0.2)
    if not result_text:
        return True, "", ""

    is_logical = True
    fatal_issues = ""
    other_issues = ""

    for line in result_text.split("\n"):
        line = line.strip()
        if line.startswith("结果：") or line.startswith("结果:"):
            verdict = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            is_logical = "通过" in verdict and "不通过" not in verdict
        elif line.startswith("致命问题：") or line.startswith("致命问题:"):
            content = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            if content and content != "无":
                fatal_issues = content.replace("；", "\n").replace(";", "\n")
        elif line.startswith("其他问题：") or line.startswith("其他问题:"):
            content = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            if content and content != "无":
                other_issues = content.replace("；", "\n").replace(";", "\n")

    # 合并问题
    all_issues = ""
    if fatal_issues:
        all_issues += fatal_issues
    if other_issues:
        if all_issues:
            all_issues += "\n"
        all_issues += "[其他] " + other_issues.replace("\n", "\n[其他] ")

    return is_logical, all_issues.strip(), ""


def generate_life_story(character: dict, timeline: list, structures: list) -> str:
    """
    用 DeepSeek 把离散事件列表改写成连续的自然段式人生故事。
    返回生成的故事文本（纯文字，无要点符号）。
    """
    api_key = _load_api_key()
    if not api_key:
        return (
            "（故事生成不可用：未配置 DEEPSEEK_API_KEY。\n"
            "请在项目根目录创建 .env 文件并写入：\n"
            "  DEEPSEEK_API_KEY=你的Key\n"
            "或设置环境变量 DEEPSEEK_API_KEY。）"
        )

    struct_names = "、".join([s.get("name", s) if isinstance(s, dict) else str(s) for s in structures]) if structures else "无"

    # 事件列表：只给事件名和描述，不强调年龄顺序，避免暗示流水账
    events_yaml = ""
    for e in sorted(timeline, key=lambda x: x.get("age", 0)):
        age = e.get("age", "?")
        name = e.get("name", "")
        desc = e.get("description", "")
        events_yaml += f"  - {age}岁：{name} — {desc}\n"

    system_prompt = (
        "你是一位兼具文学素养和社会学洞察的叙事写作者。"
        "将人生事件列表改写为文学质感的人生概述，不是流水账。\n\n"
        "【要求】\n"
        "1. 禁止出现具体年龄数字，用幼年/少年/青年/中年/暮年等代替\n"
        "2. 禁止使用括号，补充信息自然融入正文\n"
        "3. 禁止逐事件罗列，以主题或生命阶段概括叙述\n"
        "4. 体现个体与社会结构的关联：命运如何被时代/制度/阶层塑造\n"
        "5. 语调：冷静克制略带悲悯，避免煽情和学术腔\n"
        "6. 全文400~600字，一段或两段连续文字\n"
        "7. 直接输出正文，不加开场白"
    )

    user_prompt = (
        f"角色：{character.get('name', '')}，{character.get('gender', '')}，"
        f"出生于{character.get('birth_year', '')}年。社会结构：{struct_names}\n\n"
        f"事件：\n{events_yaml}\n"
        f"请写人生概述。"
    )

    result = _call_deepseek(system_prompt, user_prompt, max_tokens=1000, temperature=0.7)
    return result if result else "（故事生成失败：LLM 调用无返回）"





# =====================================================================
# 页面配置
# =====================================================================
st.set_page_config(
    page_title="社会学人生模拟器",
    page_icon="🎲",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =====================================================================
# 自定义样式 — 明亮主题
# =====================================================================
st.markdown("""
<style>
    /* ── 全局 ──────────────────────────────────────────────────── */
    html, body, .stApp {
        background-color: #f5f0eb;
        color: #2d3047;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* ── 标题区 ────────────────────────────────────────────────── */
    .main-title {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6c5ce7, #a29bfe, #74b9ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.1rem;
        letter-spacing: 0.05em;
    }
    .subtitle {
        font-size: 1rem;
        color: #636e72;
        margin-bottom: 1.8rem;
    }

    /* ── 欢迎页 ────────────────────────────────────────────────── */
    .welcome-box {
        background: linear-gradient(135deg, #dfe6e9, #f5f0eb);
        border-radius: 16px;
        padding: 2.5rem 3rem;
        margin: 1rem 0 2rem;
        border: 1px solid #d1ccc0;
    }
    .welcome-text {
        font-size: 1.05rem;
        color: #636e72;
        line-height: 1.9;
    }
    .welcome-text em {
        font-style: normal;
        color: #6c5ce7;
        font-weight: 600;
    }

    /* ── 卡片 ───────────────────────────────────────────────────── */
    .card {
        background: #ffffff;
        border: 1px solid #e0dcd6;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin: 0.8rem 0;
        box-shadow: 0 2px 8px rgba(45, 48, 71, 0.06);
        transition: box-shadow 0.2s, border-color 0.2s;
    }
    .card:hover {
        box-shadow: 0 4px 16px rgba(45, 48, 71, 0.12);
        border-color: #a29bfe;
    }
    .card-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #6c5ce7;
        margin-bottom: 0.6rem;
    }

    /* ── 事件卡片 ──────────────────────────────────────────── */
    .event-card {
        background: #ffffff;
        border-left: 4px solid #6c5ce7;
        border-radius: 0 10px 10px 0;
        padding: 1rem 1.2rem;
        margin: 0.6rem 0;
        box-shadow: 0 2px 8px rgba(45, 48, 71, 0.06);
        animation: fadeInUp 0.4s ease;
    }
    .event-age {
        font-size: 0.85rem;
        color: #6c5ce7;
        font-weight: 700;
    }
    .event-name {
        font-size: 1.1rem;
        font-weight: 700;
        color: #2d3047;
        margin: 0.2rem 0;
    }
    .event-desc {
        color: #555555;
        font-size: 0.9rem;
        line-height: 1.6;
    }
    .event-outcome {
        font-size: 0.8rem;
        color: #636e72;
        margin-top: 0.3rem;
        font-style: italic;
    }
    .event-reading {
        color: #e17055;
        font-size: 0.82rem;
        font-style: italic;
        margin-top: 0.4rem;
        padding-left: 0.6rem;
        border-left: 2px solid #fab1a0;
    }

    /* ── 模拟控制区 ──────────────────────────────────────────── */
    .sim-controls {
        background: #ffffff;
        border: 1px solid #e0dcd6;
        border-radius: 12px;
        padding: 1rem 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 8px rgba(45, 48, 71, 0.06);
    }
    .sim-year-display {
        font-size: 1.3rem;
        font-weight: 700;
        color: #6c5ce7;
    }

    /* ── 统计卡片 ──────────────────────────────────────────────── */
    .stat-card {
        background: #ffffff;
        border: 1px solid #e0dcd6;
        border-radius: 10px;
        padding: 1rem 0.5rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(45, 48, 71, 0.06);
    }
    .stat-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: #6c5ce7;
    }
    .stat-label {
        font-size: 0.78rem;
        color: #636e72;
        margin-top: 0.2rem;
    }
    .stat-change-up {
        font-size: 0.7rem;
        color: #27ae60;
        font-weight: 600;
    }
    .stat-change-down {
        font-size: 0.7rem;
        color: #e74c3c;
        font-weight: 600;
    }

    /* ── 指标进度条 ──────────────────────────────────────────── */
    .metric-bar-outer {
        width: 100%;
        height: 6px;
        background: #e0dcd6;
        border-radius: 3px;
        margin: 0.3rem 0;
        overflow: hidden;
    }
    .metric-bar-inner {
        height: 100%;
        border-radius: 3px;
        transition: width 0.5s ease;
    }

    /* ── 按钮 ──────────────────────────────────────────────────── */
    .stButton > button {
        background: linear-gradient(135deg, #6c5ce7, #a29bfe) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.5rem 2rem !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        transition: all 0.2s !important;
        box-shadow: 0 2px 8px rgba(108, 92, 231, 0.3) !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #5b4cdb, #8c7cf5) !important;
        box-shadow: 0 4px 16px rgba(108, 92, 231, 0.5) !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button:disabled {
        background: #d1ccc0 !important;
        box-shadow: none !important;
        color: #a0a0a0 !important;
    }

    /* ── 分隔线 ────────────────────────────────────────────────── */
    hr {
        border-color: #d1ccc0;
        margin: 1.5rem 0;
    }

    /* ── 侧边栏 ────────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: #ede8e3 !important;
        border-right: 1px solid #d1ccc0 !important;
    }

    /* ── 结构网络 iframe 容器 ─────────────────────────────────── */
    .network-container {
        background: #ffffff;
        border: 1px solid #e0dcd6;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(45, 48, 71, 0.06);
    }

    /* ── 检测报告样式 ──────────────────────────────────────────── */
    .issue-fatal {
        background: #fff0f0;
        border-left: 4px solid #e74c3c;
        border-radius: 0 8px 8px 0;
        padding: 0.7rem 1rem;
        margin: 0.4rem 0;
    }
    .issue-serious {
        background: #fff8eb;
        border-left: 4px solid #f39c12;
        border-radius: 0 8px 8px 0;
        padding: 0.7rem 1rem;
        margin: 0.4rem 0;
    }
    .issue-minor {
        background: #f0fff4;
        border-left: 4px solid #27ae60;
        border-radius: 0 8px 8px 0;
        padding: 0.7rem 1rem;
        margin: 0.4rem 0;
    }
    .issue-code {
        font-weight: 700;
        font-size: 0.85rem;
    }
    .issue-msg {
        color: #555555;
        font-size: 0.85rem;
        margin-top: 0.2rem;
    }
    .issue-suggestion {
        color: #636e72;
        font-size: 0.8rem;
        margin-top: 0.2rem;
        font-style: italic;
    }

    /* ── 动画 ──────────────────────────────────────────────────── */
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(10px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    /* ── 滑块样式 ─────────────────────────────────────────────── */
    input[type="range"] {
        accent-color: #6c5ce7;
    }

    /* ── 进度条容器（Streamlit 原生） ─────────────────────── */
    .stProgress > div > div > div {
        background: #6c5ce7 !important;
    }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# 初始化 session state
# =====================================================================
def init_session_state():
    # 清理之前版本可能残留的不可序列化对象
    if "page_container" in st.session_state:
        del st.session_state.page_container

    defaults = {
        "page": "welcome",
        "character": None,
        "full_timeline": None,
        "displayed_events": [],
        "current_age": 0,
        "simulation_done": False,
        "selected_structures": [],
        "life_result": None,
        "validator_result": None,
        "random_seed": random.randint(1, 999999),
        "generation_error": None,
        "needs_generation": False,       # 标记是否需要执行生成流程
        "generation_done": False,        # 标记生成是否已完成
        "generation_step": "",           # 当前生成步骤文字
        "gen_params": {},                # 生成所需参数缓存
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _scroll_to_top():
    """注入 JS 使页面滚动到顶部。"""
    import streamlit.components.v1 as components
    components.html(
        """<script>
        function stt() {
            try { window.parent.scrollTo(0, 0); } catch(e) {}
            try {
                var el = window.parent.document.querySelector('[data-testid="stMainBlockContainer"]');
                if (el) el.scrollTop = 0;
            } catch(e) {}
        }
        setTimeout(stt, 100);
        setTimeout(stt, 300);
        </script>""",
        height=0,
    )


def _clear_all_results():
    """清除所有生成结果相关的 session_state，用于重新模拟。
    保留 page/random_seed/_prev_page 以及 Streamlit widget key（以 struct_/tab/ 开头的）。
    """
    keep_prefixes = ("struct_", "tab_")  # Streamlit widget key 前缀
    keep_keys = {"page", "random_seed", "_prev_page"}
    for k in list(st.session_state.keys()):
        if k in keep_keys:
            continue
        if any(k.startswith(p) for p in keep_prefixes):
            continue
        st.session_state.pop(k, None)


def _remove_events_after_death(timeline: list) -> list:
    """
    安全网：检测死亡/终结类事件，移除其后的所有事件。
    匹配方式：事件ID + 事件名称关键词（双重保障）。
    """
    if not timeline:
        return timeline

    # 终结类事件 ID 集合
    _DEATH_IDS = {
        "mech_called_to_sacrifice",   # 被征召为集体牺牲
        "mech_elderly_sacrifice",      # 老年人主动自尽
        "org_lonely_death",            # 孤独终老
    }
    # 名称关键词（兜底：即使 ID 不在集合中，名称包含这些词也算）
    _DEATH_KEYWORDS = ["自尽", "自杀", "牺牲", "孤独终老", "社会性死亡"]

    death_idx = None
    for i, evt in enumerate(timeline):
        eid = evt.get("id", "")
        name = evt.get("name", "")
        # 双重匹配：ID 精确匹配 或 名称包含死亡关键词
        if eid in _DEATH_IDS or any(kw in name for kw in _DEATH_KEYWORDS):
            death_idx = i
            break

    if death_idx is not None and death_idx + 1 < len(timeline):
        removed = timeline[death_idx + 1:]
        removed_names = [e.get("name", "?") for e in removed]
        # 只保留到死亡事件为止
        timeline = timeline[:death_idx + 1]
        # 标记死亡事件
        timeline[death_idx]["is_terminal"] = True
        st.warning(
            f"⚠️ 已自动清理 {len(removed)} 个死亡后事件："
            f"{', '.join(removed_names)}"
        )

    return timeline


def cleanup_session_for_page(target_page: str):
    """切换页面前清理不应残留的 session_state 键，避免旧数据泄漏到新页面。"""
    # 结果页专属数据：离开结果页时清除
    result_only_keys = ["life_story", "logic_check", "validator_result"]
    # 模拟页专属数据：离开模拟页时清除
    simulate_only_keys = ["displayed_events", "current_age", "simulation_done",
                          "needs_generation", "generation_done", "generation_step", "gen_params"]

    if target_page in ("welcome", "setup"):
        # 回到首页/设置页时，清掉所有生成结果
        _clear_all_results()
    elif target_page == "simulate":
        # 进入模拟页时，清掉上一次的结果页数据
        for k in result_only_keys:
            st.session_state.pop(k, None)
    elif target_page == "result":
        # 进入结果页时，清掉模拟过程数据
        for k in simulate_only_keys:
            st.session_state.pop(k, None)


# =====================================================================
# 动态属性计算：将初始属性 + 已展示事件的 outcomes 叠加
# =====================================================================
def compute_current_attributes(character, displayed_events, full_timeline):
    """
    从角色初始属性出发，叠加所有「已展示」事件的 outcome 变化，
    返回当前状态字典。用于模拟推进页的动态指标展示。
    """
    if not character or "attributes" not in character:
        return {}

    # 深拷贝初始属性
    attrs = dict(character["attributes"])

    if not displayed_events or not full_timeline:
        return attrs

    sorted_timeline = sorted(full_timeline, key=lambda e: e.get("age", 0))

    # 键名映射：兼容事件 YAML 中的旧键
    key_aliases = {"health_level": "health"}

    # 0~1 范围属性
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

    import random as _rnd
    for idx in displayed_events:
        if idx >= len(sorted_timeline):
            continue
        evt = sorted_timeline[idx]
        outcomes = evt.get("outcomes", {})
        for attr, change_range in outcomes.items():
            if not isinstance(change_range, (list, tuple)) or len(change_range) != 2:
                continue
            mapped_attr = key_aliases.get(attr, attr)
            min_c, max_c = change_range
            change = _rnd.uniform(min_c, max_c)
            old_val = attrs.get(mapped_attr, 0.0)
            if mapped_attr == "education_level":
                attrs[mapped_attr] = max(0.0, min(7.0, old_val + change))
            elif mapped_attr in zero_one_attrs:
                attrs[mapped_attr] = max(0.0, min(1.0, old_val + change))
            else:
                attrs[mapped_attr] = max(-1.0, min(1.0, old_val + change))
    return attrs


def get_attr_delta(character, displayed_events, full_timeline, attr_name):
    """计算某属性自初始以来的累积变化"""
    if not character or "attributes" not in character:
        return 0.0
    initial = character["attributes"].get(attr_name, 0.0)
    current = compute_current_attributes(character, displayed_events, full_timeline)
    return current.get(attr_name, initial) - initial


# =====================================================================
# 格式化属性为可读显示
# =====================================================================
def format_attr_display(attr_name, value, delta=0.0):
    """将属性值格式化为可读的中文展示"""
    # 特殊映射
    edu_labels = ["文盲", "小学", "初中", "高中", "大专/本科", "研究生", "博士"]
    if attr_name == "education_level":
        idx = min(int(value), len(edu_labels) - 1)
        return edu_labels[idx]

    # 百分比型指标 (0~1) → 百分比
    pct_attrs = {
        "health": "健康状况", "social_status": "社会地位",
        "wealth": "财富水平", "stress_level": "压力水平",
        "community_integration": "社区整合", "cultural_capital": "文化资本",
        "economic_capital": "经济资本", "social_capital": "社会资本",
    }
    if attr_name in pct_attrs or value <= 1.0 and value >= 0.0:
        pct = int(value * 100)
        return f"{pct}%"

    return f"{value:.2f}"


def attr_label(attr_name):
    """属性中文标签"""
    labels = {
        "health": "健康状况", "social_status": "社会地位",
        "wealth": "财富水平", "education_level": "教育水平",
        "stress_level": "压力水平", "cultural_capital": "文化资本",
        "economic_capital": "经济资本", "social_capital": "社会资本",
        "community_integration": "社区整合度",
    }
    return labels.get(attr_name, attr_name)


# =====================================================================
# 代表性（里程碑）事件判断
# =====================================================================
_MILESTONE_KW = [
    # 生命里程碑
    "出生", "死亡", "结婚", "离婚", "生子", "怀孕",
    # 教育/职业
    "入学", "毕业", "入职", "升职", "降职", "失业", "退休", "创业", "破产",
    # 地域/生活
    "搬家", "迁移", "出国", "回国",
    # 健康
    "生病", "住院", "确诊", "康复", "重伤",
    # 其他重大
    "获奖", "入狱", "释放", "判刑",
]


def is_milestone_event(event: dict) -> bool:
    """
    判断事件是否为「代表性/里程碑」事件。
    满足以下任一条件即返回 True：
      1. 事件名称或描述含里程碑关键词
      2. outcomes 中 health/social_status/wealth 的变化幅度 ≥ 0.3
      3. 年龄是 10 的倍数（10/20/30/40/50/60/70/80 岁）
    """
    name = event.get("name", "")
    desc = event.get("description", "")

    # 标准1：关键词
    for kw in _MILESTONE_KW:
        if kw in name or kw in desc:
            return True

    # 标准2：核心指标大幅变化
    outcomes = event.get("outcomes", {})
    for attr, change_range in outcomes.items():
        if attr in ("health", "social_status", "wealth", "education_level"):
            if isinstance(change_range, (list, tuple)) and len(change_range) == 2:
                avg = (change_range[0] + change_range[1]) / 2.0
                if abs(avg) >= 0.3:
                    return True

    # 标准3：整十岁
    age = event.get("age", 0)
    if age > 0 and age % 10 == 0:
        return True

    return False




# =====================================================================
# 侧边栏
# =====================================================================
def render_sidebar():
    with st.sidebar:
        st.markdown("### 🎲 社会学人生模拟器")
        st.markdown("---")

        with st.expander("📚 社会学理论速览", expanded=False):
            st.markdown("**🔴 涂尔干**: 机械团结 · 有机团结")
            st.markdown("**🔵 韦伯**: 理性化 · 祛魅世界")
            st.markdown("**🟣 布迪厄**: 场域 · 惯习 · 文化资本")
            st.markdown("**🟠 福柯**: 规训社会 · 全景敞视")
            st.markdown("**🟢 费孝通**: 乡土社会 · 差序格局")
            st.markdown("**🟡 贝克**: 风险社会")
            st.markdown("**🔷 齐美尔**: 大都市 · 陌生人")

        st.markdown("---")
        st.markdown(
            "<div style='font-size:0.75rem;color:#888;'>"
            "北京大学社会学系<br>"
            "「社会学的人工智能」课后实践"
            "</div>",
            unsafe_allow_html=True,
        )


# =====================================================================
# 页面 0：欢迎页
# =====================================================================
def render_welcome_page():
    st.markdown(
        '<div class="welcome-box">'
        '<p class="main-title">🎲 社会学人生模拟器</p>'
        '<p class="welcome-text">'
        '同一段人生，在不同的理论透镜下呈现截然不同的命运。<br>'
        '选择社会结构，设定虚拟人物，<em>用社会学的眼睛活一遍</em>。<br>'
        '你会发现：决定命运的，也许不是你活着的方式，而是谁在注视你。'
        '</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    col_center = st.columns([1, 2, 1])[1]
    with col_center:
        if st.button("📖 进入设置", use_container_width=True, type="primary", key="btn_welcome_setup"):
            _clear_all_results()
            st.session_state.page = "setup"
            st.rerun()


# =====================================================================
# 页面 1：设置页
# =====================================================================
def render_setup_page():
    st.markdown(
        '<p class="main-title">🎲 社会学人生模拟器</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="subtitle">选择宏观社会结构，设定虚拟人物，'
        '体验社会理论如何塑造个体命运</p>',
        unsafe_allow_html=True,
    )

    structure_engine = StructureEngine(DATA_DIR)
    character_gen = CharacterGenerator(DATA_DIR)

    # ── 第一步：选择社会结构 ──────────────────────────────────
    st.markdown("## ① 选择宏观社会结构")
    st.info("💡 选择 1–2 个社会结构，它们会相互作用，共同影响人物的人生轨迹")

    structures_by_theorist = structure_engine.get_structures_by_category()
    selected_ids = []

    for theorist, structures in structures_by_theorist.items():
        st.markdown(f"### {theorist}")
        cols = st.columns(2)
        for j, s in enumerate(structures):
            with cols[j % 2]:
                is_selected = s["id"] in st.session_state.get("selected_structures", [])
                checked = st.checkbox(
                    f"{s['emoji']} {s['name']}",
                    value=is_selected,
                    key=f"struct_{s['id']}",
                    help=s.get("description", ""),
                )
                if checked:
                    selected_ids.append(s["id"])

    st.session_state.selected_structures = selected_ids

    # ── 结构网络关系图 ──────────────────────────────────────
    with st.expander("🔗 理论结构关系网络图（可交互）", expanded=False):
        network_path = os.path.join(BASE_DIR, "structure_network.html")
        if os.path.exists(network_path):
            st.markdown('<div class="network-container">', unsafe_allow_html=True)
            with open(network_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            st.components.v1.html(html_content, height=550, scrolling=False)
            st.markdown('</div>', unsafe_allow_html=True)
            st.caption(
                "💡 点击连线查看两理论间的关系与原因。绿色实线 = 相生（互相促进），"
                "红色虚线 = 相克（相互矛盾）。拖拽节点可移动，滚轮缩放。"
            )
        else:
            st.info("📌 结构网络图文件未找到（structure_network.html）")

    st.markdown("---")

    # ── 第二步：设定人物 ────────────────────────────────────────
    st.markdown("## ② 设定虚拟人物")

    tab_preset, tab_custom = st.tabs(["🎭 预设人物", "✏️ 自定义"])

    selected_preset_id = None
    preset_options_map = {}  # display_name → preset_id

    with tab_preset:
        presets = character_gen.get_preset_characters()
        preset_display = [""]  # 空选项
        for p in presets:
            display_name = f"{p['emoji']} {p['name']}"
            preset_display.append(display_name)
            preset_options_map[display_name] = p

        selected_preset = st.selectbox(
            "选择预设人物（快速开始）",
            preset_display,
            format_func=lambda x: x if x else "请选择...",
        )
        if selected_preset and selected_preset in preset_options_map:
            p = preset_options_map[selected_preset]
            selected_preset_id = p["id"]
            st.markdown(f"**{p.get('description', '')}**")

    custom_settings = {}
    with tab_custom:
        col1, col2 = st.columns(2)
        with col1:
            gender_options = character_gen.get_gender_options()
            gender_choice = st.selectbox(
                "性别",
                range(len(gender_options)),
                format_func=lambda i: f"{gender_options[i]['emoji']} {gender_options[i]['name']}",
            )
            birth_place_options = character_gen.get_birth_place_options()
            birth_place_choice = st.selectbox(
                "出生地类型",
                range(len(birth_place_options)),
                format_func=lambda i: f"{birth_place_options[i]['emoji']} {birth_place_options[i]['name']}",
            )
        with col2:
            era_options = character_gen.get_era_options()
            era_choice = st.selectbox(
                "时代背景",
                range(len(era_options)),
                format_func=lambda i: f"{era_options[i]['emoji']} {era_options[i]['name']}",
            )
            parent_class_options = character_gen.get_parent_class_options()
            parent_class_choice = st.selectbox(
                "父母阶层",
                range(len(parent_class_options)),
                format_func=lambda i: f"{parent_class_options[i]['emoji']} {parent_class_options[i]['name']}",
            )
        custom_settings = {
            "gender_id": gender_options[gender_choice]["id"],
            "birth_place_id": birth_place_options[birth_place_choice]["id"],
            "era_id": era_options[era_choice]["id"],
            "parent_class_id": parent_class_options[parent_class_choice]["id"],
        }

    st.markdown("---")

    # ── 第三步：生成 ────────────────────────────────────────────
    st.markdown("## ③ 生成人生模拟")

    col_seed, col_btn = st.columns([1, 2])
    with col_seed:
        random_seed = st.number_input(
            "随机种子（相同种子 → 相同结果）",
            min_value=0,
            max_value=999999,
            value=st.session_state.random_seed,
            step=1,
        )
        st.session_state.random_seed = random_seed
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        generate_button = st.button(
            "🚀 开始模拟人生",
            use_container_width=True,
            type="primary",
            key="btn_setup_generate",
        )

    if generate_button:
        if len(selected_ids) < 1:
            st.error("⚠️ 请至少选择 1 个社会结构")
            return

        # 清除旧结果
        _clear_all_results()

        # 生成人物
        try:
            if selected_preset_id:
                character = character_gen.apply_preset(selected_preset_id)
                if character is None:
                    st.error(f"⚠️ 预设人物 '{selected_preset_id}' 加载失败，请选择其他或自定义")
                    return
            else:
                character = character_gen.generate_character(**custom_settings)

            # 确保角色有 health / social_status / wealth 初始值
            attrs = character.setdefault("attributes", {})
            attrs.setdefault("health", random.uniform(0.6, 0.9))
            attrs.setdefault("social_status", random.uniform(0.2, 0.5))
            attrs.setdefault("wealth", random.uniform(0.1, 0.4))

        except Exception as e:
            st.error(f"⚠️ 人物生成失败：{e}")
            return

        # 缓存参数，立即切换到模拟页执行生成
        st.session_state.character = character
        st.session_state.selected_structures = selected_ids
        st.session_state.random_seed = random_seed
        st.session_state.needs_generation = True
        st.session_state.generation_done = False
        st.session_state.generation_step = "准备中..."
        st.session_state.displayed_events = []
        st.session_state.current_age = 0
        st.session_state.simulation_done = False
        st.session_state.page = "simulate"
        st.rerun()


# =====================================================================
# 页面 2：模拟推进页（逐年/逐批展示事件 + 动态指标）
# =====================================================================
def _run_generation_on_simulate_page():
    """在模拟页上执行全部生成流程，带进度展示。"""
    character = st.session_state.get("character")
    selected_ids = st.session_state.get("selected_structures", [])
    random_seed = st.session_state.get("random_seed", 42)

    # ── 进度展示区 ──────────────────────────────────────────────
    st.markdown("## 🎲 正在生成你的人生...")
    st.markdown("---")

    step_placeholder = st.empty()
    progress_bar = st.progress(0.0)

    steps = [
        ("⏳ 生成人生时间线...", 0.15),
        ("🔍 AI 逻辑校验...", 0.40),
        ("🤖 AI 优化事件描述...", 0.65),
        ("📖 AI 撰写人生故事...", 0.85),
    ]

    # 第1步：生成时间线
    step_placeholder.markdown(f"### {steps[0][0]}")
    try:
        life_gen = LifeGenerator(DATA_DIR)
        result = life_gen.generate_timeline_with_visualization(
            character=character,
            selected_structure_ids=selected_ids,
            seed=random_seed,
        )
    except Exception as e:
        import traceback
        st.error(f"⚠️ 时间线生成出错：{e}")
        st.session_state.generation_error = traceback.format_exc()
        st.session_state.needs_generation = False
        if st.button("返回设置页", key="btn_gen_err_back"):
            _clear_all_results()
            st.session_state.page = "setup"
            st.session_state._scroll_needed = True
            st.rerun()
        return

    timeline = result.get("timeline", [])

    # ── 安全网：移除死亡事件后的所有后续事件 ─────────────────────
    timeline = _remove_events_after_death(timeline)

    if not timeline:
        st.warning(
            "⚠️ 当前结构组合下未能生成有效人生事件。"
            "这可能是因为所选社会结构之间冲突过大，"
            "或随机种子不理想。请尝试换一个种子或调整结构组合。"
        )
        if st.button("返回设置页", key="btn_no_tl_back"):
            _clear_all_results()
            st.session_state.page = "setup"
            st.session_state._scroll_needed = True
            st.rerun()
        return

    progress_bar.progress(steps[0][1])

    # 第2步：逻辑校验循环
    step_placeholder.markdown(f"### {steps[1][0]}")
    MAX_LOGIC_RETRIES = 3
    logic_passed = False
    logic_issues = ""
    logic_suggestions = ""

    for attempt in range(MAX_LOGIC_RETRIES):
        logic_passed, logic_issues, logic_suggestions = check_story_logic(character, timeline)
        if logic_passed:
            break
        else:
            if attempt < MAX_LOGIC_RETRIES - 1:
                # 重新生成时间线
                try:
                    new_seed = random.randint(1, 999999)
                    result = life_gen.generate_timeline_with_visualization(
                        character=character,
                        selected_structure_ids=selected_ids,
                        seed=new_seed,
                    )
                    new_tl = result.get("timeline", [])
                    if new_tl:
                        timeline = new_tl
                except Exception:
                    pass

    progress_bar.progress(steps[1][1])

    # 第3步：LLM 优化事件描述
    step_placeholder.markdown(f"### {steps[2][0]}")
    timeline = optimize_events_with_llm(character, timeline, selected_ids)
    progress_bar.progress(steps[2][1])

    # 第4步：LLM 生成人生故事
    step_placeholder.markdown(f"### {steps[3][0]}")
    life_story = generate_life_story(character, timeline, selected_ids)
    progress_bar.progress(1.0)

    # ── 全部完成，存储结果 ──────────────────────────────────────
    st.session_state.full_timeline = timeline
    st.session_state.metadata = result.get("metadata", {})
    st.session_state.life_result = result
    st.session_state.generation_error = None
    st.session_state.life_story = life_story
    st.session_state.logic_check = {
        "passed": logic_passed,
        "issues": logic_issues,
        "suggestions": logic_suggestions,
        "retries": min(attempt + 1, MAX_LOGIC_RETRIES),
    }
    st.session_state.needs_generation = False
    st.session_state.generation_done = True
    st.session_state._scroll_needed = True  # 标记需要滚动到顶部
    st.rerun()


def render_simulate_page():
    character = st.session_state.get("character")
    full_timeline = st.session_state.get("full_timeline")

    # ── 如果还没生成，先执行生成流程 ────────────────────────────
    if st.session_state.get("needs_generation", False):
        _run_generation_on_simulate_page()
        return

    if not character or not full_timeline:
        st.error("没有可模拟的数据，请先运行模拟")
        gen_err = st.session_state.get("generation_error")
        if gen_err:
            with st.expander("🔍 技术详情"):
                st.code(gen_err)
        if st.button("返回重新设置", key="btn_sim_nodata_back"):
            _clear_all_results()
            st.session_state.page = "setup"
            st.session_state._scroll_needed = True
            st.rerun()
        return

    # ── 头部信息 ────────────────────────────────────────────────
    col_head, col_btn = st.columns([3, 1])
    with col_head:
        st.markdown(f"## 📜 {character['name']} 的人生")
        info_parts = [
            f"**出生年份**：约 {character.get('birth_year', '?')} 年",
            f"**性别**：{character.get('gender_display', character.get('gender', '未知'))}",
            f"**出生地**：{character.get('birth_place_display', character.get('birth_place', '未知'))}",
        ]
        st.markdown(" | ".join(info_parts))
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("⏹ 结束模拟，查看总结", use_container_width=True, key="btn_sim_end"):
            st.session_state.simulation_done = True
            st.session_state.page = "result"
            st.session_state._scroll_needed = True
            st.rerun()

    st.markdown("---")

    # ── 当前动态指标 ────────────────────────────────────────────
    displayed = st.session_state.displayed_events
    current_attrs = compute_current_attributes(character, displayed, full_timeline)

    # 核心四大指标：健康、社会地位、财富、教育
    st.markdown("### 📊 当前状态")
    core_metrics = [
        ("health", "健康"),
        ("social_status", "社会地位"),
        ("wealth", "财富"),
        ("education_level", "教育"),
    ]
    metric_cols = st.columns(4)
    edu_labels = ["文盲", "小学", "初中", "高中", "大专/本科", "研究生", "博士"]
    for i, (key, label) in enumerate(core_metrics):
        val = current_attrs.get(key, 0)
        delta = get_attr_delta(character, displayed, full_timeline, key)
        with metric_cols[i]:
            if key == "education_level":
                idx = min(int(val), len(edu_labels) - 1)
                display_val = edu_labels[idx]
                st.markdown(
                    f'<div class="stat-card">'
                    f'<div class="stat-value" style="font-size:1.4rem;">{display_val}</div>'
                    f'<div class="stat-label">{label}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                pct = int(val * 100)
                delta_pct = int(delta * 100)
                delta_html = ""
                if delta_pct > 0:
                    delta_html = f'<div class="stat-change-up">↑+{delta_pct}%</div>'
                elif delta_pct < 0:
                    delta_html = f'<div class="stat-change-down">↓{delta_pct}%</div>'

                st.markdown(
                    f'<div class="stat-card">'
                    f'<div class="stat-value">{pct}%</div>'
                    f'<div class="stat-label">{label}</div>'
                    f'{delta_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # 次要指标行
    secondary_metrics = [
        ("stress_level", "压力"),
        ("cultural_capital", "文化资本"),
        ("economic_capital", "经济资本"),
        ("social_capital", "社会资本"),
        ("community_integration", "社区整合"),
        ("anomie_level", "失范感"),
    ]
    st.markdown("#### 社会心理指标")
    sec_cols = st.columns(len(secondary_metrics))
    for i, (key, label) in enumerate(secondary_metrics):
        val = current_attrs.get(key, 0)
        pct = max(0, min(100, int(val * 100)))
        with sec_cols[i]:
            bar_color = "#6c5ce7"
            if "stress" in key or "anomie" in key:
                bar_color = "#e17055"
            st.markdown(
                f'<div style="text-align:center; font-size:0.75rem; color:#636e72;">{label}</div>'
                f'<div class="metric-bar-outer">'
                f'<div class="metric-bar-inner" style="width:{pct}%;background:{bar_color};"></div>'
                f'</div>'
                f'<div style="text-align:center; font-size:0.7rem; color:#555;">{pct}%</div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── 已展示的事件 ────────────────────────────────────────────
    sorted_timeline = sorted(full_timeline, key=lambda e: e.get("age", 0))

    for idx in displayed:
        if idx >= len(sorted_timeline):
            continue
        event = sorted_timeline[idx]
        age = event.get("age", 0)
        emoji = event.get("action_emoji", "📋")
        name = event.get("name", "未知事件")
        desc = event.get("description", "")
        reading = event.get("sociological_reading", "")
        outcomes = event.get("outcomes", {})

        # 渲染 outcome 变化
        outcome_parts = []
        for attr, cr in outcomes.items():
            if isinstance(cr, (list, tuple)) and len(cr) == 2:
                outcome_parts.append(
                    f"{attr_label(attr)} {'+' if cr[1] > 0 else ''}{cr[0]:+.1f}~{cr[1]:+.1f}"
                )
        outcome_html = ""
        if outcome_parts:
            outcome_html = (
                f'<div class="event-outcome">📊 属性变化：{", ".join(outcome_parts)}</div>'
            )

        st.markdown(f"""
        <div class="event-card">
            <div class="event-age">{emoji} {age} 岁</div>
            <div class="event-name">{name}</div>
            <div class="event-desc">{desc}</div>
            {outcome_html}
            {f'<div class="event-reading">📖 {reading}</div>' if reading else ''}
        </div>
        """, unsafe_allow_html=True)

    # ── 控制区：推进按钮 ────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="sim-controls">', unsafe_allow_html=True)

    next_idx = len(displayed)
    if next_idx >= len(sorted_timeline):
        st.markdown(
            '<div class="sim-year-display">🎉 人生模拟完毕！</div>',
            unsafe_allow_html=True,
        )

        # 直接在模拟页显示人生故事
        life_story = st.session_state.get("life_story", "")
        if life_story:
            st.markdown("---")
            st.markdown("### 📖 人生故事")
            st.markdown(life_story)

        if st.button("📊 查看完整人生总结", use_container_width=True, type="primary", key="btn_sim_summary"):
            st.session_state.simulation_done = True
            st.session_state.page = "result"
            st.session_state._scroll_needed = True
            st.rerun()
    else:
        next_event = sorted_timeline[next_idx]
        next_age = next_event.get("age", 0)

        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1, 2, 1])
        with col_ctrl2:
            batch_indices = []
            batch_age = next_age
            for i in range(next_idx, len(sorted_timeline)):
                if sorted_timeline[i].get("age", 0) <= batch_age:
                    batch_indices.append(i)
                else:
                    break

            batch_label = f"⏳ {batch_age} 岁 → 继续"
            if st.button(batch_label, use_container_width=True, type="primary", key=f"btn_next_{batch_age}"):
                st.session_state.displayed_events.extend(batch_indices)
                st.session_state.current_age = batch_age
                st.rerun()

            if next_idx + 1 < len(sorted_timeline):
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("⏩ 快进到下一阶段", use_container_width=True, key="btn_fast_forward"):
                    target_age = batch_age + 5
                    fast_indices = []
                    for i in range(next_idx, len(sorted_timeline)):
                        if sorted_timeline[i].get("age", 0) <= target_age:
                            fast_indices.append(i)
                        else:
                            break
                    st.session_state.displayed_events.extend(fast_indices)
                    st.session_state.current_age = min(
                        target_age,
                        sorted_timeline[-1].get("age", 0),
                    )
                    st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# =====================================================================
# 时间线重新生成（质量修复）
# =====================================================================


# =====================================================================
# 页面 3：结果总结页
# =====================================================================
def render_result_page():
    character = st.session_state.get("character")
    timeline = st.session_state.get("full_timeline")
    metadata = st.session_state.get("metadata", {})
    selected_structures = st.session_state.get("selected_structures", [])

    if not character or not timeline:
        st.error("没有可显示的结果，请先运行模拟")
        if st.button("返回重新设置", key="btn_result_nodata_back"):
            _clear_all_results()
            st.session_state.page = "setup"
            st.session_state._scroll_needed = True
            st.rerun()
        return

    # ── 头部 ────────────────────────────────────────────────────
    col_head, col_btn = st.columns([3, 1])
    with col_head:
        st.markdown(f"## 📜 {character['name']} 的人生年表")
        info_parts = [
            f"**出生年份**：约 {character.get('birth_year', '?')} 年",
            f"**性别**：{character.get('gender_display', character.get('gender', '未知'))}",
            f"**出生地**：{character.get('birth_place_display', character.get('birth_place', '未知'))}",
        ]
        st.markdown(" | ".join(info_parts))
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 重新模拟", use_container_width=True, key="btn_result_retry"):
            _clear_all_results()
            st.session_state.page = "setup"
            st.session_state._scroll_needed = True
            st.rerun()

    st.markdown("---")

    # ── 统计概览 ────────────────────────────────────────────────
    st.markdown("### 📊 人生统计")
    ages = [e.get("age", 0) for e in timeline]
    life_span = max(ages) - min(ages) if ages else 0
    # 用全部事件计算最终属性
    all_indices = list(range(len(sorted(timeline, key=lambda e: e.get("age", 0)))))
    final_attrs = compute_current_attributes(character, all_indices, timeline)
    edu_level = int(final_attrs.get("education_level", 0))
    edu_labels = ["文盲", "小学", "初中", "高中", "大专/本科", "研究生", "博士"]

    stat_cols = st.columns(4)
    with stat_cols[0]:
        st.markdown(f'<div class="stat-card">'
                     f'<div class="stat-value">{len(timeline)}</div>'
                     f'<div class="stat-label">总事件数</div>'
                     f'</div>', unsafe_allow_html=True)
    with stat_cols[1]:
        st.markdown(f'<div class="stat-card">'
                     f'<div class="stat-value">{life_span} 年</div>'
                     f'<div class="stat-label">人生跨度</div>'
                     f'</div>', unsafe_allow_html=True)
    with stat_cols[2]:
        st.markdown(f'<div class="stat-card">'
                     f'<div class="stat-value" style="font-size:1.4rem;">{edu_labels[min(edu_level, 6)]}</div>'
                     f'<div class="stat-label">最终学历</div>'
                     f'</div>', unsafe_allow_html=True)
    with stat_cols[3]:
        final_age = max(ages) if ages else 0
        st.markdown(f'<div class="stat-card">'
                     f'<div class="stat-value">{final_age} 岁</div>'
                     f'<div class="stat-label">终老年龄</div>'
                     f'</div>', unsafe_allow_html=True)

    # ── 最终四项核心指标 ──────────────────────────────────────────
    st.markdown("### 📈 人生终局指标")
    core_final = [
        ("health", "健康状况"), ("wealth", "财富水平"),
        ("social_status", "社会地位"), ("stress_level", "压力水平"),
    ]
    fcols = st.columns(4)
    for i, (key, label) in enumerate(core_final):
        val = final_attrs.get(key, 0)
        pct = int(val * 100)
        with fcols[i]:
            st.markdown(f'<div class="stat-card">'
                         f'<div class="stat-value">{pct}%</div>'
                         f'<div class="stat-label">{label}</div>'
                         f'</div>', unsafe_allow_html=True)

    st.markdown("---")

    # ── 人生故事（AI 已预生成 — 放在突出位置）───────────────────────────────
    st.markdown("### 📖 人生故事")
    life_story = st.session_state.get("life_story", "")
    if life_story:
        st.markdown(life_story)
    else:
        st.info("人生故事生成失败或不可用。")

    st.markdown("---")

    # ── 社会规则预览 ────────────────────────────────────────────
    with st.expander("🌍 本次模拟的社会规则", expanded=False):
        social_rules_engine = SocialRulesEngine(DATA_DIR)
        social_rules = social_rules_engine.generate_social_rules(selected_structures)

        st.markdown(f"**社会名称**：{social_rules.get('name', '未命名')}")

        # 社会特点描述
        structure_engine = StructureEngine(DATA_DIR)
        all_structures = {s["id"]: s for s in structure_engine.structures}
        st.markdown("#### 🏛️ 社会特点")
        for sid in selected_structures:
            s = all_structures.get(sid)
            if s:
                st.markdown(
                    f"- **{s.get('emoji', '')} {s.get('name', sid)}**（{s.get('theorist', '')}）："
                    f"{s.get('description', '')}"
                )

        st.markdown("---")

        col1, col2, col3 = st.columns(3)
        with col1:
            edu = social_rules.get("education", {})
            st.markdown("**📚 教育制度**")
            st.markdown(f"- 入学：{edu.get('school_start_age', 6)} 岁")
            st.markdown(f"- 小学：{edu.get('primary_years', 6)} 年")
            st.markdown(f"- 大学：{edu.get('university_years', 4)} 年")
        with col2:
            work = social_rules.get("work", {})
            st.markdown("**🏭 工作制度**")
            st.markdown(f"- 最低工龄：{work.get('min_age', 16)} 岁")
            st.markdown(f"- 退休：{work.get('retirement_age', 60)} 岁")
        with col3:
            marriage = social_rules.get("marriage", {})
            st.markdown("**💒 婚姻制度**")
            st.markdown(f"- 法定婚龄：{marriage.get('legal_age', 22)} 岁")

    st.markdown("---")

    # ── 结构网络关系图 ────────────────────────────────────────────
    with st.expander("🔗 理论结构关系网络（可交互）", expanded=False):
        network_path = os.path.join(BASE_DIR, "structure_network.html")
        if os.path.exists(network_path):
            st.markdown('<div class="network-container">', unsafe_allow_html=True)
            with open(network_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            st.components.v1.html(html_content, height=550, scrolling=False)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("📌 结构网络图未找到")

    st.markdown("---")

    # ── 完整人生时间线 ────────────────────────────────────────────────
    st.markdown("### ⏳ 完整人生时间线")

    sorted_tl = sorted(timeline, key=lambda e: e.get("age", 0))

    # 事件总数 ≤ 30 时直接全部展示；> 30 时默认只展示代表性事件（兜底）
    if len(timeline) <= 30:
        display_events = sorted_tl
        st.caption(f"共 {len(timeline)} 个事件")
    else:
        show_all = st.checkbox(
            "显示全部事件（默认只展示代表性/里程碑事件）",
            value=False,
            key="show_all_events_result",
        )
        if show_all:
            display_events = sorted_tl
            st.caption(f"展示全部 {len(display_events)} 个事件")
        else:
            display_events = [e for e in sorted_tl if is_milestone_event(e)]
            if not display_events:
                display_events = sorted_tl[:10]
            st.caption(
                f"展示代表性事件 {len(display_events)} 个 / 共 {len(timeline)} 个"
                f"（勾选上方复选框查看完整时间线）"
            )

    for event in display_events:
        age = event.get("age", 0)
        emoji = event.get("action_emoji", "📋")
        name = event.get("name", "未知事件")
        desc = event.get("description", "")
        reading = event.get("sociological_reading", "")
        outcomes = event.get("outcomes", {})
        outcome_parts = []
        for attr, cr in outcomes.items():
            if isinstance(cr, (list, tuple)) and len(cr) == 2:
                outcome_parts.append(f"{attr_label(attr)} {cr[0]:+.1f}~{cr[1]:+.1f}")
        outcome_html = ""
        if outcome_parts:
            outcome_html = (
                f'<div class="event-outcome">📊 {", ".join(outcome_parts)}</div>'
            )

        st.markdown(f"""
        <div class="event-card">
            <div class="event-age">{emoji} {age} 岁</div>
            <div class="event-name">{name}</div>
            <div class="event-desc">{desc}</div>
            {outcome_html}
            {f'<div class="event-reading">📖 {reading}</div>' if reading else ''}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── 逻辑校验摘要 ────────────────────────────────────────────
    logic_check = st.session_state.get("logic_check", {})
    st.markdown("### 🔍 逻辑校验报告")
    if logic_check:
        passed = logic_check.get("passed", False)
        retries = logic_check.get("retries", 0)
        issues = logic_check.get("issues", "")
        suggestions = logic_check.get("suggestions", "")

        if passed:
            st.success(f"✅ 逻辑校验通过（共尝试 {retries} 次）")
        else:
            st.warning(f"⚠️ 逻辑校验有瑕疵（共尝试 {retries} 次，已达上限）")
            if issues:
                with st.expander("📋 发现的问题", expanded=True):
                    for line in issues.split("\n"):
                        line = line.strip()
                        if line:
                            st.markdown(f"- {line}")
            if suggestions:
                with st.expander("💡 改进建议"):
                    st.markdown(suggestions)
    else:
        st.info("未进行逻辑校验。")



# =====================================================================
# 主程序入口
# =====================================================================
def main():
    init_session_state()
    render_sidebar()

    # 页面切换时滚动到顶部
    _prev_page = st.session_state.get("_prev_page", "welcome")
    _curr_page = st.session_state.page
    if _prev_page != _curr_page:
        st.session_state._prev_page = _curr_page
        _scroll_to_top()

    # 只渲染当前页面（Streamlit 每次 rerun 都是全新渲染，不会残留旧内容）
    page = st.session_state.page
    if page == "welcome":
        render_welcome_page()
    elif page == "setup":
        render_setup_page()
    elif page == "simulate":
        render_simulate_page()
    elif page == "result":
        render_result_page()


if __name__ == "__main__":
    main()
