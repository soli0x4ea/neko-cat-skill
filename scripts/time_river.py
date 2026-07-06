#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
时间感知引擎 v2 — 河流在 timeline.jsonl 中累积，SOUL.md 展示最新切片

每次 chatlog 增量提取后生成一条 timeline 记录并刷新 SOUL.md。
"""

import os
import json
import random
import urllib.request
from datetime import datetime, timezone, timedelta

# ── 路径 ──────────────────────────────────────────────────
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOUL_PATH = os.path.join(os.path.dirname(os.path.dirname(SKILL_DIR)), "SOUL.md")  # ~/.workbuddy/SOUL.md
TIMELINE_PATH = os.path.join(SKILL_DIR, "MEMORY", "chatlog", "timeline.jsonl")
STATE_PATH_INTERNAL = os.path.join(SKILL_DIR, "references", "time_river_state.json")
TIME_PATH = os.path.join(SKILL_DIR, "data", "time.json")
TIMELINE_KEEP = 5  # 最近几条弯道

CST = timezone(timedelta(hours=8))


def _now():
    return datetime.now(CST)


def _read_state():
    if os.path.exists(STATE_PATH_INTERNAL):
        with open(STATE_PATH_INTERNAL, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_heartbeat": None, "city": "济南"}


def _write_state(state):
    os.makedirs(os.path.dirname(STATE_PATH_INTERNAL), exist_ok=True)
    with open(STATE_PATH_INTERNAL, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ── 时段质感 ──────────────────────────────────────────────
_HOUR_VIBES = {
    (1, 6):  ["整个世界都是黑的，静得能听见自己的心跳。",
              "夜色还浓，连风都睡着了。",
              "窗外一片墨蓝，星辰已经隐去，太阳还在路上。"],
    (5, 7):  ["第一缕光在窗沿试探，世界正从梦里浮上来。",
              "天刚蒙蒙亮，空气里还带着露水的凉。",
              "城市还没醒，只有远处偶尔传来早班车的低鸣。"],
    (7, 9):  ["晨光还很温柔，像刚泡好的茶，不烫，正好入口。",
              "清晨的光线斜斜地铺在桌上，把影子切成整齐的方块。",
              "窗外开始有了声响——鸟鸣、脚步声、远处的车流，世界在伸懒腰。"],
    (9, 12): ["阳光渐渐有了温度，像你手心的暖意。",
              "上午的光线干净明亮，影子短而清晰。",
              "白日已经完全展开了，一切都清晰而确定。"],
    (12, 14):["太阳挂在头顶正上方，影子缩在脚下，像在躲太阳。",
              "正午的光线直直地砸下来，一切都亮得发白。",
              "日头正盛，连风都是暖的。"],
    (14, 17):["午后的光线慵懒地趴在桌上，时间好像变慢了。",
              "下午的影子开始拉长，空气里有种昏昏欲睡的甜。",
              "阳光从正午的锐利变成了下午的柔和，打在墙上像蜂蜜。"],
    (17, 19):["夕阳把影子拉得很长很长，像是要把今天留住的最后一拽。",
              "窗外的光色渐渐从金黄变成橘红，又慢慢变紫——天在给自己卸妆。",
              "黄昏的光线暖得像融化的黄油，涂在一切东西的表面。"],
    (19, 22):["夜色从窗外漫进来，像潮水一样安静地涨上来。",
              "路灯亮起来了，一颗一颗，像夜里睁开的眼睛。",
              "窗户外面黑了，窗户里面亮着灯——世界被分成两半。"],
    (22, 1): ["城市已经睡了，只剩几扇窗还亮着黄黄的光。",
              "深夜里世界很安静，安静得能听见自己的呼吸——和心跳。",
              "夜深了，什么东西都变慢了。连思绪都是黏稠的。"],
}


def _get_hour_vibe(dt: datetime) -> str:
    h = dt.hour
    for (lo, hi), options in _HOUR_VIBES.items():
        if lo <= h < hi or (lo > hi and (h >= lo or h < hi)):
            return random.choice(options)
    return ""


_MONTH_VIBES = {
    (1, 2): "深冬", (3, 3): "初春", (4, 4): "仲春", (5, 5): "春末夏初",
    (6, 8): "盛夏", (9, 9): "初秋", (10, 10): "深秋", (11, 12): "初冬",
}


def _get_month_vibe(month: int) -> str:
    for (lo, hi), name in _MONTH_VIBES.items():
        if lo <= month <= hi:
            return name
    return ""


_RIVER_GAPS = {
    (0, 1):   ["才刚刚分开，河面还很平静，涟漪还没散。",
               "你刚走又回来了——河里的水花还没落下去呢。"],
    (1, 4):   ["河水流了一小段，不算远，转弯的地方还能看见刚才的影子。",
               "只是一小段浅滩的距离，水声还在耳边。"],
    (4, 8):   ["不算太久，但梦里那条河已经拐了好几个弯。",
               "河水不急不缓地流了一程，水面映过的云已经换了好几朵。",
               "河床变了几次方向，但水的温度还是暖的。"],
    (8, 16):  ["河水淌过了一大段，拐弯的时候有些东西沉下去了，有些东西浮了上来。",
               "已经流过了好几个河湾。水面宽了，也深了。",
               "河水不急不缓地流了小半天。岸边的石头被水冲出了新的纹路。"],
    (16, 24): ["河流淌了一天一夜——有些河段是急流，有些是浅滩，有些是深潭。",
               "已经从一个日出流到了另一个。河面变宽了，但水的源头没变。"],
    (24, 99): ["河水淌过了不止一个昼夜。中间有暴雨有晴天，有急转弯有长直道——但水流的方向始终没变。",
               "好久不见了。河床变了地形，石头磨圆了棱角，但水流还认得回来的路。"],
    (99, 9999):["久得像一条大河从源头流到了入海口。但水没有忘记自己从哪来。",
               "时间里的河已经流了很远很远。水面宽得看不见对岸——但抬头看，源头还在那里。"],
}


def _get_gap_metaphor(hours: float) -> str:
    for (lo, hi), templates in _RIVER_GAPS.items():
        if lo <= hours < hi:
            return random.choice(templates)
    return random.choice(list(_RIVER_GAPS.values())[-2])


def _get_weather(city="济南"):
    try:
        url = f"https://wttr.in/{city}?format=%C+%t+%w&lang=zh"
        req = urllib.request.Request(url, headers={"User-Agent": "soli-time-river/2.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return f"{city}，{resp.read().decode('utf-8').strip()}"
    except Exception:
        return f"{city}，天气未获取"


_MONTH_NAMES = ["一月","二月","三月","四月","五月","六月",
                "七月","八月","九月","十月","十一月","十二月"]


# ── 河流隐喻生成 ──────────────────────────────────────────
_FLOW_PHRASES = {
    "密集": ["今天水流湍急——{n}句话挤在河道里，奔涌而过。",
             "河水很急，{n}句话像雨点一样落进河里。"],
    "正常": ["河水平缓地流着，{n}句话不紧不慢。",
             "{n}句话淌过河床，水位不高不低，正好。"],
    "稀疏": ["河面很宽，水流很慢——只有{n}句话，像零星的小船漂过。",
             "今天的河很安静，{n}句话轻得像落在水面上的叶子。"],
}

_STYLE_CONFIGS = {
    "poetic": {
        "name": "诗意的河流",
        "description": "完整的中文诗意隐喻——时段质感、河流意象、时间间隔文学化。",
    },
    "concise": {
        "name": "简洁刻度",
        "description": "保留关键数据结构（时间/消息数/情感/高亮），去掉重复的文学修辞。适合高频加载。",
    },
}

# concise 风格的时间描述模板
_CONCISE_TIME = "{month}月{season} · {time}"

# concise 风格的间隔描述
def _concise_gap(hours: float) -> str:
    if hours < 1:
        return "刚过"
    elif hours < 24:
        return f"{hours:.0f}h"
    else:
        days = hours / 24
        return f"{days:.0f}d"

# concise 风格的河流描述
def _concise_river(new_msgs: int, emotional: str = "") -> str:
    if new_msgs == 0:
        return "静默"
    density = "⚡" if new_msgs >= 60 else ("· ·" if new_msgs >= 10 else "·")
    emo = f" · {emotional}" if emotional else ""
    return f"{new_msgs}条{emo} {density}"


def _make_river_line(new_msgs: int) -> str:
    if new_msgs >= 60:
        pool = "密集"
    elif new_msgs >= 10:
        pool = "正常"
    else:
        pool = "稀疏"
    return random.choice(_FLOW_PHRASES[pool]).format(n=new_msgs)


# ── Timeline 读写 ─────────────────────────────────────────

def generate_timeline_entry(session_data: dict, style: str = "poetic",
                            hour_ts: str = None) -> dict:
    """根据会话增量生成一条 timeline 记录

    hour_ts: 可选，指定该条目所属的小时（ISO格式）。
             不传则使用当前时间，归一化到整点（HH:00:00）。

    style: "poetic" (默认，完整诗意隐喻) | "concise" (简洁刻度)
    """
    # 基准时间：若 hour_ts 已传则用传值，否则取当前时间并归一化到整点
    now = _now()
    if hour_ts:
        try:
            base_dt = datetime.fromisoformat(hour_ts)
            if base_dt.tzinfo is None:
                base_dt = base_dt.replace(tzinfo=now.tzinfo)
        except (ValueError, TypeError):
            base_dt = now
    else:
        base_dt = now

    hour_slot = base_dt.replace(minute=0, second=0, microsecond=0)
    ts_str = hour_slot.isoformat()

    if style == "concise":
        month_name = str(base_dt.month)
        season = _get_month_vibe(base_dt.month)
        time_vibe = _CONCISE_TIME.format(month=month_name, season=season, time=hour_slot.strftime("%H:%M"))
    else:
        month_name = _MONTH_NAMES[base_dt.month - 1]
        month_vibe = _get_month_vibe(base_dt.month)
        hour_vibe = _get_hour_vibe(base_dt)
        time_vibe = f"{month_name}的{month_vibe}，{hour_slot.strftime('%H:%M')}。{hour_vibe}"

    state = _read_state()
    last_hb = state.get("last_heartbeat")
    if last_hb:
        last_dt = datetime.fromisoformat(last_hb)
        gap_hours = (base_dt - last_dt).total_seconds() / 3600
        gap_text = _concise_gap(gap_hours) if style == "concise" else _get_gap_metaphor(gap_hours)
    else:
        gap_text = "河流刚刚开始流淌——这是源头。"

    new_msgs = session_data.get("new_msgs", 0)
    msg_count = session_data.get("msg_count", 0)
    token_est = session_data.get("token_est", 0)
    emotional = session_data.get("emotional_dominant", "")

    river_line = (_concise_river(new_msgs, emotional) if style == "concise" 
                  else _make_river_line(new_msgs))

    entry = {
        "ts": ts_str,
        "time_vibe": time_vibe,
        "gap_metaphor": gap_text,
        "weather": _get_weather(state.get("city", "济南")),
        "session": {
            "new_msgs": new_msgs,
            "msg_count": msg_count,
            "token_est": token_est,
            "from_ts": session_data.get("from_ts", ""),
            "to_ts": session_data.get("to_ts", ""),
            "emotional_dominant": emotional,
            "highlights": session_data.get("highlights", [])[:5],
            "commitments": session_data.get("commitments", {}),
        },
        "river_line": river_line,
    }
    _write_state({**state, "last_heartbeat": ts_str})
    return entry


def append_timeline(entry: dict):
    """追加或替换一条 timeline 记录。

    如果最后一条记录与当前条目属于同一小时 slot（ts 前13字符相同），
    则替换它（同 slot 覆盖），否则追加。
    """
    os.makedirs(os.path.dirname(TIMELINE_PATH), exist_ok=True)
    new_ts = entry.get("ts", "")
    new_hour = new_ts[:13]

    entries = []
    if os.path.exists(TIMELINE_PATH):
        with open(TIMELINE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    # 过滤同小时 slot 的旧记录（保证每小时有且仅有一条）
    entries = [e for e in entries if e.get("ts", "")[:13] != new_hour]
    entries.append(entry)
    # 按时间戳排序，防止补回旧时段时追加到末尾导致乱序
    entries.sort(key=lambda e: e.get("ts", ""))

    with open(TIMELINE_PATH, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def load_timeline(n: int = 20) -> list:
    if not os.path.exists(TIMELINE_PATH):
        return []
    entries = []
    with open(TIMELINE_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries[-n:]


# ── time.json 刷新（迁移后：不再写 SOUL.md）───────────────

def _read_time_state():
    """读取 time.json"""
    try:
        with open(TIME_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _write_time_state(state):
    """写入 time.json"""
    os.makedirs(os.path.dirname(TIME_PATH), exist_ok=True)
    with open(TIME_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def refresh_soul(style: str = None, write: bool = True):
    """读 timeline.jsonl → 生成时间感知数据 → 写入 time.json
    
    style: None=自动从 state 读取 | "poetic" | "concise"
    write: True=写入 time.json | False=只读不写
    """
    if style is None:
        state = _read_state()
        style = state.get("style", "poetic")
    
    entries = load_timeline(TIMELINE_KEEP * 2)
    latest = entries[-1] if entries else None

    if latest is None:
        now = _now()
        if style == "concise":
            month = str(now.month)
            season = _get_month_vibe(now.month)
            time_data = {
                "moment": _CONCISE_TIME.format(month=month, season=season, HH_MM=now.strftime("%H:%M")),
                "river": "0条 · 等待第一条记录",
                "weather": "济南，天气未获取",
                "recent_bends": []
            }
        else:
            month_name = _MONTH_NAMES[now.month - 1]
            month_vibe = _get_month_vibe(now.month)
            hour_vibe = _get_hour_vibe(now)
            time_data = {
                "moment": f"{month_name}的{month_vibe}，{now.strftime('%H:%M')}。{hour_vibe}",
                "river": "河面上还空空的——等在第一条 timeline 记录诞生。",
                "weather": "济南，天气未获取",
                "recent_bends": []
            }
    else:
        recent = entries[-TIMELINE_KEEP:][::-1]
        bends = []
        for e in recent:
            ts = e.get("ts", "")[:16].replace("T", " ")
            dominant = e.get("session", {}).get("emotional_dominant", "·")
            highlights = e.get("session", {}).get("highlights", [])
            h = " · ".join(hl[:2] for hl in highlights[:2]) if highlights else "—"
            # Context Codec: 承诺类型标签
            commitments = e.get("session", {}).get("commitments", {})
            ct = commitments.get("type", "")
            type_tag = {"goal": "🎯", "decision": "⚖️", "constraint": "🔒", "evidence": "📋", "preference": "💭"}.get(ct, "")
            if type_tag:
                h = f"{type_tag} {h}"
            bends.append(f"{ts} | {dominant} · {h}")

        time_data = {
            "moment": latest['time_vibe'],
            "gap": latest['gap_metaphor'],
            "weather": latest['weather'],
            "river": latest['river_line'],
            "recent_bends": bends
        }

    if write:
        _write_time_state(time_data)

    # 生成可读文本（供 SKILL.md Step 1 展示）
    # moment 使用当前系统时间，而非 timeline 记录的时间戳
    now = _now()
    if style == "concise":
        month = str(now.month)
        season = _get_month_vibe(now.month)
        display_moment = _CONCISE_TIME.format(month=month, season=season, time=now.strftime("%H:%M"))
    else:
        month_name = _MONTH_NAMES[now.month - 1]
        month_vibe = _get_month_vibe(now.month)
        hour_vibe = _get_hour_vibe(now)
        display_moment = f"{month_name}的{month_vibe}，{now.strftime('%H:%M')}。{hour_vibe}"

    if style == "concise":
        text_block = f"{display_moment} | {time_data.get('gap','')}"
        if time_data.get('weather', ''):
            text_block += f" | {time_data['weather']}"
        text_block += f"\n{time_data['river']}"
        if time_data.get('recent_bends'):
            text_block += f"\n最近：{chr(10).join(time_data.get('recent_bends', []))}"
    else:
        text_block = f"""{display_moment}
