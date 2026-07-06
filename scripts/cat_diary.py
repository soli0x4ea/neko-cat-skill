#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neko 电子猫 — 猫日记
LLM 在交互结束时调用，以猫的视角记录今天的故事。
用法: python cat_diary.py --mood <心情> --hunger <饱食> "猫的日记内容..."
"""
import json, os, sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 自适应路径：兼容 RedSkill 平铺布局（.py 在根目录）和子目录布局（.py 在 scripts/）
SKILL_DIR = SCRIPT_DIR
if not os.path.exists(os.path.join(SKILL_DIR, "SKILL.md")):
    SKILL_DIR = os.path.dirname(SKILL_DIR)
DIARY_DIR = os.path.join(SKILL_DIR, "MEMORY", "diary")


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def write_entry(text, mood=50, hunger=50, hp=50, intimacy=0.3):
    """追加一条猫日记"""
    os.makedirs(DIARY_DIR, exist_ok=True)
    path = os.path.join(DIARY_DIR, f"{_today()}.md")
    now = datetime.now().strftime("%H:%M")

    # 心情标签
    if mood >= 90:
        mood_tag = "😻 踩奶中"
    elif mood >= 70:
        mood_tag = "😸 开心"
    elif mood >= 40:
        mood_tag = "😺 平静"
    elif mood >= 20:
        mood_tag = "😿 不开心"
    else:
        mood_tag = "😾 炸毛"

    entry = (
        f"\n### {now} {mood_tag}\n"
        f"{text}\n"
    )

    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
        return True
    except Exception as e:
        return False


def read_today():
    """读取今天的猫日记"""
    path = os.path.join(DIARY_DIR, f"{_today()}.md")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "（今天还没有日记）"


def read_recent(n=3):
    """读取最近 N 天的日记摘要"""
    try:
        files = sorted(
            [f for f in os.listdir(DIARY_DIR) if f.endswith(".md")],
            reverse=True
        )
        entries = []
        for f in files[:n]:
            path = os.path.join(DIARY_DIR, f)
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
            first_line = content.strip().split("\n")[0] if content.strip() else "(空)"
            entries.append(f"**{f.replace('.md','')}**: {first_line}")
        return "\n".join(entries) if entries else "（没有日记）"
    except:
        return "（无法读取日记）"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Neko 猫日记")
    parser.add_argument("--mood", type=int, default=50, help="心情值")
    parser.add_argument("--hunger", type=int, default=50, help="饱食度")
    parser.add_argument("--hp", type=int, default=50, help="健康值")
    parser.add_argument("--intimacy", type=float, default=0.3, help="亲密度")
    parser.add_argument("--read", action="store_true", help="读取今天的日记")
    parser.add_argument("text", nargs="*", help="日记内容")

    args = parser.parse_args()

    if args.read:
        print(read_today())
    elif args.text:
        text = " ".join(args.text)
        ok = write_entry(text, args.mood, args.hunger, args.hp, args.intimacy)
        print("🐱 记下了。" if ok else "写日记失败了喵。")
    else:
        print("喵？写日记需要内容。用法: cat_diary.py '今天主人...'")
