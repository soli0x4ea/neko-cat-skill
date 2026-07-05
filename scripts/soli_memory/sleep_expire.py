#!/usr/bin/env python3
"""
Soli 的睡眠遗忘 — MK Sleep Cycle 第3层
每月 1 号 03:30 运行：P0/P1/P2 分级遗忘，归 archive 压缩。

核心理念（来自 MK）：
- "忘记是功能不是 bug"
- 不是删除，是压缩和归档
- P0：核心偏好、基础设施 — 永久保留
- P1：技术方案、工具设定 — 带日期，过时压缩
- P2：实验、临时记录 — 30 天无引用即归 archive

处理对象：
- MEMORY/chatlog/      — 超过 30 天的 JSONL → archive
- MEMORY/episodes/     — 超过 30 天的 JSON → archive
- MEMORY/episodes_llm/ — 超过 30 天的 JSON → archive
- MEMORY/daily_distill/— 超过 30 天的文件 → archive
"""

import os
import sys
import json
import shutil
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import List, Tuple

# ── 路径配置 ──
SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_DIR = SKILL_ROOT / "MEMORY"
ARCHIVE_ROOT = MEMORY_DIR / "archive"

# 需要归档的子目录
ARCHIVE_TARGETS = ["chatlog", "episodes", "episodes_llm"]

# 归档阈值
ARCHIVE_DAYS = 30  # 超过 30 天的文件归档

# P0 保护列表 — 永远不动
P0_PATTERNS = [
    "MEMORY.md",          # 长期记忆索引
    "relationships/",     # 关系模式
    "facts/",             # 结构化事实
    "semantic/",          # 语义记忆
    "index/",             # 搜索索引
    "fingerprint/",       # 数字指纹
    "interaction_patterns.json",
    "dreams.md",
    "reflections.md",
    "timeline.jsonl",
]


def is_within_days(file_path: Path, days: int) -> bool:
    """文件是否在 N 天内"""
    try:
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        age = datetime.now() - mtime
        return age.days <= days
    except OSError:
        return True  # 无法判断则保留


def is_p0_protected(file_path: Path) -> bool:
    """检查文件/目录是否在 P0 保护列表中"""
    rel_path = str(file_path.relative_to(MEMORY_DIR))
    for pattern in P0_PATTERNS:
        if rel_path.startswith(pattern) or rel_path == pattern:
            return True
    return False


def scan_expired_files() -> List[Tuple[Path, str]]:
    """扫描可归档的文件，返回 (文件路径, 归档原因)"""
    expired = []
    
    for target in ARCHIVE_TARGETS:
        target_dir = MEMORY_DIR / target
        if not target_dir.exists():
            continue
        
        for item in sorted(target_dir.iterdir()):
            # 跳过隐藏文件、目录、临时文件
            if item.name.startswith('.') or item.name.startswith('_'):
                continue
            if item.is_dir():
                continue
            if item.suffix == '.py':
                continue
            
            if not is_within_days(item, ARCHIVE_DAYS):
                expired.append((item, f"超过 {ARCHIVE_DAYS} 天（{target}/）"))
    
    return expired


def archive_file(file_path: Path, reason: str) -> Path:
    """将文件移至 archive 目录，保持原有相对结构"""
    # 计算相对于 MEMORY_DIR 的路径
    rel_path = file_path.relative_to(MEMORY_DIR)
    
    # 按月份归档
    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
    month_dir = mtime.strftime('%Y-%m')
    archive_dir = ARCHIVE_ROOT / month_dir / rel_path.parent
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    dest = archive_dir / file_path.name
    
    # 如果目标已存在，加时间戳
    if dest.exists():
        timestamp = datetime.now().strftime('%H%M%S')
        dest = archive_dir / f"{file_path.stem}_{timestamp}{file_path.suffix}"
    
    shutil.move(str(file_path), str(dest))
    return dest


