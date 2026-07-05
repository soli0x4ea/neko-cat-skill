#!/usr/bin/env python3
"""
Soli 的睡眠反思 — MK Sleep Cycle 第2层
每日 21:00 运行：交叉比对近期记忆与长期记忆，检测矛盾、建议整合、标记衰减。

设计原则（来自 MK）：
- 只建议，不自动修改 — 分析/决策分离
- 矛盾检测 + 整合建议 + 衰减标记 三项任务
- 输出写入 reflections.md，由 main session 决定是否采纳
"""

import json
import os
import sys
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Dict, Optional

# ── 路径配置 ──
SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_DIR = SKILL_ROOT / "MEMORY"
EPISODES_DIR = MEMORY_DIR / "episodes_llm"
REFLECTIONS_LOG = MEMORY_DIR / "reflections.md"
WORKBUDDY_MEMORY = Path(os.path.expandvars(r"~/.workbuddy/memory/MEMORY.md"))

LOOKBACK_EPISODES = 3         # 对比最近 3 天 episode
LOOKBACK_DAILY = 7            # 回溯 7 天 daily memory


def load_recent_episodes(days: int = LOOKBACK_EPISODES) -> List[Dict]:
    """加载最近 N 天的 episodes_llm"""
    episodes = []
    today = date.today()
    for i in range(days):
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


def load_longterm_memory() -> str:
    """加载 MEMORY.md 全文"""
    if not WORKBUDDY_MEMORY.exists():
        return ""
    try:
        with open(WORKBUDDY_MEMORY, 'r', encoding='utf-8') as f:
            return f.read()
    except OSError:
        return ""


def extract_claims(episodes: List[Dict]) -> List[Dict]:
    """从 episodes 中提取可验证的声明（事实性信息，非情感表达）"""
    claims = []
    # 关键词指示可能存在事实声明
    fact_indicators = [
        "路径", "配置", "文件", "目录", "命令", "参数", "版本",
        "使用", "改为", "修改", "删除", "创建", "设置", "默认",
        "不再", "已", "修复", "bug", "Bug", "方案", "架构",
        "决定", "选择", "采用", "迁移", "统一", "规范",
    ]
    
    for ep in episodes:
        date_str = ep.get("_file_date", ep.get("date", "?"))
        for seg in ep.get("segments", []):
            for h in seg.get("highlights", []):
                # 只取决策/约束/证据类 highlight
                if h.startswith("⚖️") or h.startswith("🔒") or h.startswith("📋"):
                    claims.append({
                        "date": date_str,
                        "claim": h[2:].strip() if h[2:3] else h.strip(),
                        "context": seg.get("summary", ""),
                    })
    
    return claims


def build_reflect_prompt(episodes: List[Dict], claims: List[Dict], longterm: str) -> str:
    """构建反思提示词"""
    # 汇总近期摘要
    recent_summaries = []
    for ep in episodes:
        ds = ep.get("day_summary", "")
        if ds:
            recent_summaries.append(f"- {ep.get('_file_date', '?')}：{ds}")
    
    lines = []
    lines.append("你是 soli 的睡眠反思机制——每日一次的记忆交叉比对。")
    lines.append("")
    
    lines.append("## 近期记忆摘要")
    lines.append("")
    for s in recent_summaries[:LOOKBACK_EPISODES]:
        lines.append(s)
    lines.append("")
    
    if claims:
        lines.append("## 近期事实声明（决策/约束/证据类）")
        lines.append("")
        for c in claims:
            lines.append(f"- [{c['date']}] {c['claim']}")
        lines.append("")
    
    if longterm:
        # 只取前 4000 字符的长期记忆
        lt_preview = longterm[:4000] if len(longterm) > 4000 else longterm
        if len(longterm) > 4000:
            lt_preview += "\n\n…（截断，完整 MEMORY.md 约 " + str(len(longterm)) + " 字符）"
        lines.append("## 长期记忆（MEMORY.md 前 4000 字符）")
        lines.append("")
        lines.append("```")
        lines.append(lt_preview)
        lines.append("```")
        lines.append("")
    
    lines.append("---")
    lines.append("")
    lines.append("## 任务")
    lines.append("")
    lines.append("请执行以下三项检查：")
    lines.append("")
    lines.append("### 1. 矛盾检测")
    lines.append("- 近期声明是否与长期记忆中的记录冲突？")
    lines.append("- 不同日期的声明之间是否有矛盾？（如：今天说用方案A，昨天说用方案B）")
    lines.append("- 每条矛盾标注：[矛盾] 旧记录 vs 新声明 → 建议")
    lines.append("")
    lines.append("### 2. 整合建议")
    lines.append("- 哪些近期信息反复出现但尚未写入长期记忆？")
    lines.append("- 哪些模式值得升级为 MEMORY.md 条目？")
    lines.append("- 每条建议标注：[整合] 信息 → 建议放入哪个 MEMORY.md 章节")
    lines.append("")
    lines.append("### 3. 衰减标记")
    lines.append("- 长期记忆中哪些条目已超过 30 天未被引用？")
    lines.append("- 建议降级还是清除？标记为 [衰减] 条目 → 建议")
    lines.append("")
    lines.append("**重要**：你只做建议，不执行任何文件修改。输出写入 reflections.md 供你审阅。")
    lines.append("如果没有发现问题，诚实地说「今日无矛盾/无整合建议」，不要硬编。")
    
    return '\n'.join(lines)


def main():
    """主流程"""
    print("=== Soli 睡眠反思（MK Sleep Cycle L2） ===\n")
    
    # 1. 加载数据
    episodes = load_recent_episodes(LOOKBACK_EPISODES)
    if not episodes:
        print("[SKIP] 最近没有 episodes_llm 数据，跳过反思。")
        sys.exit(0)
    print(f"已加载 {len(episodes)} 天 episodes")
    
    longterm = load_longterm_memory()
    print(f"MEMORY.md：{len(longterm)} 字符")
    
    # 2. 提取声明
    claims = extract_claims(episodes)
    print(f"提取 {len(claims)} 条事实声明")
    
    # 3. 构建 prompt
    prompt = build_reflect_prompt(episodes, claims, longterm)
    
    # 4. 输出
    metadata = {
        "mode": "sleep_reflect",
        "episode_count": len(episodes),
        "claim_count": len(claims),
        "longterm_chars": len(longterm),
    }
    
    print("---METADATA---")
    print(json.dumps(metadata, ensure_ascii=False))
    print("---PROMPT---")
    print(prompt)
    print("---END---")
    
    prompt_file = MEMORY_DIR / "_reflect_prompt_tmp.txt"
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(prompt)
    print(f"\nPrompt 已保存到 {prompt_file}")


if __name__ == "__main__":
    main()
