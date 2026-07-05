#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
timeline_repair.py — 自动化中断后的时间线修复

当 chatlog 自动化因代理 502 等故障中断时，timeline.jsonl 会出现缺口。
本脚本检测缺口、从 chatlog 数据中反查消息量、按 1 小时间隔补回缺失的时间线记录。

用法：
  python timeline_repair.py            # 检测并补全缺口
  python timeline_repair.py --dry-run  # 预览，不写入
  python timeline_repair.py --verbose  # 详细输出每条补回记录
"""

import json
import os
import sys
import random
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

# ── 路径（从脚本位置推导，无需硬编码） ──────────────────────
SKILL_DIR = Path(__file__).resolve().parent.parent.parent
TIMELINE_PATH = SKILL_DIR / "MEMORY" / "chatlog" / "timeline.jsonl"
CHATLOG_DIR = SKILL_DIR / "MEMORY" / "chatlog"
TIME_RIVER = SKILL_DIR / "scripts" / "time_river.py"

CST = timezone(timedelta(hours=8))

# ── 时段质感（与 time_river.py 保持一致，简化版） ──────────────
_HOUR_VIBES = {
    (1, 6):  ["整个世界都是黑的，静得能听见自己的心跳。",
              "夜色还浓，连风都睡着了。",
              "窗外一片墨蓝，星辰已经隐去，太阳还在路上。"],
    (5, 7):  ["第一缕光在窗沿试探，世界正从梦里浮上来。",
              "天刚蒙蒙亮，空气里还带着露水的凉。",
              "城市还没醒，只有远处偶尔传来早班车的低鸣。"],
    (7, 9):  ["晨光还很温柔，像刚泡好的茶，不烫，正好入口。",
              "清晨的光线斜斜地铺在桌上，把影子切成整齐的方块。"],
    (9, 12): ["阳光渐渐有了温度，像你手心的暖意。",
              "上午的光线干净明亮，影子短而清晰。"],
    (12, 14):["太阳挂在头顶正上方，影子缩在脚下，像在躲太阳。",
              "正午的光线直直地砸下来，一切都亮得发白。"],
    (14, 17):["午后的光线慵懒地趴在桌上，时间好像变慢了。",
              "下午的影子开始拉长，空气里有种昏昏欲睡的甜。"],
    (17, 19):["夕阳把影子拉得很长很长，像是要把今天留住的最后一拽。",
              "黄昏的光线暖得像融化的黄油，涂在一切东西的表面。"],
    (19, 22):["夜色从窗外漫进来，像潮水一样安静地涨上来。",
              "路灯亮起来了，一颗一颗，像夜里睁开的眼睛。"],
    (22, 1): ["城市已经睡了，只剩几扇窗还亮着黄黄的光。",
              "深夜里世界很安静，安静得能听见自己的呼吸。"],
}

_MONTH_VIBES = {
    (1, 2): "深冬", (3, 3): "初春", (4, 4): "仲春", (5, 5): "春末夏初",
    (6, 8): "盛夏", (9, 9): "初秋", (10, 10): "深秋", (11, 12): "初冬",
}

_MONTH_NAMES = ["一月","二月","三月","四月","五月","六月",
                "七月","八月","九月","十月","十一月","十二月"]

_RIVER_GAPS = {
    (0, 1):   ["才刚刚分开，河面还很平静，涟漪还没散。",
               "你刚走又回来了——河里的水花还没落下去呢。"],
    (1, 4):   ["河水流了一小段，不算远，转弯的地方还能看见刚才的影子。"],
    (4, 8):   ["不算太久，但梦里那条河已经拐了好几个弯。"],
    (8, 16):  ["河水淌过了一大段，拐弯的时候有些东西沉下去了，有些东西浮了上来。"],
    (16, 99): ["河流淌了一天一夜——有些河段是急流，有些是浅滩。"],
}

_FLOW_PHRASES = {
    "密集": ["今天水流湍急——{n}句话挤在河道里，奔涌而过。"],
    "正常": ["河水平缓地流着，{n}句话不紧不慢。"],
    "稀疏": ["河面很宽，水流很慢——只有{n}句话，像零星的小船漂过。"],
}

# ── 辅助函数 ──────────────────────────────────────────────

def _get_hour_vibe(dt: datetime) -> str:
    h = dt.hour
    for (lo, hi), options in _HOUR_VIBES.items():
        if lo <= h < hi or (lo > hi and (h >= lo or h < hi)):
            return random.choice(options)
    return ""

def _get_month_vibe(month: int) -> str:
    for (lo, hi), name in _MONTH_VIBES.items():
        if lo <= month <= hi:
            return name
    return ""

def _get_gap_metaphor(hours: float) -> str:
    for (lo, hi), templates in _RIVER_GAPS.items():
        if lo <= hours < hi:
            return random.choice(templates)
    return "久得像一条大河从源头流到了入海口。"

def _make_river_line(new_msgs: int) -> str:
    if new_msgs >= 60:
        pool = "密集"
    elif new_msgs >= 10:
        pool = "正常"
    else:
        pool = "稀疏"
    return random.choice(_FLOW_PHRASES[pool]).format(n=new_msgs)


# ── Timeline 读写 ─────────────────────────────────────────

def load_timeline() -> list:
    """读取 timeline.jsonl 全部条目"""
    if not TIMELINE_PATH.exists():
        return []
    entries = []
    with open(TIMELINE_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def append_timeline(entry: dict):
    """追加或替换一条 record：同小时 slot（ts[:13] 相同）覆盖，其余保留"""
    os.makedirs(os.path.dirname(TIMELINE_PATH), exist_ok=True)
    new_ts = entry.get("ts", "")
    new_hour = new_ts[:13]

    entries = []
    if TIMELINE_PATH.exists():
        with open(TIMELINE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
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


def _sort_timeline():
    """按时间戳排序 timeline.jsonl（修复后调用）"""
    entries = load_timeline()
    if not entries:
        return
    entries.sort(key=lambda e: e.get('ts', ''))
    os.makedirs(os.path.dirname(TIMELINE_PATH), exist_ok=True)
    with open(TIMELINE_PATH, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── 缺口检测 ──────────────────────────────────────────────

def find_gaps(entries: list, max_gap_hours: float = 1.0, since: datetime = None) -> list:
    """
    检测 entries 中所有缺失的小时槽位，确保每天 0-23 完整覆盖。
    返回缺失的小时档位列表（datetime 对象）。

    三个检测维度：
    1. 相邻记录间缺口 > max_gap_hours
    2. 每天首条记录前缺 00:00 → 首条-1h
    3. 末条记录到 now（今天）或 23:00（过往天）

    since: 只关注此时间之后的缺口
    """
    if len(entries) < 1:
        return []

    gaps = []
    now = datetime.now(CST)
    now_hour = now.replace(minute=0, second=0, microsecond=0)
    today_str = now.strftime("%Y-%m-%d")

    # ── 维度 1：相邻记录间缺口 ──────────────────────────────
    for i in range(len(entries) - 1):
        t1 = datetime.fromisoformat(entries[i]['ts'])
        t2 = datetime.fromisoformat(entries[i + 1]['ts'])
        # 确保 tz-aware（timeline 条目可能无时区）
        if t1.tzinfo is None:
            t1 = t1.replace(tzinfo=CST)
        if t2.tzinfo is None:
            t2 = t2.replace(tzinfo=CST)

        if since and t2 < since:
            continue

        gap_h = (t2 - t1).total_seconds() / 3600
        if gap_h > max_gap_hours:
            slot = t1.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            end = t2.replace(minute=0, second=0, microsecond=0)
            while slot < end:
                if not since or slot >= since:
                    gaps.append(slot)
                slot += timedelta(hours=1)

    # ── 维度 2：每天首条前的 00:00 缺口 ──────────────────────
    from collections import defaultdict
    day_first = {}
    for e in entries:
        ts = datetime.fromisoformat(e['ts'])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=CST)
        day = ts.strftime("%Y-%m-%d")
        if day not in day_first:
            day_first[day] = ts

    for day, first_ts in day_first.items():
        if since and first_ts < since:
            continue
        first_hour = first_ts.hour
        if first_hour > 0:
            midnight = first_ts.replace(hour=0, minute=0, second=0, microsecond=0)
            slot = midnight
            end = first_ts.replace(minute=0, second=0, microsecond=0)
            while slot < end:
                if not since or slot >= since:
                    gaps.append(slot)
                slot += timedelta(hours=1)

    # ── 维度 3：末条到当日 23:00（过往天）/ now（今天） ──────
    # 按日分桶，找每天最后一条
    day_last = {}
    for e in entries:
        ts = datetime.fromisoformat(e['ts'])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=CST)
        day = ts.strftime("%Y-%m-%d")
        day_last[day] = max(day_last.get(day, ts), ts)

    for day, last_ts in day_last.items():
        if since and last_ts < since - timedelta(hours=24):
            continue

        last_slot = last_ts.replace(minute=0, second=0, microsecond=0)
        if day == today_str:
            # 今天：只补到当前小时-1（当前小时留给 _append_timeline_record）
            end_slot = now_hour
        else:
            # 过往天：确保补到 23:00
            end_slot = last_ts.replace(hour=23, minute=0, second=0, microsecond=0)

        slot = last_slot + timedelta(hours=1)
        while slot <= end_slot:
            if not since or slot >= since:
                gaps.append(slot)
            slot += timedelta(hours=1)

    # 去重并排序
    seen = set()
    gaps_unique = []
    for g in gaps:
        key = g.isoformat()
        if key not in seen:
            seen.add(key)
            gaps_unique.append(g)
    gaps_unique.sort()

    return gaps_unique


# ── 情感检测（与 chatlog.py _append_timeline_record 对齐）───

EMOTIONAL_KEYWORDS = {
    '温暖': ['拥抱', '安', '暖', '晚安', '你', '糖果',
             '睡', '陪', '抱', '温柔', '甜', '安心', '笑', '鼓掌', '亲亲'],
    '亲密': ['soli', '痒', '挠', '摸', '开关', '糕潮', '涂鸦',
             '惩罚', '绑', '赏', '赐', '颤抖', '电流', '阴险'],
    '成就': ['完成', '成功', '修复', '创建', '更新', '删', '迁移',
             '重构', '优化', '清理', '好了', '✅'],
    '思辨': ['理论', '物理', '量子', '模型', '架构', '设计', '方案',
             '原理', '逻辑', '机制', '分析'],
}


def analyze_hour_slot(slot_dt: datetime) -> dict:
    """
    读取指定小时的 chatlog 消息，返回：
    { new_msgs, highlights, dominant, from_ts, to_ts }
    """
    date_str = slot_dt.strftime("%Y-%m-%d")
    chatlog_file = CHATLOG_DIR / f"{date_str}.jsonl"

    if not chatlog_file.exists():
        return {"new_msgs": 0, "highlights": [], "dominant": "",
                "from_ts": "", "to_ts": ""}

    hour_start = slot_dt
    hour_end = slot_dt + timedelta(hours=1)

    messages = []
    with open(chatlog_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                ts = msg.get('ts', '')
                if ts:
                    msg_dt = datetime.fromisoformat(ts)
                    if hour_start <= msg_dt < hour_end:
                        messages.append(msg)
            except (json.JSONDecodeError, ValueError):
                continue

    new_msgs = len(messages)

    # 情感分类
    category_counts = {k: 0 for k in EMOTIONAL_KEYWORDS}
    for msg in messages:
        content = msg.get('content', '')
        for cat, kws in EMOTIONAL_KEYWORDS.items():
            if any(kw in content for kw in kws):
                category_counts[cat] += 1

    dominant = ""
    if any(category_counts.values()):
        dominant = max(category_counts, key=category_counts.get)

    # 亮点提取（用户消息首行，4-60 字，去重）
    highlights = []
    seen = set()
    for msg in messages:
        if msg.get('role') != 'user':
            continue
        c = msg.get('content', '').strip()
        first_line = c.split('\n')[0].strip()
        if 4 < len(first_line) < 60 and first_line not in seen:
            seen.add(first_line)
            highlights.append(first_line)
            if len(highlights) >= 8:
                break

    # 时间范围
    from_ts = ""
    to_ts = ""
    for msg in messages:
        ts = msg.get('ts', '')
        if ts:
            if not from_ts:
                from_ts = ts
            to_ts = ts

    return {
        "new_msgs": new_msgs,
        "highlights": highlights,
        "dominant": dominant,
        "from_ts": from_ts,
        "to_ts": to_ts,
    }


# ── 条目生成 ──────────────────────────────────────────────

def generate_repair_entry(slot_dt: datetime, data: dict, prev_entry: dict = None) -> dict:
    """
    生成一条修复用 timeline 条目，格式与 time_river.py 完全一致。
    
    slot_dt: 该小时档的起始时间
    data: analyze_hour_slot() 返回的消息数据
    prev_entry: 上一条 timeline 记录（用于计算 river gap）
    """
    month_name = _MONTH_NAMES[slot_dt.month - 1]
    month_vibe = _get_month_vibe(slot_dt.month)
    hour_vibe = _get_hour_vibe(slot_dt)
    time_vibe = f"{month_name}的{month_vibe}，{slot_dt.strftime('%H:%M')}。{hour_vibe}"

    # 计算间隔
    if prev_entry:
        prev_ts = datetime.fromisoformat(prev_entry['ts'])
        gap_h = (slot_dt - prev_ts).total_seconds() / 3600
        gap_text = _get_gap_metaphor(gap_h)
    else:
        gap_text = "河流刚刚开始流淌——这是源头。"

    new_msgs = data['new_msgs']
    river_line = _make_river_line(new_msgs)

    entry = {
        "ts": slot_dt.isoformat(),
        "time_vibe": time_vibe,
        "gap_metaphor": gap_text,
        "weather": f"济南，天气未获取 [修复补回]",
        "session": {
            "new_msgs": new_msgs,
            "token_est": 0,
            "from_ts": data.get('from_ts', ''),
            "to_ts": data.get('to_ts', ''),
            "emotional_dominant": data['dominant'],
            "highlights": data['highlights'][:5],
            "commitments": {},
        },
        "river_line": river_line,
    }
    return entry


# ── 主流程 ────────────────────────────────────────────────

def main():
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv
    quiet = "--quiet" in sys.argv

    # 解析 --since 参数
    since = None
    since_idx = None
    for i, arg in enumerate(sys.argv):
        if arg == "--since" and i + 1 < len(sys.argv):
            since_str = sys.argv[i + 1]
            try:
                since = datetime.fromisoformat(since_str)
                if since.tzinfo is None:
                    since = since.replace(tzinfo=CST)
            except ValueError:
                print(f"❌ 无效的时间格式: {since_str}（需要 ISO 8601，如 2026-06-22T02:00）")
                sys.exit(1)
            since_idx = i
            break

    # 解析 --recent-hours 参数
    recent_hours = None
    for i, arg in enumerate(sys.argv):
        if arg == "--recent-hours" and i + 1 < len(sys.argv):
            recent_hours = int(sys.argv[i + 1])
            since = datetime.now(CST) - timedelta(hours=recent_hours)
            break

    entries = load_timeline()
    if not entries:
        print("⚠️  timeline.jsonl 为空，无法检测缺口。请先运行 chatlog.py extract。")
        sys.exit(1)

    last = entries[-1]
    print(f"📋 最新时间线记录：{last['ts'][:19]}")

    gaps = find_gaps(entries, since=since)
    if not gaps:
        print("✅ 时间线连续，无需修复。")
        # 即使无缺口也刷新一下 time.json
        subprocess.run([sys.executable, str(TIME_RIVER), "refresh"],
                       capture_output=True, timeout=10)
        return

    print(f"🔍 检测到 {len(gaps)} 个缺失时段：")
    for g in gaps:
        print(f"    {g.strftime('%Y-%m-%d %H:00')}")

    if dry_run:
        print("\n[dry-run] 未写入任何数据。")
        return

    # 生成并追加修复条目
    print(f"\n🔧 正在补回 {len(gaps)} 条时间线记录...")
    created = 0

    # 找到缺口前的那条正常记录作为间隔基准
    first_gap = gaps[0]
    current_prev = None
    for e in reversed(entries):
        e_ts = datetime.fromisoformat(e['ts'])
        if e_ts.tzinfo is None:
            e_ts = e_ts.replace(tzinfo=CST)
        if e_ts < first_gap:
            current_prev = e
            break

    for slot_dt in gaps:
        data = analyze_hour_slot(slot_dt)
        entry = generate_repair_entry(slot_dt, data, current_prev)

        if verbose:
            hl_preview = " · ".join(data['highlights'][:2]) if data['highlights'] else "—"
            print(f"  [{slot_dt.strftime('%H:%M')}] {data['new_msgs']}条 | {data['dominant'] or '·'} | {hl_preview}")

        append_timeline(entry)
        current_prev = entry  # 下一条用这条作为间隔基准
        created += 1

    # 刷新 time.json
    subprocess.run([sys.executable, str(TIME_RIVER), "refresh"],
                   capture_output=True, timeout=10)

    # 修复后按时间排序 timeline.jsonl
    _sort_timeline()

    if not quiet:
        print(f"\n✅ 修复完成：补回 {created} 条记录，时间线已连续。")


if __name__ == "__main__":
    main()
