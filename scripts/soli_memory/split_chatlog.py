#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chatlog 拆分工具 — 当 chatlog 过大时按时间段拆分，分片交给 LLM 处理后合并。
"""

import json
import os
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

# 拆分阈值
MAX_BYTES = 300 * 1024       # 300KB：超过就拆分
MAX_MSGS_PER_CHUNK = 200     # 每片最多 200 条消息
MIN_CHUNKS = 1               # 最少拆分片数


def get_chatlog_date(filepath: str) -> str:
    """从文件路径提取日期"""
    basename = os.path.basename(filepath)
    return basename.replace(".jsonl", "")


def split_by_message_count(messages: list, max_per_chunk: int = MAX_MSGS_PER_CHUNK) -> list:
    """按消息数拆分"""
    chunks = []
    for i in range(0, len(messages), max_per_chunk):
        chunks.append(messages[i:i + max_per_chunk])
    return chunks


def split_by_time_gap(messages: list, gap_minutes: int = 120) -> list:
    """按时段间隔拆分（在超过 gap_minutes 的间隙处断点）"""
    if not messages:
        return []

    chunks = []
    current_chunk = [messages[0]]
    prev_ts = _parse_ts(messages[0])

    for msg in messages[1:]:
        curr_ts = _parse_ts(msg)
        if curr_ts and prev_ts:
            diff = (curr_ts - prev_ts).total_seconds()
            if diff > gap_minutes * 60 and len(current_chunk) >= 10:
                chunks.append(current_chunk)
                current_chunk = []
        current_chunk.append(msg)
        prev_ts = curr_ts

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _parse_ts(msg: dict):
    """解析消息时间戳"""
    ts_str = msg.get("ts", "")
    try:
        if "T" in ts_str:
            return datetime.fromisoformat(ts_str)
        return None
    except (ValueError, TypeError):
        return None


def split_chatlog(filepath: str, strategy: str = "auto") -> list[list[dict]]:
    """拆分 chatlog 文件，返回消息块列表。
    
    strategy:
      - "auto": 按文件大小自动选择（默认）
      - "time": 按时间间隙强制拆分
      - "count": 按消息数强制拆分
    """
    # 读取所有消息
    messages = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not messages:
        return []

    file_size = os.path.getsize(filepath)

    # 判断是否需要拆分
    if strategy == "count":
        return split_by_message_count(messages)
    elif strategy == "time":
        return split_by_time_gap(messages)
    else:  # auto
        if file_size <= MAX_BYTES and len(messages) <= MAX_MSGS_PER_CHUNK:
            return [messages]  # 不需要拆分
        elif len(messages) > MAX_MSGS_PER_CHUNK * 2:
            return split_by_message_count(messages)
        else:
            return split_by_time_gap(messages)


def chunk_to_jsonl(chunk: list[dict], outpath: str):
    """将消息块写入临时 JSONL 文件"""
    with open(outpath, "w", encoding="utf-8") as f:
        for msg in chunk:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")


def get_chunk_info(chunks: list[list[dict]]) -> list[dict]:
    """返回每个 chunk 的摘要信息"""
    info = []
    for i, chunk in enumerate(chunks):
        first_ts = _parse_ts(chunk[0]) if chunk else None
        last_ts = _parse_ts(chunk[-1]) if chunk else None
        info.append({
            "chunk_id": i + 1,
            "total_chunks": len(chunks),
            "message_count": len(chunk),
            "time_range": f"{first_ts.strftime('%H:%M') if first_ts else '?'} → {last_ts.strftime('%H:%M') if last_ts else '?'}",
            "user_msgs": sum(1 for m in chunk if m.get("role") == "user"),
            "asst_msgs": sum(1 for m in chunk if m.get("role") == "assistant"),
        })
    return info


def merge_episodes(chunks_data: list[dict], date: str) -> dict:
    """合并多个 chunk 的 LLM 提取结果为完整 episode"""
    all_segments = []
    for chunk_data in chunks_data:
        segs = chunk_data.get("segments", [])
        for s in segs:
            # 标注来源 chunk
            s["_chunk"] = chunk_data.get("_chunk_id", "?")
        all_segments.extend(segs)

    # 合并 day_summary
    summaries = [c.get("day_summary", "") for c in chunks_data if c.get("day_summary")]
    merged_summary = " | ".join(summaries) if summaries else ""

    return {
        "date": date,
        "source": f"chatlog → LLM 提取（{len(chunks_data)} 片合并）",
        "segments": all_segments,
        "day_summary": merged_summary,
        "_chunk_count": len(chunks_data)
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python split_chatlog.py <chatlog.jsonl> [auto|count|time]")
        sys.exit(1)

    filepath = sys.argv[1]
    strategy = sys.argv[2] if len(sys.argv) > 2 else "auto"

    chunks = split_chatlog(filepath, strategy)

    info = get_chunk_info(chunks)
    print(json.dumps({
        "file": filepath,
        "strategy": strategy,
        "total_chunks": len(chunks),
        "chunks": info
    }, ensure_ascii=False, indent=2))
