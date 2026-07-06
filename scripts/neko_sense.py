#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neko 电子猫 — CLI 路由 + stdout 记录
命令: feed / pet / play / treat / vet / check / status
"""
import sys, os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from neko_core import (
    feed, pet, play, treat, vet, check, status,
    log_stdout, load_today_stdout, load_recent_changes,
    feed_cat_food, eat_and_digest, save_diary_md, list_diaries,
    trigger_event
)
from narratives import (
    _build_feed_narrative, _build_pet_narrative, _build_play_narrative,
    _build_treat_narrative, _build_vet_narrative, _build_status_panel,
    _build_boundary_narrative, _build_random_event_narrative,
)


def main():
    if len(sys.argv) < 2:
        print("🐱 Neko 电子猫")
        print("用法: neko.py <命令>")
        print("命令: feed | pet | play | treat | vet | check | status")
        return

    cmd = sys.argv[1].lower()
    output = ""

    if cmd == "feed":
        result = feed()
        output = _build_feed_narrative(
            result["hunger_before"], result["hunger_after"],
            intimacy=0.3
        )

    elif cmd == "pet":
        result = pet()
        output = _build_pet_narrative(
            result["mood_before"], result["mood_after"],
            intimacy=result.get("intimacy", 0.3)
        )

    elif cmd == "play":
        result = play()
        output = _build_play_narrative(
            result["mood_before"], result["mood_after"],
            result["hunger_after"],
            intimacy=0.3
        )

    elif cmd == "treat":
        result = treat()
        if "error" in result:
            print(result["error"])
            return
        output = _build_treat_narrative(
            result["mood_before"], result["mood_after"],
            result["hunger_before"],
            intimacy=0.3
        )

    elif cmd == "vet":
        result = vet()
        output = _build_vet_narrative(
            result["hp_before"], result["hp_after"],
            result["mood_after"],
            intimacy=result.get("intimacy", 0.3)
        )
        if result.get("action") == "revive":
            output = "💫 猫从喵星回来了。\n\n" + output

    elif cmd == "check":
        result = check()
        parts = []

        # 状态面板
        parts.append(_build_status_panel(
            result["hp"], result["hunger"], result["mood"],
            result.get("intimacy", 0.3), result.get("candy", 0)
        ))

        # 边界事件
        boundaries = result.get("boundaries", [])
        if boundaries:
            parts.append("")
            parts.append("⚠️ **重要事件**")
            parts.append(_build_boundary_narrative(
                boundaries, result["hp"], result["hunger"], result["mood"],
                result.get("intimacy", 0.3)
            ))

        # 随机事件
        event = result.get("random_event")
        if event:
            parts.append("")
            parts.append("🎲 **随机事件**")
            parts.append(_build_random_event_narrative(event, result.get("intimacy", 0.3)))

        # 最近 soulchanges
        changes = load_recent_changes(5)
        if changes:
            parts.append("")
            parts.append("📊 **最近变化**")
            for c in changes[-5:]:
                t = c["time"][11:19] if "T" in c["time"] else c["time"][:8]
                cmd_name = c["cmd"]
                delta_str = " | ".join(f"{k}:{v}" for k, v in c.get("delta", {}).items())
                parts.append(f"  `{t}` {cmd_name} → {delta_str}")

        output = "\n".join(parts)

        # 自动刷新时间河流
        try:
            from time_river import refresh_soul
            refresh_soul(write=True)
        except:
            pass

    elif cmd == "status":
        result = status()
        output = _build_status_panel(
            result["hp"], result["hunger"], result["mood"],
            result.get("intimacy", 0.3), result.get("candy", 0)
        )

    # ── 记忆管道命令 ──────────────────────────────────

    elif cmd == "cat-food":
        # 放猫粮：LLM 统计对话条数 → 存猫粮
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        n_treats, total, output = feed_cat_food(n)

    elif cmd == "digest":
        # 消化：LLM 生成情景记忆后调用
        mood = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        ok, output = eat_and_digest(mood)
        if not ok:
            print(output)
            return
        # 提示 LLM 写日记
        output += "\n\n📝 **记得写猫日记**：`python scripts/cat_diary.py --mood <值> '日记内容'`"

    elif cmd == "episodes":
        # 列出情景记忆
        eps = list_diaries()
        if eps:
            output = "📖 **情景记忆**\n" + "\n".join(f"- {e}" for e in eps)
        else:
            output = "📖 还没有情景记忆。"

    # ── 事件命令 ──────────────────────────────────────

    elif cmd == "event":
        event_id = sys.argv[2] if len(sys.argv) > 2 else "1"
        output, effects = trigger_event(event_id)

    else:
        print(f"🐱 喵？不知道 '{cmd}' 是什么。试试 feed, pet, play, treat, vet, check。")
        return

    # 输出到终端
    print(output)

    # 记录到 stdout 文件
    log_stdout(cmd, output)


if __name__ == "__main__":
    main()
