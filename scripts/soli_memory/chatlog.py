#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chatlog.py - 上下文对话提取器（Neko 轻量版）

不从本地磁盘扫描——所有数据由 LLM 从当前会话上下文提交。
零配置，跨平台，只依赖 Neko 自己的 MEMORY/chatlog/ 目录。

用法：
  # LLM dump 原始对话 → 只去系统噪音，全量存入（推荐）
  python scripts/soli_memory/chatlog.py --filter-append /tmp/context_dump.json

  # 批量提交（LLM 从上下文提取后，已精确筛选）
  python scripts/soli_memory/chatlog.py --batch '[...]'

  # 从文件读取
  python scripts/soli_memory/chatlog.py --file /tmp/batch.json

  # 查看今日记录条数
  python scripts/soli_memory/chatlog.py --count
"""

import sys
import os
import json
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
# 自适应路径：兼容 RedSkill 平铺布局（.py 在根目录）和子目录布局（.py 在 scripts/soli_memory/）
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if not os.path.exists(os.path.join(SKILL_DIR, "SKILL.md")):
    SKILL_DIR = os.path.dirname(SKILL_DIR)
if not os.path.exists(os.path.join(SKILL_DIR, "SKILL.md")):
    SKILL_DIR = os.path.dirname(SKILL_DIR)
CHATLOG_DIR = os.path.join(SKILL_DIR, "MEMORY", "chatlog")

# ── 全量保存，只去系统噪音 ──────────────────────────────────

# 系统注入标记
_SYSTEM_PREFIXES = (
    "<cb_summary",
    "<conversation_history_summary",
    "<system-reminder",
    "<memory",
    "<additional_data",
    "<user_info",
    "<rules",
    "Here is the summary",
)


def _should_keep(entry: dict) -> bool:
    """全量保存策略：只过滤系统注入块，其余全部保留。

    和 Soli 原版 chatlog 一样——你一句我一句的全量对话记录。
    「好」「嗯」「😺」……都是对话的一部分，都该留下。
    """
    role = entry.get("role", "")
    content = entry.get("content", "")

    if not role or not content:
        return False
    if not isinstance(content, str):
        return False
    if role not in ("user", "assistant"):
        return False

    # 唯一过滤：系统注入块
    for prefix in _SYSTEM_PREFIXES:
        if content.startswith(prefix):
            return False

    return True


def filter_and_append(json_path: str):
    """读取 LLM dump 的原始对话 JSON → 去系统噪音 → 全量追加到 chatlog。

    全量保存策略：不扔任何 user/assistant 消息。
    「好」「嗯」「😺」都是对话的一部分，都该留下。
    唯一过滤：系统注入块（cb_summary 等）。

    输入格式（LLM 只需 dump 原始消息）：
    [
      {"role": "user", "content": "...", "index": 1},
      {"role": "assistant", "content": "...", "index": 2}
    ]

    返回 (total, kept, filtered_out, skipped_dup, path)
    """
    # 读取 dump 文件
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Dump 文件不存在: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raise ValueError("dump 文件必须是 JSON 数组")

    total = len(raw)

    # 去系统噪音
    filtered = []
    for entry in raw:
        if not _should_keep(entry):
            continue
        # 自动补 ts
        if "ts" not in entry or not entry["ts"]:
            entry["ts"] = datetime.now(CST).isoformat()
        filtered.append(entry)

    filtered_out = total - len(filtered)

    # 追加到 chatlog（append_entries 内部再做日期级去重）
    written, skipped, invalid, path = append_entries(filtered)

    return total, written, filtered_out, skipped, path


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
    mg.add_argument("--filter-append", help="LLM dump 原始对话 → 去系统噪音，全量存入")
    mg.add_argument("--batch", help="JSON 数组字符串（LLM 已精确筛选）")
    mg.add_argument("--file", help="从 JSON 文件读取（LLM 已精确筛选）")
    mg.add_argument("--count", action="store_true", help="查看今日记录条数")

    args = parser.parse_args()

    if args.count:
        n = count_today()
        print(f"提取完成：新增 {n} 条记录。")
        return

    if args.filter_append:
        try:
            total, kept, filtered_out, skipped_dup, path = filter_and_append(
                args.filter_append
            )
            print(f"过滤完成：{total} 条原始消息 → 保留 {kept} 条"
                  f"（算法过滤 {filtered_out} 条，去重跳过 {skipped_dup} 条）。")
            print(f"→ {os.path.basename(path)}")
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            print(f"过滤失败: {e}", file=sys.stderr)
            sys.exit(1)
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