def archive_report(archived: List[Tuple[Path, Path, str]]) -> str:
    """生成归档报告"""
    lines = []
    lines.append(f"# 月度归档报告 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    
    if not archived:
        lines.append("本月无需归档。所有文件均在 30 天内。")
        return '\n'.join(lines)
    
    lines.append(f"共归档 {len(archived)} 个文件：\n")
    
    by_dir = {}
    for src, dest, reason in archived:
        rel = str(src.relative_to(MEMORY_DIR))
        dir_name = str(Path(rel).parent) or "/"
        if dir_name not in by_dir:
            by_dir[dir_name] = []
        by_dir[dir_name].append(f"- {Path(rel).name} → {dest}")
    
    for dir_name, files in sorted(by_dir.items()):
        lines.append(f"## {dir_name}")
        lines.append(f"（{len(files)} 个文件）")
        lines.extend(files)
        lines.append("")
    
    lines.append(f"---")
    lines.append(f"归档位置：`{ARCHIVE_ROOT}`")
    lines.append(f"需要时仍可查找，但不再占用 context window。")
    
    return '\n'.join(lines)


def compress_p2_entries(memory_file: Path) -> dict:
    """扫描 MEMORY.md 中超过 90 天的 P2 级条目，输出压缩建议（不自动修改）"""
    # P2 特征：实验性、临时性、已过时
    # 这一步只生成建议，由 reflect 层或人工决定是否执行
    result = {"scanned": False, "suggestions": []}
    
    if not memory_file.exists():
        return result
    
    result["scanned"] = True
    
    try:
        with open(memory_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError:
        return result
    
    sections = content.split('\n## ')
    for section in sections[1:]:  # 跳过文件头
        # 检查章节是否有「最近更新」标签
        if '📅 最后更新' not in section and '📅 更新于' not in section:
            continue
        
        # 尝试提取日期
        import re
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', section)
        if not date_match:
            continue
        
        try:
            section_date = datetime.strptime(date_match.group(1), '%Y-%m-%d')
            age = (datetime.now() - section_date).days
        except ValueError:
            continue
        
        # 超过 90 天的章节建议压缩
        if age > 90:
            title = section.split('\n')[0] if section else "?"
            result["suggestions"].append({
                "section": title[:60],
                "age_days": age,
                "suggestion": f"压缩：移入 reference/ 或缩减为一行摘要",
            })
    
    return result


def main():
    """主流程"""
    print("=== Soli 睡眠遗忘（MK Sleep Cycle L3） ===\n")
    
    # 1. 扫描过期文件
    expired = scan_expired_files()
    print(f"找到 {len(expired)} 个可归档文件")
    
    if not expired:
        print("所有文件均在 30 天内，无需归档。")
        sys.exit(0)
    
    # 2. 逐个归档
    archived = []
    for file_path, reason in expired:
        # 双重检查 P0 保护
        if is_p0_protected(file_path):
            print(f"[P0 保护] 跳过：{file_path.name}")
            continue
        
        try:
            dest = archive_file(file_path, reason)
            archived.append((file_path, dest, reason))
            print(f"[归档] {file_path.name} → {dest}")
        except OSError as e:
            print(f"[错误] 无法归档 {file_path.name}：{e}")
    
    # 3. 生成归档报告
    report = archive_report(archived)
    report_file = ARCHIVE_ROOT / f"archive_report_{datetime.now().strftime('%Y%m')}.md"
    os.makedirs(ARCHIVE_ROOT, exist_ok=True)
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n归档报告：{report_file}")
    print(f"共归档 {len(archived)} 个文件")
    
    # 4. P2 压缩建议
    memory_file = Path(os.path.expandvars(r"~/.workbuddy/memory/MEMORY.md"))
    p2_result = compress_p2_entries(memory_file)
    if p2_result["suggestions"]:
        print(f"\nP2 压缩建议（{len(p2_result['suggestions'])} 条）：")
        for s in p2_result["suggestions"]:
            print(f"  - [{s['age_days']}天] {s['section']}")
    
    # 5. 输出 JSON 摘要
    summary = {
        "mode": "sleep_expire",
        "expired_count": len(expired),
        "archived_count": len(archived),
        "p2_suggestions": len(p2_result.get("suggestions", [])),
        "report": str(report_file),
    }
    print("\n---SUMMARY---")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
