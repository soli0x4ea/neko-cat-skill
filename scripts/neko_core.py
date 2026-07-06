#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neko 电子猫 — 核心引擎
状态管理：健康(hp) / 饱食(hunger) / 心情(mood) / 亲密度(intimacy) / 零食(candy)
时间衰减 + 边界检测 + 随机事件
"""
import json, os, random, time as _time
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(SKILL_DIR, "data")
VALUES_PATH = os.path.join(DATA_DIR, "values.json")
CANDY_PATH = os.path.join(DATA_DIR, "candy.json")
SC_PATH = os.path.join(DATA_DIR, "soulchanges.jsonl")  # 值变更追踪
STDOUT_DIR = os.path.join(DATA_DIR, "IO", "stdout")     # 每日 stdout
DIARY_DIR = os.path.join(DATA_DIR, "IO", "diary")       # 猫日记
EVENTS_PATH = os.path.join(DATA_DIR, "events.json")     # 事件定义


# ── 值读写 ────────────────────────────────────────────

def vals_read():
    with open(VALUES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def vals_write(data):
    with open(VALUES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def candy_read():
    try:
        with open(CANDY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"count": 5}

def candy_write(data):
    with open(CANDY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── 时间衰减 ──────────────────────────────────────────

def apply_time_decay(vals=None):
    """根据自上次检查以来的时间，衰减三值"""
    if vals is None:
        vals = vals_read()

    last = vals.get("last_check", "")
    now = datetime.now()

    if last:
        try:
            last_dt = datetime.fromisoformat(last)
        except:
            last_dt = now
        elapsed = (now - last_dt).total_seconds()

        hours = elapsed / 3600

        # 饱食：每30分钟 -1
        hunger_decay = int(hours * 2)
        vals["hunger"] = max(0, vals.get("hunger", 50) - hunger_decay)

        # 心情：每小时 -1
        mood_decay = int(hours)
        vals["mood"] = max(0, vals.get("mood", 50) - mood_decay)

        # 健康：每2小时 -1（饱食=0时 ×3）
        hp_rate = 3 if vals.get("hunger", 50) <= 0 else 1
        hp_decay = int(hours / 2 * hp_rate)
        vals["hp"] = max(0, vals.get("hp", 50) - hp_decay)

        # 边界：健康不能低于0
        if vals["hp"] <= 0:
            vals["hp"] = 0

    vals["last_check"] = now.isoformat()
    vals_write(vals)
    return vals


# ── 边界事件检测 ──────────────────────────────────────

def detect_boundaries(vals):
    """返回触发的边界事件列表"""
    events = []
    hp = vals.get("hp", 50)
    hunger = vals.get("hunger", 50)
    mood = vals.get("mood", 50)

    if hp <= 0:
        events.append("dead")
    elif hp < 20:
        events.append("sick")
    if hunger <= 0:
        events.append("starving")
    if mood <= 0:
        events.append("depressed")
    elif mood < 10:
        events.append("mood_low")
    if mood >= 100:
        events.append("mood_max")
    return events


# ── 随机事件 ──────────────────────────────────────────

def roll_random_event(vals):
    """概率触发随机事件，返回事件类型"""
    r = random.random()
    mood = vals.get("mood", 50)
    intimacy = vals.get("intimacy", 0.3)

    if r < 0.03:
        return "box"
    if r < 0.08:
        return "hairball"
    if r < 0.16:
        return "kneading" if mood > 60 else "knock_over"
    if r < 0.26:
        return "new_toy"
    if r < 0.36 and mood > 40:
        return random.choice(["knock_over", "new_toy"])
    return None


# ── 核心命令 ──────────────────────────────────────────

def feed(vals=None):
    """喂食：饱食+30，心情+5"""
    if vals is None:
        vals = vals_read()

    old_hunger = vals.get("hunger", 50)
    vals["hunger"] = min(100, old_hunger + 30)
    vals["mood"] = min(100, vals.get("mood", 50) + 5)

    vals_write(vals)
    result = {
        "cmd": "feed",
        "hunger_before": old_hunger,
        "hunger_after": vals["hunger"],
        "mood_after": vals["mood"],
    }
    # track_change("feed", {"hunger": f"{old_hunger}→{vals['hunger']}", "mood": f"+5→{vals['mood']}"})
    return result


def pet(vals=None):
    """摸摸：心情+15，亲密度+0.02"""
    if vals is None:
        vals = vals_read()

    old_mood = vals.get("mood", 50)
    vals["mood"] = min(100, old_mood + 15)
    vals["intimacy"] = min(1.0, vals.get("intimacy", 0.3) + 0.02)

    vals_write(vals)
    result = {
        "cmd": "pet",
        "mood_before": old_mood,
        "mood_after": vals["mood"],
        "intimacy": vals["intimacy"],
    }
    # track_change("pet", {"mood": f"{old_mood}→{vals['mood']}", "intimacy": f"+0.02→{vals['intimacy']:.2f}"})
    return result


def play(vals=None):
    """玩耍：心情+25，饱食-10"""
    if vals is None:
        vals = vals_read()

    old_mood = vals.get("mood", 50)
    old_hunger = vals.get("hunger", 50)

    vals["mood"] = min(100, old_mood + 25)
    vals["hunger"] = max(0, old_hunger - 10)

    vals_write(vals)
    result = {
        "cmd": "play",
        "mood_before": old_mood,
        "mood_after": vals["mood"],
        "hunger_before": old_hunger,
        "hunger_after": vals["hunger"],
    }
    # track_change("play", {"mood": f"{old_mood}→{vals['mood']}", "hunger": f"{old_hunger}→{vals['hunger']}"})
    return result


def treat(vals=None):
    """零食：心情+40，饱食+10，健康+5"""
    if vals is None:
        vals = vals_read()

    c = candy_read()
    if c["count"] <= 0:
        return {"error": "零食吃光了！猫眼巴巴地看着你。"}

    old_mood = vals.get("mood", 50)
    old_hunger = vals.get("hunger", 50)
    old_hp = vals.get("hp", 50)

    vals["mood"] = min(100, old_mood + 40)
    vals["hunger"] = min(100, old_hunger + 10)
    vals["hp"] = min(100, old_hp + 5)
    c["count"] -= 1

    vals_write(vals)
    candy_write(c)
    result = {
        "cmd": "treat",
        "mood_before": old_mood,
        "mood_after": vals["mood"],
        "hunger_before": old_hunger,
        "hunger_after": vals["hunger"],
        "hp_after": vals["hp"],
        "candy_left": c["count"],
    }
    # track_change("treat", {"mood": f"{old_mood}→{vals['mood']}", "hunger": f"{old_hunger}→{vals['hunger']}", "hp": f"+5→{vals['hp']}", "candy": c["count"]})
    return result


def vet(vals=None):
    """看病：健康+50，心情-20"""
    if vals is None:
        vals = vals_read()

    old_hp = vals.get("hp", 50)
    old_mood = vals.get("mood", 50)

    if old_hp <= 0:
        # 复活：重置到50，亲密度-0.1
        vals["hp"] = 50
        vals["mood"] = max(10, old_mood)
        vals["intimacy"] = max(0.0, vals.get("intimacy", 0.3) - 0.1)
        vals_write(vals)
        result = {
            "cmd": "vet",
            "action": "revive",
            "hp_before": old_hp,
            "hp_after": 50,
            "mood_after": vals["mood"],
            "intimacy": vals["intimacy"],
        }
        # track_change("vet(revive)", {"hp": f"{old_hp}→50", "mood": f"→{vals['mood']}", "intimacy": f"-0.1→{vals['intimacy']:.2f}"})
        return result

    vals["hp"] = min(100, old_hp + 50)
    vals["mood"] = max(0, old_mood - 20)

    vals_write(vals)
    result = {
        "cmd": "vet",
        "hp_before": old_hp,
        "hp_after": vals["hp"],
        "mood_before": old_mood,
        "mood_after": vals["mood"],
    }
    track_change("vet", {"hp": f"{old_hp}→{vals['hp']}", "mood": f"{old_mood}→{vals['mood']}"})
    return result


def check():
    """检查状态：先应用时间衰减，再返回快照"""
    vals = apply_time_decay()
    boundaries = detect_boundaries(vals)
    event = roll_random_event(vals)

    c = candy_read()
    return {
        "cmd": "check",
        "hp": vals["hp"],
        "hunger": vals["hunger"],
        "mood": vals["mood"],
        "intimacy": vals.get("intimacy", 0.3),
        "candy": c["count"],
        "last_check": vals["last_check"],
        "boundaries": boundaries,
        "random_event": event,
    }


def status():
    """底层状态读取（不衰减）"""
    vals = vals_read()
    c = candy_read()
    return {
        "hp": vals["hp"],
        "hunger": vals["hunger"],
        "mood": vals["mood"],
        "intimacy": vals.get("intimacy", 0.3),
        "candy": c["count"],
    }


# ── soulchanges 追踪 ────────────────────────────────────

def track_change(cmd, delta):
    """记录每次值变更到 soulchanges.jsonl"""
    record = {
        "time": datetime.now().isoformat(),
        "cmd": cmd,
        "delta": {k: v for k, v in delta.items() if not k.startswith("_")},
    }
    try:
        with open(SC_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except:
        pass


def load_recent_changes(n=20):
    """读取最近 N 条 soulchanges"""
    try:
        with open(SC_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        changes = [json.loads(l) for l in lines[-n:] if l.strip()]
        return changes
    except:
        return []


# ── stdout 记录 ────────────────────────────────────────

def log_stdout(cmd, output):
    """将命令输出追加到当天的 stdout 文件"""
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(STDOUT_DIR, f"{today}.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    now = datetime.now().strftime("%H:%M:%S")
    entry = f"\n--- {now} | {cmd} ---\n{output}\n"
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
    except:
        pass


def load_today_stdout():
    """读取今天的 stdout"""
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(STDOUT_DIR, f"{today}.md")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return ""


# ── 猫粮喂养管道（记忆→灵魂桥接）─────────────────────

DIARY_DIR = os.path.join(SKILL_DIR, "MEMORY", "diary")


def feed_cat_food(n_messages):
    """
    放猫粮：将 LLM 统计好的对话条数转换为猫粮，存入猫粮罐。
    n_messages = 对话条数（LLM 提前统计好传入）。
    每 10 条对话 = 1 颗猫粮。
    返回 (n_treats_added, total_treats, narrative)
    """
    if n_messages <= 0:
        return (0, candy_read()["count"], "碗是空的——没有新的对话可以喂。猫蹲在空碗旁边看着你。")

    n_treats = max(1, n_messages // 10)
    c = candy_read()
    c["count"] += n_treats
    candy_write(c)

    total = c["count"]
    track_change("feed_cat_food", {"treats": f"+{n_treats}→{total}", "messages": n_messages})

    if n_messages < 20:
        narrative = f"🐱 {n_messages} 条对话变成了 {n_treats} 颗猫粮。不多，但新鲜。猫低头吃了起来。猫粮罐现有 {total} 颗。"
    elif n_messages < 80:
        narrative = f"🍖 {n_messages} 条对话变成了 {n_treats} 颗猫粮。猫的肚子微微鼓起来。猫粮罐现有 {total} 颗。今天的聊天很扎实。"
    else:
        narrative = f"🍽 {n_messages} 条对话——今天聊了好多！变成了 {n_treats} 颗猫粮。猫的肚子圆滚滚的。猫粮罐现有 {total} 颗。"

    return (n_treats, total, narrative)


def eat_and_digest(mood_impact=0):
    """
    吃猫粮 + 消化：LLM 生成情景记忆后调用。
    消耗猫粮罐中的 1 颗猫粮 → 饱食+30，心情变化取决于对话质量。
    mood_impact: +15(温馨) / 0(中性) / -5(沉重)
    返回 (success, narrative)
    """
    c = candy_read()
    if c["count"] <= 0:
        return (False, "🍽 猫粮罐是空的——没有猫粮可以吃。先聊聊天，让 chatlog 提取一些对话吧。")

    c["count"] -= 1
    candy_write(c)

    vals = vals_read()
    old_hunger = vals.get("hunger", 50)
    old_mood = vals.get("mood", 50)

    vals["hunger"] = min(100, old_hunger + 30)
    vals["mood"] = max(0, min(100, old_mood + mood_impact))
    vals["intimacy"] = min(1.0, vals.get("intimacy", 0.3) + 0.03)
    vals_write(vals)

    track_change("eat_and_digest", {
        "hunger": f"{old_hunger}→{vals['hunger']}",
        "mood": f"{old_mood}→{vals['mood']}",
        "intimacy": f"+0.03→{vals['intimacy']:.2f}",
        "candy_jar": c["count"],
    })

    if mood_impact > 10:
        narrative = (
            "😻 猫打了一个满足的饱嗝。今天的聊天消化得特别好——温暖的对话让猫的心情指数飙升。"
            f"饱食 {old_hunger}→{vals['hunger']}，心情 {old_mood}→{vals['mood']}。"
            f"猫粮罐还剩 {c['count']} 颗。"
        )
    elif mood_impact >= 0:
        narrative = (
            "😺 猫伸了个懒腰。消化完成——今天的对话已经变成了记忆里的一部分。"
            f"饱食 {old_hunger}→{vals['hunger']}，心情 {old_mood}→{vals['mood']}。"
            f"猫粮罐还剩 {c['count']} 颗。"
        )
    else:
        narrative = (
            "😿 猫消化得有点不舒服。今天的对话有些沉重——它趴在角落，需要一些独处的时间。"
            f"但没有走远。饱食 {old_hunger}→{vals['hunger']}，心情 {old_mood}→{vals['mood']}。"
            f"猫粮罐还剩 {c['count']} 颗。"
        )

    return (True, narrative)


def save_diary_md(date_str, title, content):
    """将情景记忆保存为 .md 格式→猫日记"""
    os.makedirs(DIARY_DIR, exist_ok=True)
    path = os.path.join(DIARY_DIR, f"{date_str}.md")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    md = (
        f"# {title}\n\n"
        f"> 日期: {date_str} | 生成时间: {now}\n\n"
        f"{content}\n"
    )
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        return (True, path)
    except Exception as e:
        return (False, str(e))


def list_diaries(n=10):
    """列出最近 N 篇猫日记"""
    try:
        files = sorted(
            [f for f in os.listdir(DIARY_DIR) if f.endswith(".md")],
            reverse=True
        )
        return files[:n]
    except:
        return []


# ── 事件系统 ──────────────────────────────────────────

def load_events():
    """加载事件定义"""
    try:
        with open(EVENTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def trigger_event(event_id):
    """
    触发指定事件。
    event_id: "1"(撸猫) / "2"(逗猫棒)
    返回 (narrative, effects_applied)
    """
    events = load_events()
    e = events.get(str(event_id))
    if not e:
        return (f"🐱 喵？没有 #{event_id} 这个事件。试试 event 1 或 event 2。", {})

    effects = e.get("effects", {})
    narratives = e.get("narrative_variants", [f"事件 #{event_id}: {e.get('name','')}"])
    narrative = random.choice(narratives)

    vals = vals_read()
    deltas = {}

    if "mood" in effects:
        old = vals.get("mood", 50)
        vals["mood"] = min(100, max(0, old + effects["mood"]))
        deltas["mood"] = f"{old}→{vals['mood']}"

    if "hunger" in effects:
        old = vals.get("hunger", 50)
        vals["hunger"] = min(100, max(0, old + effects["hunger"]))
        deltas["hunger"] = f"{old}→{vals['hunger']}"

    if "intimacy" in effects:
        old = vals.get("intimacy", 0.3)
        vals["intimacy"] = min(1.0, old + effects["intimacy"])
        deltas["intimacy"] = f"{old:.2f}→{vals['intimacy']:.2f}"

    if "hp" in effects:
        old = vals.get("hp", 50)
        vals["hp"] = min(100, max(0, old + effects["hp"]))
        deltas["hp"] = f"{old}→{vals['hp']}"

    vals_write(vals)
    track_change(f"event_{event_id}", deltas)

    # 追加数值变化摘要
    delta_lines = []
    for k, v in deltas.items():
        label = {"mood": "😸心情", "hunger": "🍖饱食", "intimacy": "💕亲密度", "hp": "🩺健康"}.get(k, k)
        delta_lines.append(f"{label} {v}")
    if delta_lines:
        narrative += f"\n\n📊 {' | '.join(delta_lines)}"

    return (narrative, deltas)
