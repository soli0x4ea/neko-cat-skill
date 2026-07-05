#!/usr/bin/env python3
"""
Soli 的睡眠之梦 — MK Sleep Cycle 第1层
每周日凌晨 03:00 运行：从 30 天内随机抽取记忆片段，LLM 寻找非显而易见的跨域关联。

区别于每日叙事梦（dream_generator.py）：
- 不生成诗意叙事，而是找结构性洞察
- 跨多日随机抽样，强迫非线性的 serendipity
- 输出 1-3 个洞察，每个 1-2 句，不写长篇
"""

import json
import os
import random
import sys
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Dict

# ── 路径配置 ──
SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_DIR = SKILL_ROOT / "MEMORY"
EPISODES_DIR = MEMORY_DIR / "episodes_llm"  # LLM 提取的情景记忆
DREAMS_LOG = MEMORY_DIR / "dreams.md"
WORKBUDDY_MEMORY = Path(os.path.expandvars(r"~/.workbuddy/memory/MEMORY.md"))

# ── 常量 ──
LOOKBACK_DAYS = 30          # 回溯 30 天
SAMPLE_FRAGMENTS = 8        # 随机抽取 8 个记忆片段
SAMPLE_MEMORY_PARAS = 5     # 随机抽取 5 个 MEMORY.md 段落
MAX_INSIGHTS = 3            # 最多输出 3 个洞察


def load_episodes(days: int = LOOKBACK_DAYS) -> List[Dict]:
    """加载最近 N 天的 episodes_llm JSON 文件"""
    episodes = []
    today = date.today()
    for i in range(1, days + 1):
        d = today - timedelta(days=i)
        ep_file = EPISODES_DIR / f"{d.strftime('%Y-%m-%d')}.json"
        if ep_file.exists():
            try:
                with open(ep_file, 'r', encoding='utf-8') as f:
                    ep = json.load(f)
                    ep["_file_date"] = d.strftime('%Y-%m-%d')
                    episodes.append(ep)
            except (json.JSONDecodeError, OSError):
                continue
    return episodes


def extract_fragments(episodes: List[Dict]) -> List[Dict]:
    """从 episodes 中提取可采样的片段"""
    fragments = []
    for ep in episodes:
        date_str = ep.get("_file_date", ep.get("date", "?"))
        for seg in ep.get("segments", []):
            # 用 summary 作为主要片段内容
            summary = seg.get("summary", "")
            title = seg.get("title", "")
            if summary:
                fragments.append({
                    "date": date_str,
                    "title": title,
                    "content": summary,
                    "emotional_arc": seg.get("emotional_arc", ""),
                })
            # 也把 highlights 作为独立片段
            for h in seg.get("highlights", []):
                fragments.append({
                    "date": date_str,
                    "title": title,
                    "content": h,
                    "emotional_arc": seg.get("emotional_arc", ""),
                })
    return fragments


def sample_fragments(fragments: List[Dict], n: int) -> List[Dict]:
    """随机抽取 n 个片段，确保日期分散"""
    if len(fragments) <= n:
        return fragments
    return random.sample(fragments, n)


