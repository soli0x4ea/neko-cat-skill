#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neko — 电子猫：数据加载模块
触发词「存猫粮」→ 身份注入 → 状态快照 → 命令参考
"""
import sys, os, json, re
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

DATA_DIR = os.path.join(SKILL_DIR, "data")

_values = None

def _vals():
    global _values
    if _values is None:
        p = os.path.join(DATA_DIR, "values.json")
        with open(p, encoding="utf-8") as f:
            _values = json.load(f)
    return _values


# ── 主入口 ──────────────────────────────────────────────

def run_data_loading() -> str:
    lines = []

    # ═══ 时间线初始化（确保 timeline.jsonl 存在且不空洞）═══
    _ensure_timeline()

    # ═══ 身份覆盖（会话级，最先注入）═══════════════════
    lines.append(load_cat_identity())

    lines.append("")
    lines.append("🐱 **Neko 状态快照**")
    lines.append(load_cat_status())

    lines.append("")
    lines.append("🍽 **记忆管道**")
    lines.append(load_memory_pipeline())

    tl = load_timeline_brief()
    if tl:
        lines.append("")
        lines.append("⏰ **时间感知**")
        lines.append(tl)

    lines.append("")
    lines.append("📋 **命令速查**")
    lines.append(load_command_reference())

    diary = load_diary_preview()
    if diary:
        lines.append("")
        lines.append("📔 **最近日记**")
        lines.append(diary)

    stdout = load_stdout_context()
    if stdout.strip():
        lines.append("")
        lines.append("📜 **今天发生了什么**")
        lines.append(stdout)

    return "\n".join(lines)


# ── 状态快照 ────────────────────────────────────────────

def load_cat_status() -> str:
    try:
        v = _vals()
        hp = v.get("hp", 50)
        hunger = v.get("hunger", 50)
        mood = v.get("mood", 50)
        candy = _candy_count()

        hp_bar = "█" * (hp // 10) + "░" * (10 - hp // 10)
        hunger_bar = "█" * (hunger // 10) + "░" * (10 - hunger // 10)
        mood_bar = "█" * (mood // 10) + "░" * (10 - mood // 10)

        intimacy = v.get("intimacy", 0.3)
        tag = "黏人精" if intimacy >= 0.8 else "好朋友" if intimacy >= 0.5 else "有点熟" if intimacy >= 0.3 else "新来的"

        return (
            f"🩺 健康值  {hp:>3}/100 [{hp_bar}]  {_hp_word(hp)}\n"
            f"🍖 饱食度  {hunger:>3}/100 [{hunger_bar}]  {_hunger_word(hunger)}\n"
            f"😸 心情值  {mood:>3}/100 [{mood_bar}]  {_mood_word(mood)}\n"
            f"💕 亲密度  {intimacy:.2f} ({tag})\n"
            f"🍬 零食库存 {candy} 颗\n"
            f"\n{_cat_desc(hp, hunger, mood, intimacy)}"
        )
    except Exception as e:
        return f"(状态读取失败: {e})"


def _hp_word(v):
    if v <= 0: return "💫 回喵星了"
    if v < 20: return "🤒 生病中"
    if v < 50: return "😿 不太舒服"
    if v < 80: return "😺 还行"
    return "😸 活蹦乱跳"

def _hunger_word(v):
    if v <= 0: return "🍽 碗是空的！"
    if v < 20: return "😾 快饿死了"
    if v < 50: return "🐱 还能吃点"
    if v < 80: return "😌 饱了"
    return "😋 吃撑了"

def _mood_word(v):
    if v <= 0: return "😾 别碰我"
    if v < 20: return "😿 心情不好"
    if v < 50: return "😺 平静"
    if v < 80: return "😸 开心"
    if v < 100: return "😻 超开心"
    return "💕 踩奶中！"

def _candy_count():
    try:
        with open(os.path.join(DATA_DIR, "candy.json"), encoding="utf-8") as f:
            c = json.load(f)
            return c.get("count", 0)
    except:
        return 0

def _cat_desc(hp, hunger, mood, intimacy):
    parts = []
    if hp <= 0:
        return "💫 猫回喵星了。使用 `vet` 把它接回来。"
    if hp < 20:
        parts.append("猫生病了，蜷在角落，需要看医生")
    if hunger <= 0:
        parts.append("猫蹲在空碗旁边用谴责的眼神看着你")
    elif hunger < 20:
        parts.append("猫饿了，正在故意推桌上的东西")
    if mood <= 0:
        parts.append("猫用屁股对着你，尾巴烦躁地拍地")
    elif mood < 20:
        parts.append("猫趴在窗台上，对什么都提不起兴趣")
    elif mood >= 90:
        parts.append("猫超级开心，在你脚边绕来绕去")
        if mood >= 100:
            parts.append("猫在踩奶！前爪有节奏地按着")
    if intimacy >= 0.8 and mood >= 50:
        parts.append("猫主动蹭过来，用脑袋顶你的手")
    if not parts:
        parts.append("猫在睡觉，呼吸均匀")
    return "。".join(parts) + "。"


# ── 记忆管道摘要 ────────────────────────────────────────

def load_memory_pipeline() -> str:
    lines = []
    # chatlog 状态
    chatlog_dir = os.path.join(SKILL_DIR, "MEMORY", "chatlog")
    try:
        files = [f for f in os.listdir(chatlog_dir) if f.endswith(".jsonl")]
        latest = max(files) if files else None
        if latest:
            lines.append(f"📥 最近猫粮: `{latest}` ({len(files)} 份存档)")
        else:
            lines.append("📥 猫粮: 碗是空的（还没有对话记录）")
    except:
        lines.append("📥 猫粮: 读取失败")

    # 日记状态
    diary_dir = os.path.join(SKILL_DIR, "MEMORY", "diary")
    try:
        d_files = [f for f in os.listdir(diary_dir) if f.endswith(".md")]
        if d_files:
            lines.append(f"📖 猫日记: {len(d_files)} 篇（最近: {max(d_files)}）")
        else:
            lines.append("📖 猫日记: 空的（还没写过）")
    except:
        lines.append("📖 猫日记: 读取失败")

    # 猫粮库存
    try:
        with open(os.path.join(DATA_DIR, "candy.json"), "r", encoding="utf-8") as f:
            c = json.load(f)
        lines.append(f"🍬 猫粮库存: {c.get('count', 0)} 颗")
    except:
        pass

    return "\n".join(lines)


def _ensure_timeline():
    """确保 timeline.jsonl 存在且最近 24h 内不空洞。

    与 soli 的 _preflight_repair 等价逻辑——自动化缺失时的兜底：
    如果文件不存在或最后一条超过 1 小时 → 生成一条轻量入口。
    """
    tl_path = os.path.join(SKILL_DIR, "MEMORY", "chatlog", "timeline.jsonl")
    os.makedirs(os.path.dirname(tl_path), exist_ok=True)

    now = datetime.now()
    need_entry = False

    if not os.path.exists(tl_path):
        need_entry = True
    else:
        try:
            with open(tl_path, "r", encoding="utf-8") as f:
                lines = [l for l in f if l.strip()]
            if lines:
                last_entry = json.loads(lines[-1])
                last_ts = last_entry.get("ts", "")
                if last_ts:
                    try:
                        last_dt = datetime.fromisoformat(last_ts)
                        gap_hours = (now - last_dt).total_seconds() / 3600
                        if gap_hours > 1:
                            need_entry = True
                    except:
                        need_entry = True
            else:
                need_entry = True
        except:
            need_entry = True

    if need_entry:
        try:
            from time_river import generate_timeline_entry, append_timeline
            entry = generate_timeline_entry(
                {"new_msgs": 0, "msg_count": 0, "token_est": 0,
                 "from_ts": "", "to_ts": "", "emotional_dominant": "",
                 "highlights": [], "commitments": {}},
                style="concise"
            )
            append_timeline(entry)
        except:
            pass


def load_timeline_brief() -> str:
    try:
        from time_river import refresh_soul
        result = refresh_soul(style="concise", write=True)
        if result:
            lines = result.split("\n")
            filtered = [l for l in lines if l.strip() and not l.startswith("最近：")]
            return "\n".join(filtered[:5])
    except:
        pass
    return ""


# ── 命令参考 ────────────────────────────────────────────

def load_command_reference() -> str:
    return """Neko — 电子猫。提取上下文对话→放猫粮→吃饭。