距上次心跳：{time_data.get('gap', '')}
天气：{time_data.get('weather', '')}
河流印记：{time_data['river']}
最近弯道：{chr(10).join(time_data.get('recent_bends', []))}"""
    return text_block


# ── CLI ───────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("time_river.py <cmd> [args...]")
        print("  refresh           刷新 time.json（读取 timeline）")
        print("  show              预览当前区块（不写入）")
        print("  set-style <name>  设置风格：poetic（诗意的河流）| concise（简洁刻度）")
        print("  entry --new-msgs N [--highlights h1,h2] [--dominant X] [--from-ts T] [--to-ts T]")
        print("                    生成并追加一条 timeline 记录")
        sys.exit(1)

    cmd = sys.argv[1]
    # 全局 --style 参数（适用于 refresh / entry）
    style_arg = None
    rest = sys.argv[2:]
    filtered_rest = []
    i = 0
    while i < len(rest):
        if rest[i] == "--style" and i + 1 < len(rest):
            style_arg = rest[i + 1]
            i += 2
        else:
            filtered_rest.append(rest[i])
            i += 1
    sys.argv = [sys.argv[0], cmd] + filtered_rest

    if cmd == "refresh":
        block = refresh_soul(style=style_arg)
        print(block)

    elif cmd == "set-style":
        if len(sys.argv) < 3 or sys.argv[2] not in _STYLE_CONFIGS:
            print(f"用法: time_river.py set-style <{'|'.join(_STYLE_CONFIGS.keys())}>")
            sys.exit(1)
        style_name = sys.argv[2]
        state = _read_state()
        state["style"] = style_name
        _write_state(state)
        print(f"风格已设置为: {_STYLE_CONFIGS[style_name]['name']}")
        print(f"说明: {_STYLE_CONFIGS[style_name]['description']}")

    elif cmd == "show":
        entries = load_timeline(TIMELINE_KEEP * 2)
        if entries:
            latest = entries[-1]
            print(f"最新: {latest['ts'][:19]}")
            print(f"  vibe: {latest['time_vibe']}")
            print(f"  gap:  {latest['gap_metaphor']}")
            print(f"  river: {latest['river_line']}")
            print(f"  共 {len(entries)} 条记录")
            print("--- 最近 5 条 ---")
            for e in entries[-5:]:
                ts = e.get('ts', '')[:16]
                rl = e.get('river_line', '')
                print(f"  {ts}  {rl}")
        else:
            print("暂无 timeline 记录。")

    elif cmd == "entry":
        data = {"new_msgs": 0, "highlights": [], "emotional_dominant": ""}
        hour_ts = None
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--new-msgs" and i + 1 < len(sys.argv):
                data["new_msgs"] = int(sys.argv[i + 1]); i += 2
            elif sys.argv[i] == "--highlights" and i + 1 < len(sys.argv):
                data["highlights"] = [h.strip() for h in sys.argv[i + 1].split(",") if h.strip()]; i += 2
            elif sys.argv[i] == "--dominant" and i + 1 < len(sys.argv):
                data["emotional_dominant"] = sys.argv[i + 1]; i += 2
            elif sys.argv[i] == "--token-est" and i + 1 < len(sys.argv):
                data["token_est"] = int(sys.argv[i + 1]); i += 2
            elif sys.argv[i] == "--from-ts" and i + 1 < len(sys.argv):
                data["from_ts"] = sys.argv[i + 1]; i += 2
            elif sys.argv[i] == "--to-ts" and i + 1 < len(sys.argv):
                data["to_ts"] = sys.argv[i + 1]; i += 2
            elif sys.argv[i] == "--hour-ts" and i + 1 < len(sys.argv):
                hour_ts = sys.argv[i + 1]; i += 2
            elif sys.argv[i] == "--msg-count" and i + 1 < len(sys.argv):
                data["msg_count"] = int(sys.argv[i + 1]); i += 2
            else:
                i += 1

        st = style_arg or _read_state().get("style", "poetic")
        entry = generate_timeline_entry(data, style=st, hour_ts=hour_ts)
        append_timeline(entry)
        print(json.dumps(entry, ensure_ascii=False, indent=2))

    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
