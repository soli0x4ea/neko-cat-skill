#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
save_chatlog.py — Neko 聊天记录存储脚本

LLM 从当前会话上下文 dump 完整对话 → 此脚本过滤系统噪音 → 存入 chatlog。

用法：
  # 全量提取并存储（LLM dump 全部上下文）
  python scripts/save_chatlog.py --dump /tmp/context_dump.json

  # 增量提取（只存书签之后的新消息，推荐日常使用）
  python scripts/save_chatlog.py --incremental /tmp/context_dump.json

  # 查看今日记录条数
  python scripts/save_chatlog.py --count

  # 查看增量书签状态
  python scripts/save_chatlog.py --bookmark
"""

import sys
import os
import json
import hashlib
from datetime import datetime, timezone, timedelta

# 确保能 import dlc 包
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)

from dlc.memory.chatlog import ChatlogStore

CST = timezone(timedelta(hours=8))
CHATLOG_DIR = os.path.join(SKILL_DIR, "MEMORY", "chatlog")
BOOKMARK_PATH = os.path.join(SKILL_DIR, "data", "extract_bookmark.json")

# ── 系统噪音过滤 ────────────────────────────────────────────

_SYSTEM_PREFIXES = (
    "<cb_summary",
    "<conversation_history_summary",
    "<system-reminder",
    "<memory",
    "<additional_data",
    "<user_info",
    "<rules",
    "<identity_context",
    "<project_context",
    "<product_identity",
    "<working_memory_content",
    "<memory_and_skills_reminder",
    "Here is the summary",
    "Summary of the conversation",
)


def _should_keep(entry: dict) -> bool:
    """全量保存：只过滤系统注入块，user/assistant 全部保留。"""
    role = entry.get("role", "")
    content = entry.get("content", "")
    if not role or not content:
        return False
    if not isinstance(content, str):
        return False
    if role not in ("user", "assistant"):
        return False
    for prefix in _SYSTEM_PREFIXES:
        if content.strip().startswith(prefix):
            return False
    return True


# ── 书签管理 ────────────────────────────────────────────────

def _load_bookmark() -> dict:
    if not os.path.exists(BOOKMARK_PATH):
        return {}
    try:
        with open(BOOKMARK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_bookmark(bm: dict):
    os.makedirs(os.path.dirname(BOOKMARK_PATH), exist_ok=True)
    tmp = BOOKMARK_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(bm, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, BOOKMARK_PATH)


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


# ── 核心：过滤 + 存储 ───────────────────────────────────────

def filter_and_save(json_path: str, incremental: bool = False) -> dict:
    """读取 LLM dump 的原始对话 → 过滤噪音 → 存入 ChatlogStore。

    Args:
        json_path: LLM dump 的 JSON 文件路径
        incremental: True = 只存书签之后的新消息

    Returns:
        {total, kept, filtered_out, written, skipped, note}
    """
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Dump 文件不存在: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raise ValueError("dump 文件必须是 JSON 数组")

    total = len(raw)
    bookmark = _load_bookmark()

    # 过滤系统噪音
    clean = []
    for entry in raw:
        if _should_keep(entry):
            if "ts" not in entry or not entry["ts"]:
                entry["ts"] = time.time() if incremental else datetime.now(CST).isoformat()
            clean.append(entry)

    filtered_out = total - len(clean)

    # 增量模式：定位书签
    note = ""
    if incremental:
        last_hash = bookmark.get("last_content_hash")
        last_role = bookmark.get("last_role")
        bookmark_idx = -1
        if last_hash and last_role:
            for i, entry in enumerate(clean):
                if entry["role"] == last_role and _hash_content(entry["content"]) == last_hash:
                    bookmark_idx = i
                    break

        if bookmark_idx >= 0:
            new_entries = clean[bookmark_idx + 1:]
            skipped_inc = bookmark_idx + 1
            if new_entries:
                note = f"📌 增量提取：跳过 {skipped_inc} 条已存，新增 {len(new_entries)} 条"
            else:
                note = "📌 没有新消息（书签已是最新）"
        else:
            new_entries = clean
            note = "📌 新会话或书签丢失，全量提取" if not last_hash else "⚠️ 书签消息不在上下文中，全量重建"
    else:
        new_entries = clean
        note = "📦 全量提取"

    if not new_entries:
        return {"total": total, "kept": 0, "filtered_out": filtered_out,
                "written": 0, "skipped": 0, "note": note}

    # 通过 ChatlogStore 写入
    today_str = datetime.now(CST).strftime("%Y-%m-%d")
    store = ChatlogStore(CHATLOG_DIR)

    # 转成 batch_append 格式
    batch = []
    for entry in new_entries:
        batch.append({
            "role": entry["role"],
            "content": entry["content"],
            "ts": entry.get("ts", datetime.now(CST).isoformat()),
        })

    result = store.batch_append(today_str, batch)
    written = result.get("added", 0)
    skipped = result.get("skipped", 0)

    # 更新书签（增量模式）
    if incremental and written > 0:
        last_entry = new_entries[-1]
        new_bm = {
            "last_content_hash": _hash_content(last_entry["content"]),
            "last_role": last_entry["role"],
            "last_ts": last_entry.get("ts", ""),
            "total_extracted": bookmark.get("total_extracted", 0) + written,
            "session_count": bookmark.get("session_count", 1),
        }
        _save_bookmark(new_bm)

    return {"total": total, "kept": len(new_entries), "filtered_out": filtered_out,
            "written": written, "skipped": skipped, "note": note}


# ── CLI ─────────────────────────────────────────────────────

def main():
    import argparse

    try:
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Neko 聊天记录存储")
    mg = parser.add_mutually_exclusive_group(required=True)
    mg.add_argument("--dump", help="LLM dump 原始对话 JSON → 过滤 → 全量存入")
    mg.add_argument("--incremental", help="增量模式：LLM dump → 只存书签后的新消息")
    mg.add_argument("--count", action="store_true", help="查看今日记录条数")
    mg.add_argument("--bookmark", action="store_true", help="查看增量书签状态")

    args = parser.parse_args()

    if args.count:
        from dlc.memory.chatlog import ChatlogStore
        store = ChatlogStore(CHATLOG_DIR)
        today = datetime.now(CST).strftime("%Y-%m-%d")
        n = store.count_day(today)
        total = store.stats().get("total", 0)
        print(f"今日对话记录：{n} 条（累计 {total} 条）。")
        return

    if args.bookmark:
        bm = _load_bookmark()
        if bm.get("last_content_hash"):
            print(f"书签状态：已累计 {bm.get('total_extracted', 0)} 条消息。")
            print(f"最后提取：{bm.get('last_ts', '未知')} ({bm.get('last_role', '?')})")
        else:
            print("书签状态：空（尚未进行过增量提取）")
        return

    json_path = args.dump or args.incremental
    is_incremental = bool(args.incremental)

    try:
        r = filter_and_save(json_path, incremental=is_incremental)
        print(r["note"])
        if r["written"] > 0:
            print(f"过滤完成：{r['total']} 条原始 → {r['kept']} 条有效 "
                  f"→ 存入 {r['written']} 条（过滤 {r['filtered_out']} 条，去重跳过 {r['skipped']} 条）")
        else:
            print(f"跳过写入：{r['total']} 条中无新消息。")
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        print(f"提取失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