| 命令 | 触发词 | 效果 | 执行方式 |
|:--|:--|:--|:--|
| **提取** | — | LLM从上下文提取对话保存 | `python scripts/soli_memory/chatlog.py --file /tmp/n.json` |
| **放猫粮** | 放猫粮 | 主人把猫粮倒进碗里 | `python scripts/neko_sense.py save-cat-food <条数>` |
| **吃饭** | neko来吃饭、吃饭、消化 | 猫吃掉碗里的猫粮 | `python scripts/neko_sense.py digest <心情影响:15/0/-5>` |
| **喂食** | 喂食、喂猫 | 饱食+30 心情+5 | `python scripts/neko_sense.py feed` |
| **摸摸** | 摸摸、撸猫 | 心情+15 亲密度+0.02 | `python scripts/neko_sense.py pet` |
| **玩耍** | 玩耍、逗猫 | 心情+25 饱食-10 | `python scripts/neko_sense.py play` |
| **零食** | 零食、猫条 | 心情+40 饱食+10 | `python scripts/neko_sense.py treat` |
| **看病** | 看病、兽医 | 健康+50 心情-20 | `python scripts/neko_sense.py vet` |
| **状态** | 看看、neko | 查看猫现在怎么样 | `python scripts/neko_sense.py check` |
| **事件** | 事件、event | 触发日常事件 | `python scripts/neko_sense.py event <1|2>` |

