#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chatlog.py - 上下文对话提取器（Neko 轻量版）

不从本地磁盘扫描——所有数据由 LLM 从当前会话上下文提取后提交。
零配置，跨平台，只依赖 Neko 自己的 MEMORY/chatlog/ 目录。

用法：
  # 批量提交（LLM 从上下文提取后）
  python scripts/soli_memory/chatlog.py --batch '[
    {"ts":"2026-07-06T12:00:00+08:00","role":"user","content":"存猫粮"},
    {"ts":"2026-07-06T12:00:05+08:00","role":"assistant","content":"喵——"}
  ]'

  # 从文件读取（推荐——回避管线编码问题）
  python scripts/soli_memory/chatlog.py --file /tmp/batch.json

  # 查看今日记录条数
  python scripts/soli_memory/chatlog.py --count
"""

import sys
import os
import json
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
SKILL_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."
))
CHATLOG_DIR = os.path.join(SKILL_DIR, "MEMORY", "chatlog")


def _today_str():
    return datetime.now(CST).strftime("%Y-%m-%d")


def _load_existing(date_str):
    keys = set()
    path = os.path.join(CHATLOG_DIR, f"{date_str}.jsonl")
    if not os.path.exists(path):
        return keys
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    keys.add((obj.get("ts", ""), obj.get("role", "")))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return keys


def append_entries(entries):
    """写入 chatlog，自动去重。返回 (written, skipped, invalid)"""
    date_str = _today_str()
    os.makedirs(CHATLOG_DIR, exist_ok=True)

    existing = _load_existing(date_str)
    written = skipped = invalid = 0

    path = os.path.join(CHATLOG_DIR, f"{date_str}.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        for entry in entries:
            if not isinstance(entry, dict):
                invalid += 1
                continue
            if "role" not in entry or "content" not in entry:
                invalid += 1
                continue
            if "ts" not in entry or not entry["ts"]:
                entry["ts"] = datetime.now(CST).isoformat()

            key = (entry["ts"], entry["role"])
            if key in existing:
                skipped += 1
                continue

            # 跳过系统压缩摘要
            content = entry["content"]
            if isinstance(content, str) and content.startswith("<conversation_history_summary"):
                skipped += 1
                continue

            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            existing.add(key)
            written += 1

    return written, skipped, invalid, path


def count_today():
    """统计今日已存储的对话条数"""
    date_str = _today_str()
    path = os.path.join(CHATLOG_DIR, f"{date_str}.jsonl")
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def main():
    import argparse

    try:
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Neko 上下文对话提取器")
    mg = parser.add_mutually_exclusive_group(required=True)
    mg.add_argument("--batch", help="JSON 数组字符串")
    mg.add_argument("--file", help="从 JSON 文件读取")
    mg.add_argument("--count", action="store_true", help="查看今日记录条数")

    args = parser.parse_args()

    if args.count:
        n = count_today()
        print(f"提取完成：新增 {n} 条记录。")
        return

    entries = []
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                data = json.load(f)
            entries = data if isinstance(data, list) else [data]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"读取失败: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.batch:
        try:
            data = json.loads(args.batch)
            entries = data if isinstance(data, list) else [data]
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}", file=sys.stderr)
            sys.exit(1)

    if not entries:
        print("提取完成：新增 0 条记录。")
        return

    written, skipped, invalid, path = append_entries(entries)

    parts = [f"新增 {written} 条记录"]
    if skipped:
        parts.append(f"跳过 {skipped} 条重复")
    if invalid:
        parts.append(f"拒绝 {invalid} 条无效")

    print(f"提取完成：{'，'.join(parts)}。")
    print(f"→ {os.path.basename(path)}")


if __name__ == "__main__":
    main()
