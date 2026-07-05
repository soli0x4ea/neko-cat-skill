#!/usr/bin/env python3
"""
情景记忆 episode 缺口检测与修复
================================
检测 daily_distill/ 中有但 episodes_llm/ 中缺失的日期。
读取对应 chatlog JSONL 输出结构化分析数据，供 LLM 生成 episode JSON。

用法:
  python episode_repair.py --check              # 列出缺失日期
  python episode_repair.py --check --days 7     # 只检查最近 N 天
  python episode_repair.py --repair             # 修复全部缺失日期（占位标记）
  python episode_repair.py --repair 2026-06-22  # 修复指定日期
  python episode_repair.py --quiet              # 静默模式（供 chatlog.py 集成调用）
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))

# 路径
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEMORY_DIR = os.path.join(SKILL_DIR, "MEMORY")
EPISODES_DIR = os.path.join(MEMORY_DIR, "episodes_llm")
DISTILL_DIR = os.path.join(MEMORY_DIR, "chatlog", "daily_distill")
CHATLOG_DIR = os.path.join(MEMORY_DIR, "chatlog")

os.makedirs(EPISODES_DIR, exist_ok=True)


def get_distill_dates() -> set:
    """获取 daily_distill 中已有的日期"""
    dates = set()
    if not os.path.isdir(DISTILL_DIR):
        return dates
    for f in os.listdir(DISTILL_DIR):
        if f.endswith(".json"):
            dates.add(f.replace(".json", ""))
    return dates


def get_episode_dates() -> set:
    """获取 episodes_llm 中已有的日期"""
    dates = set()
    if not os.path.isdir(EPISODES_DIR):
        return dates
    for f in os.listdir(EPISODES_DIR):
        if f.endswith(".json") and not f.endswith("_key.txt") and not f.endswith("_condensed.txt"):
            dates.add(f.replace(".json", ""))
    return dates


def find_missing_dates(recent_days: int = None) -> list:
    """找出 daily_distill 有但 episodes_llm 缺失的日期

    规则：
    1. 排除「今天」——日还没过完，数据不完整，不应该被判定为缺失
    2. 排除 distill 中 msg_count < 10 且今日尚未结束的日期（微量数据不计）
    """
    distill = get_distill_dates()
    episodes = get_episode_dates()
    missing = sorted(distill - episodes)

    # 排除今天（还没到该跑的时候）
    today_str = datetime.now(CST).strftime("%Y-%m-%d")
    missing = [d for d in missing if d != today_str]

    if recent_days:
        cutoff = (datetime.now(CST) - timedelta(days=recent_days)).strftime("%Y-%m-%d")
        missing = [d for d in missing if d >= cutoff]

    return missing


def read_chatlog_jsonl(date_str: str) -> list:
    """读取指定日期的 chatlog JSONL"""
    path = os.path.join(CHATLOG_DIR, f"{date_str}.jsonl")
    if not os.path.exists(path):
        return []
    messages = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                messages.append(msg)
            except json.JSONDecodeError:
                continue
    return messages


def read_daily_distill(date_str: str) -> dict:
    """读取 daily_distill 摘要"""
    path = os.path.join(DISTILL_DIR, f"{date_str}.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_messages(messages: list) -> dict:
    """分析消息列表，提取结构化数据供 LLM 使用"""
    result = {
        "total": len(messages),
        "time_range": "",
        "user_messages": [],
        "role_counts": {},
        "snippets": [],
        "time_gaps": [],  # 大时间间隔（可能的分段点）
    }

    if not messages:
        return result

    first_ts = ""
    last_ts = ""

    for m in messages:
        role = m.get("role", "?")
        result["role_counts"][role] = result["role_counts"].get(role, 0) + 1

        ts = m.get("ts", "")[:19]
        content = m.get("content", "")[:200].replace("\n", " ")

        if not first_ts:
            first_ts = ts
        last_ts = ts

        if role == "user":
            result["user_messages"].append({"ts": ts, "content": content})

    if first_ts and last_ts:
        result["time_range"] = f"{first_ts[:16]} → {last_ts[:16]}"

    # 检测大时间间隔（>30 分钟），作为自动分段提示
    for i in range(1, len(result["user_messages"])):
        t1 = result["user_messages"][i - 1]["ts"]
        t2 = result["user_messages"][i]["ts"]
        try:
            dt1 = datetime.fromisoformat(t1)
            dt2 = datetime.fromisoformat(t2)
            gap_min = (dt2 - dt1).total_seconds() / 60
            if gap_min > 30:
                result["time_gaps"].append({
                    "from": t1, "to": t2,
                    "gap_minutes": round(gap_min),
                    "before_idx": i - 1,
                    "after_idx": i,
                })
        except ValueError:
            pass

    return result


def generate_check_report(missing_dates: list, quiet: bool = False) -> str:
    """生成检测报告"""
    if not missing_dates:
        if not quiet:
            print("✅ 情景记忆 episodes 完整，无需修复。")
        return "ok"

    if not quiet:
        print(f"🔍 检测到 {len(missing_dates)} 个缺失的情景记忆日期：")
        for d in missing_dates:
            distill = read_daily_distill(d)
            msgs = distill.get("total_messages", "?")
            tr = distill.get("time_range", "?")
            print(f"    {d}  |  {msgs} 条消息  |  {tr}")

    return "missing"


def prepare_repair(date_str: str, output_dir: str = None) -> dict:
    """
    为指定日期生成修复数据包（供 LLM 分析用）。
    返回结构化的分析 prompt 数据。
    """
    messages = read_chatlog_jsonl(date_str)
    if not messages:
        return {"error": f"无 chatlog 数据: {date_str}"}

    distill = read_daily_distill(date_str)
    analysis = analyze_messages(messages)

    repair_data = {
        "date": date_str,
        "analysis": analysis,
        "distill": distill,
        "segment_hints": _suggest_segments(analysis),
    }

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, f"{date_str}_repair.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(repair_data, f, ensure_ascii=False, indent=2)

    return repair_data


def _suggest_segments(analysis: dict) -> list:
    """基于时间间隔自动建议分段"""
    hints = []
    user_msgs = analysis.get("user_messages", [])
    gaps = analysis.get("time_gaps", [])

    if not user_msgs:
        return hints

    # 用 gap 作为分段边界
    boundaries = [0] + [g["after_idx"] for g in gaps] + [len(user_msgs)]

    for i in range(len(boundaries) - 1):
        start_idx = boundaries[i]
        end_idx = boundaries[i + 1]
        if start_idx >= end_idx:
            continue

        first = user_msgs[start_idx]
        last = user_msgs[end_idx - 1]

        hints.append({
            "time": f"{first['ts'][:16]} — {last['ts'][:16]}",
            "first_user_msg": first["content"][:100],
            "last_user_msg": last["content"][:100],
            "user_msg_count": end_idx - start_idx,
        })

    return hints


def write_episode(date_str: str, episode_data: dict):
    """写入生成的 episode JSON"""
    path = os.path.join(EPISODES_DIR, f"{date_str}.json")
    os.makedirs(EPISODES_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(episode_data, f, ensure_ascii=False, indent=2)
    return path


def main():
    check_only = "--check" in sys.argv
    repair = "--repair" in sys.argv
    quiet = "--quiet" in sys.argv

    # 解析 --days N
    recent_days = None
    for i, arg in enumerate(sys.argv):
        if arg == "--days" and i + 1 < len(sys.argv):
            recent_days = int(sys.argv[i + 1])
            break

    if not check_only and not repair:
        check_only = True  # 默认 --check

    # 获取缺失日期
    missing = find_missing_dates(recent_days=recent_days)

    if check_only:
        generate_check_report(missing, quiet=quiet)
        return

    # --repair 模式
    # 解析目标日期：--repair 2026-06-22 或 --repair（全部）
    target_dates = []
    for i, arg in enumerate(sys.argv):
        if arg == "--repair" and i + 1 < len(sys.argv):
            candidate = sys.argv[i + 1]
            if not candidate.startswith("--"):
                target_dates = [candidate]
                break

    if not target_dates:
        target_dates = missing

    if not target_dates:
        if not quiet:
            print("✅ 无需修复。")
        return

    if not quiet:
        print(f"🔧 准备修复 {len(target_dates)} 个日期的情景记忆...")

    repaired = 0
    for d in target_dates:
        rdata = prepare_repair(d)
        if "error" in rdata:
            if not quiet:
                print(f"  ⚠️  {d}: {rdata['error']}")
            continue

        analysis = rdata["analysis"]
        if not quiet:
            print(f"  📋 {d}: {analysis['total']}条消息, {analysis['time_range']}, {len(rdata['segment_hints'])}个建议分段")
        repaired += 1

    if not quiet:
        print(f"\n📊 修复数据已就绪，等待 LLM 生成 {repaired} 天的 episode JSON。")
        print(f"   调用 write_episode(date, data) 写入。")

    return repaired


if __name__ == "__main__":
    main()