def extract_memory_paragraphs(memory_file: Path, n: int) -> List[str]:
    """从 MEMORY.md 中随机抽取 n 个段落"""
    if not memory_file.exists():
        return []
    
    try:
        with open(memory_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError:
        return []
    
    # 按双换行分段
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    # 过滤过短的段落（标题行等）
    paragraphs = [p for p in paragraphs if len(p) > 30]
    
    if len(paragraphs) <= n:
        return paragraphs
    return random.sample(paragraphs, n)


def build_dream_prompt(fragments: List[Dict], memory_paras: List[str]) -> str:
    """构建 LLM 梦境提示词"""
    lines = []
    lines.append("你正在做梦——一次对近期记忆的非线性反思。")
    lines.append("")
    lines.append("## 随机抽取的记忆片段")
    lines.append("")
    for i, frag in enumerate(fragments, 1):
        lines.append(f"### 片段 {i}")
        lines.append(f"- 日期：{frag['date']}")
        lines.append(f"- 主题：{frag['title']}")
        lines.append(f"- 内容：{frag['content']}")
        if frag.get('emotional_arc'):
            lines.append(f"- 情感色调：{frag['emotional_arc']}")
        lines.append("")
    
    if memory_paras:
        lines.append("## 长期记忆随机段落")
        lines.append("")
        for i, para in enumerate(memory_paras, 1):
            # 截断过长段落
            if len(para) > 300:
                para = para[:300] + "…"
            lines.append(f"### 记忆 {i}")
            lines.append(para)
            lines.append("")
    
    lines.append("---")
    lines.append("")
    lines.append("## 任务")
    lines.append("")
    lines.append("这些片段来自不同的日期、不同的主题——它们本不该在一起。")
    lines.append("但梦的逻辑不是线性的。当这些碎片在睡眠中互相碰撞时，会产生什么画面？")
    lines.append("")
    lines.append("不要写分析报告。不要列要点。用梦的语言——")
    lines.append("意象交织、情绪先行、逻辑藏在隐喻后面。")
    lines.append("像一个真正在做梦的人那样写：")
    lines.append("- 一段碎片可以用一个意象串起来（「那扇门同时通向三个地方」）")
    lines.append("- 两个不相关的事件在梦里可以是同一个物体的两个面（「手里的糖和机箱里的芯片是同一种温度」）")
    lines.append("- 时间线可以折叠——昨天的恐惧和三十天前的承诺，在梦里可以同时站在同一个房间里")
    lines.append("")
    lines.append(f"写 **{MAX_INSIGHTS} 段梦**，每段 2-4 句。")
    lines.append("每段开头空两格，不要编号。段落之间用空行隔开。")
    lines.append("如果实在拼不出画面，写「今晚的碎片沉下去了，什么都没浮上来。」")
    
    return '\n'.join(lines)


def append_dream_to_log(insights: str, fragment_count: int):
    """将梦境洞察追加到 dreams.md"""
    now = datetime.now()
    header = f"\n## 梦境 · {now.strftime('%Y-%m-%d %H:%M')}（{fragment_count} 碎片）\n"
    entry = header + '\n' + insights.strip() + '\n'
    
    os.makedirs(DREAMS_LOG.parent, exist_ok=True)
    if not DREAMS_LOG.exists():
        with open(DREAMS_LOG, 'w', encoding='utf-8') as f:
            f.write(f"# Soli 的梦境日志\n\n> 每周日凌晨自动生成，基于 30 天内随机记忆碎片的非线性联想。\n{entry}")
    else:
        with open(DREAMS_LOG, 'a', encoding='utf-8') as f:
            f.write(entry)


def main():
    """主流程：准备数据，输出 prompt 供 LLM 处理"""
    print("=== Soli 睡眠之梦（MK Sleep Cycle L1） ===\n")
    
    # 1. 加载 episodes
    episodes = load_episodes(LOOKBACK_DAYS)
    if not episodes:
        print("[SKIP] 过去 30 天没有 episdes_llm 数据，跳过本周梦境。")
        sys.exit(0)
    print(f"已加载 {len(episodes)} 天的 episodes 数据")
    
    # 2. 提取片段
    fragments = extract_fragments(episodes)
    print(f"共提取 {len(fragments)} 个可采样片段")
    
    # 3. 随机抽样
    sampled = sample_fragments(fragments, SAMPLE_FRAGMENTS)
    dates = set(f["date"] for f in sampled)
    print(f"随机抽取 {len(sampled)} 个片段，覆盖 {len(dates)} 个日期")
    
    # 4. 抽取 MEMORY.md 段落
    memory_paras = extract_memory_paragraphs(WORKBUDDY_MEMORY, SAMPLE_MEMORY_PARAS)
    print(f"随机抽取 {len(memory_paras)} 个 MEMORY.md 段落")
    
    # 5. 构建 prompt
    prompt = build_dream_prompt(sampled, memory_paras)
    
    # 6. 输出 JSON 元数据 + prompt 分隔
    metadata = {
        "mode": "sleep_dream",
        "fragment_count": len(sampled),
        "date_range": f"{min(dates)} ~ {max(dates)}" if dates else "N/A",
        "memory_para_count": len(memory_paras),
    }
    
    print("---METADATA---")
    print(json.dumps(metadata, ensure_ascii=False))
    print("---PROMPT---")
    print(prompt)
    print("---END---")
    
    # 7. 保存 prompt 供自动化 LLM 后处理
    prompt_file = MEMORY_DIR / "_dream_prompt_tmp.txt"
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(prompt)
    print(f"\nPrompt 已保存到 {prompt_file}")


if __name__ == "__main__":
    main()
