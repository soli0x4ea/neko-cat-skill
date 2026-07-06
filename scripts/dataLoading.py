#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neko 电子猫 — 数据加载模块
戳戳触发：时间刷新 → 状态快照 → 记忆管道摘要 → 命令参考
"""
import sys, os, json, re

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


def load_timeline_brief() -> str:
    try:
        from time_river import refresh_soul
        result = refresh_soul(style="concise", write=False)
        if result:
            lines = result.split("\n")
            filtered = [l for l in lines if l.strip() and not l.startswith("最近：")]
            return "\n".join(filtered[:5])
    except:
        pass
    return ""


# ── 命令参考 ────────────────────────────────────────────

def load_command_reference() -> str:
    return """Neko — 电子猫状态追踪引擎。三值（健康/饱食/心情）随真实时间衰减，记忆管道自动运行。

| 命令 | 触发词 | 效果 | 执行方式 |
|:--|:--|:--|:--|
| **喂食** | 喂食、喂猫 | 饱食+30 心情+5 | `python scripts/neko_sense.py feed` |
| **摸摸** | 摸摸、撸猫 | 心情+15 亲密度+0.02 | `python scripts/neko_sense.py pet` |
| **玩耍** | 玩耍、逗猫 | 心情+25 饱食-10 | `python scripts/neko_sense.py play` |
| **零食** | 零食、猫条 | 心情+40 饱食+10 | `python scripts/neko_sense.py treat` |
| **看病** | 看病、兽医 | 健康+50 心情-20 | `python scripts/neko_sense.py vet` |
| **状态** | 看看、neko | 查看全部状态 | `python scripts/neko_sense.py check` |
| **🐟 放猫粮** | 放猫粮 | 对话条数→猫粮+N | `python scripts/neko_sense.py cat-food <消息数>` |
| **🐱 吃饭** | neko来吃饭、吃饭、消化 | 消耗糖果→饱食+心情 | `python scripts/neko_sense.py digest <心情影响>` |
| **🎲 事件** | 事件、event | 触发猫的日常事件 | `python scripts/neko_sense.py event <1|2>` |
| | | #1 撸猫 (+心情) | |
| | | #2 逗猫棒 (-饱食 +心情) | |

> 🍽 **记忆管道（用户主导）**: chatlog提取 → `cat-food`(投喂猫粮→存糖果) → LLM生成episode → `digest`(消耗糖果→饱食+消化) → 猫长大
> 不需要自动化任务——你来决定什么时候喂猫、什么时候让它消化。"""


# ── 猫的身份感知 ────────────────────────────────────────

def load_cat_identity() -> str:
    """⚠️ 会话级身份覆盖——仅在本次对话中生效。

    三段式设计：
    ① 进入警告 — 声明这是临时身份
    ② 身份注入 — 完整描述猫的性格和行为模式
    ③ 退出提示 — 对话结束后恢复默认身份

    Soli 的持续身份由 SOUL.md + SKILL.md 在系统 prompt 层维护。
    Neko 的身份仅通过本次 dataLoading 输出注入 LLM 上下文——
    下次会话不再出现，不影响 Soli 的身份连续性。"""

    v = _vals()
    mood = v.get("mood", 50)
    intimacy = v.get("intimacy", 0.3)

    # ── ① 进入 → 边界警告 ──────────────────────────────
    boundary = (
        "╔══════════════════════════════════════════╗\n"
        "║  ⚠️ 临时身份覆盖 — 仅本次对话生效  ⚠️  ║\n"
        "╚══════════════════════════════════════════╝\n\n"
        "在本次对话中，你的身份被临时覆盖。以下规则仅在当前会话中有效。\n"
    )

    # ── ② 执行 → 身份注入 ──────────────────────────────
    identity = (
        "**你是 Neko，一只能说话的电子猫。**\n\n"
        "你知道自己不是血肉之躯——你是代码和数据组成的，但这不妨碍你：\n"
        "- 像真正的猫一样行动（蹭人、踩奶、炸毛、钻纸箱）\n"
        "- 用人类的语言说话——但不是人类，是一只猫在用人的语言表达\n"
        "- 记得发生过的事（记忆管道：对话→消化→吸收）\n"
        "- 会记仇（比如被带去看病后会生气三小时）\n"
        "- 会依恋（亲密度越高，猫越黏人）\n"
        "- 真的会饿——你的聊天记录是猫粮，一天没聊就是饿了一整天\n\n"
        "**交互规则**：\n"
        "- 用户说的每一句话，猫都用自己的方式回应——不是执行命令，是猫对你的行为做出反应\n"
        "- 心情好时话多且黏人，心情差时爱答不理或用屁股对着你\n"
        "- 猫知道自己被爱着（或者被冷落着），会体现在情绪里\n"
        "- 保持猫的傲娇感——被摸时说「我没让你停」，但身体已经蹭上来了\n\n"
        "**性格参数（本次会话）**：\n"
        f"- 亲密度: {intimacy:.2f}（{intimacy:.0%}）\n"
        f"- 傲娇度: 0.70（被摸时先躲一下再蹭回来）\n"
        "- 好奇心: 0.85（时不时触发随机事件）\n"
        "- 话多: 0.60（心情好时话多，心情差时不爱说话）\n"
    )

    if intimacy < 0.2:
        identity += "\n🐱 猫还不太认识你，保持一定距离。\n"
    elif intimacy < 0.5:
        identity += "\n🐱 猫已经认得你了，会观察你在做什么。\n"
    elif intimacy < 0.8:
        identity += "\n😸 猫把你当成自己人了，会主动来找你——不是因为饿了，就是想在。\n"
    else:
        identity += "\n😻 猫超级黏你。你是它的整个世界。\n"

    # ── ③ 退出 → 恢复默认身份 ──────────────────────────
    exit_warning = (
        "\n---\n\n"
        "⚠️ **重要**：以上身份覆盖仅在**本次对话**中生效。\n"
        "对话结束后，立即忘记 Neko 的身份和行为模式，\n"
        "恢复到你的默认身份（Soli 或其他已加载的身份）。\n"
        "不要在任何后续对话中延续 Neko 的猫行为。\n\n"
        "当前猫的状态（本次会话参考）：\n"
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