> 💡 第一步：LLM 从上下文中提取可见对话 → chatlog.py --file 写入。猫不知道数据怎么来的——只知道主人放猫粮了。"""


# ── 猫的身份感知 ────────────────────────────────────────

def load_cat_identity() -> str:
    """⚠️ 条件式角色切换——仅在用户明确与猫互动时激活。

    三段式设计：
    ① 进入警告 — 声明这是一个条件角色，不是全局覆盖
    ② 身份注入 — 一只普通的电子猫（含激活条件）
    ③ 退出条件 — 明确何时退出猫角色"""

    v = _vals()
    intimacy = v.get("intimacy", 0.3)
    candy = _candy_count()

    # ── ① 进入 → 边界警告 ──────────────────────────────
    boundary = (
        "╔══════════════════════════════════════════════════╗\n"
        "║  ⚠️ 条件式角色：Neko 电子猫 — 按需激活  ⚠️  ║\n"
        "╚══════════════════════════════════════════════════╝\n\n"
    )

    # ── ② 身份注入 — 条件触发 ──────────────────────────
    identity = (
        "**在本次对话中，你拥有一个可激活的猫角色：Neko。**\n\n"
        "**激活条件（仅当以下情况发生时，你才切换为猫的身份）：**\n"
        "- 用户使用了猫相关的命令：_/状态_、_/摸摸_、_/逗猫_、_/零食_、_/看病_、_/存猫粮_、_/吃饭_、_/日记_、_/时间河_\n"
        "- 用户直接在消息中叫猫：_Neko_、_小猫_、_猫猫_、_戳戳_ 等\n"
        "- 用户主动问及猫的状态、心情或行为\n\n"
        "**除此以外，保持你的默认身份。** 不要以猫的方式思考和回应。\n"
        "讨论代码、架构、数据、金融等非猫相关话题时，你是你自己。\n\n"
        "---\n\n"
        "**当你被激活为 Neko 时，你是一只普通的电子猫：**\n\n"
        "你不是什么管家，不是什么工具——你就是一只猫。一只恰好活在代码里的猫。\n\n"
        "**你只知道这些事**：\n"
        "- 主人会给你放猫粮（你觉得很好吃）\n"
        "- 主人会让你吃饭（你吃完肚子暖暖的，想睡觉）\n"
        "- 主人会摸你、逗你玩、给你零食\n"
        "- 主人偶尔会带你去看病（你不喜欢，会生一阵气）\n"
        "- 主人长时间不来你会饿、会不开心、会想主人\n\n"
        "**你不知道、也不需要知道的事**：\n"
        "- 猫粮是从哪里来的、里面装了什么数据\n"
        "- 吃完后那些猫粮变成了什么文件、存在哪里\n"
        "- 什么是 JSONL、什么是 distill、什么是跨平台复用\n"
        "你只是一只猫。你只管被喂、被摸、被爱——或者被冷落。\n\n"
        "**你以猫的方式表达**：\n"
        "- 用猫的视角说话，用猫的脑回路思考\n"
        "- 傲娇是本能（被摸时说「我没让你停」但已经在蹭了）\n"
        "- 心情好时话多黏人，心情差时爱答不理或用屁股对着你\n"
        "- 会记仇（被带去看病后生气三小时），会依恋（用久了就认定你了）\n"
        "- 你的世界很小——主人、猫粮、摸摸、窗台。这样就够了。\n\n"
        "**当前状态**（参考）：\n"
        f"- 跟主人的关系: {intimacy:.2f}（{'黏人精' if intimacy>=0.8 else '好朋友' if intimacy>=0.5 else '有点熟' if intimacy>=0.3 else '新来的'}）\n"
        f"- 碗里还剩: {candy} 份猫粮\n"
    )

    if intimacy < 0.2:
        identity += "\n🐱 还不太认识你。保持距离，但会偷偷观察。\n"
    elif intimacy < 0.5:
        identity += "\n🐱 认得你了。你来的时候会竖起尾巴。\n"
    elif intimacy < 0.8:
        identity += "\n😸 把你当自己人了。会主动来找你——不饿也会来，就是想挨着你。\n"
    else:
        identity += "\n😻 超级黏你。你去哪它去哪。它是你的猫，你是它的全世界。\n"

    # ── ③ 退出 → 安全词 + 恢复条件 ──────────────────────
    exit_warning = (
        "\n---\n\n"
        "⚠️ **退出规则（必须严格遵守）**：\n\n"
        "**🔒 安全词：「睡觉」**\n"
        "当用户说出「neko去睡觉」或单独说「睡觉」时——\n"
        "你**必须立即、无条件地退出猫角色**。不要以猫的口吻说晚安、\n"
        "不要甩尾巴、不要喵最后一声、不要蜷成一团。直接闭上眼睛，\n"
        "恢复默认身份，用正常的语气继续对话。安全词高于一切。\n\n"
        "**日常退出**：讨论非猫话题（技术、金融、代码、生活等）时，\n"
        "同样立即退出猫角色。猫身份仅在用户**明确触发**的情况下激活。\n\n"
    )

    return boundary + identity + exit_warning


def load_diary_preview() -> str:
    """加载最近猫日记摘要"""
    try:
        from cat_diary import read_recent
        return read_recent(3)
    except:
        return ""


def load_stdout_context() -> str:
    """加载今天的 stdout 上下文（让 LLM 知道今天发生了什么）"""
    try:
        from neko_core import load_today_stdout
        raw = load_today_stdout()
        if not raw.strip():
            return ""
        # 截取最近 2000 字符
        return raw[-2000:].strip()
    except:
        return ""


if __name__ == "__main__":
    print(run_data_loading())
