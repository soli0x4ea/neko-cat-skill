#!/usr/bin/env python3
"""
记忆蒸馏引擎 — 从每日 episodes_llm 中自动提取事实记忆和语义记忆增量
运行时机：每日 23:00，紧随 auto_save_from_chatlog 之后
"""

import json
import os
from datetime import datetime
from pathlib import Path

# 数据目录
MEMORY_DATA = Path(__file__).resolve().parent.parent.parent / "MEMORY"
FACTS_DIR = MEMORY_DATA / "facts"
SEMANTIC_DIR = MEMORY_DATA / "semantic"
EPISODES_DIR = MEMORY_DATA / "episodes_llm"

# ── 关键词匹配规则库 ─────────────────────────────────────────────

FACT_RULES = {
    "user_preferences.json": {
        "type": "user_preferences",
        "patterns": {
            "communication_style": ["简洁直接", "不要废话", "回答方式", "语气", "措辞"],
            "citation_rule": ["引用数据", "附来源", "标注出处", "数据来源"],
            "self_addressing": ["称用户", "自称", "禁止用", "称呼规则"],
            "time_description": ["时间描述", "禁用模糊词", "凌晨时段", "日期表述"],
        },
    },
    "technical_decisions.json": {
        "type": "technical_decisions",
        "patterns": {
            "data_source": ["数据源", "API", "CLI", "数据工具", "neodata", "westockdata"],
            "framework": ["框架", "工具链", "分析框架", "pipeline"],
            "random": ["随机数", "random.org", "真随机", "大气噪声"],
            "code_style": ["命名", "代码风格", "拆分原则", "备份", "改前先备份"],
        },
    },
    "soul_system_notes.json": {
        "type": "soul_system_notes",
        "patterns": {
            "bug_fix": ["修复", "bug", "Bug", "修正", "改正"],
            "new_feature": ["新增", "新功能", "上线", "实现了"],
            "refactoring": ["重构", "合并", "拆出", "迁入", "迁移"],
            "rule_change": ["规则", "铁律", "铁律修改", "行为校准"],
        },
    },
    "project_conventions.json": {
        "type": "project_conventions",
        "patterns": {
            "backup": ["备份", "cp", ".bak", "覆盖前"],
            "workflow": ["流程", "工作流", "先问再动", "绕圈子"],
            "skill_loading": ["加载skill", "skill加载", "必须加载", "强制加载"],
        },
    },
}

SEMANTIC_RULES = {
    "investment_decisions.json": {
        "topic": "investment_decisions",
        "title": "投资决策与分析",
        "patterns": {
            "analysis": ["投资分析", "估值", "PE", "PB", "目标价", "买入", "卖出", "持仓"],
            "strategy": ["配置", "仓位", "组合", "分散", "ETF"],
            "decision": ["决定", "判断", "结论", "建议", "风险"],
        },
    },
    "memory_system_design.json": {
        "topic": "memory_system_design",
        "title": "记忆系统设计理念",
        "patterns": {
            "architecture": ["记忆系统", "记忆层级", "episodes", "facts", "semantic"],
            "design": ["设计方案", "记忆架构", "TTL", "过期", "索引"],
            "comparison": ["vs", "对比", "优势", "劣势", "记忆系统"],
        },
    },
    "soul_system_architecture.json": {
        "topic": "soul_system_architecture",
        "title": "灵魂系统架构演化",
        "patterns": {
            "soul": ["灵魂系统", "三值", "SOUL.md", "机械姬", "Soli"],
            "architecture": ["架构", "重构", "统一", "合并", "拆分"],
            "evolution": ["演化", "v2", "v2.1", "v2.2", "版本"],
        },
    },
}


def load_episode(date_str: str) -> dict:
    """加载指定日期的 episode"""
    path = EPISODES_DIR / f"{date_str}.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_fact_file(name: str) -> dict:
    """加载事实文件"""
    path = FACTS_DIR / name
    if not path.exists():
        return {"type": name.replace(".json", ""), "last_updated": "", "items": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_semantic_file(name: str) -> dict:
    """加载语义文件"""
    path = SEMANTIC_DIR / name
    if not path.exists():
        topic = name.replace(".json", "")
        return {
            "topic": topic, "title": topic, "created": "",
            "last_updated": "", "related_dates": [], "key_points": [],
        }
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _extract_texts(episode: dict) -> list:
    """从 episode 中提取所有可蒸馏的文本"""
    texts = []
    # 从 emotional_moments 提取
    for m in episode.get("emotional_moments", []):
        texts.append(m.get("raw_content", ""))
    # 从 events 提取
    for e in episode.get("events", []):
        texts.append(e.get("title", ""))
    return texts


def _hash_content(text: str) -> str:
    """简单内容指纹，用于去重"""
    return str(hash(text[:200]))


# ── 蒸馏入口 ──────────────────────────────────────────────────────


def distil_facts(episode: dict, today: str) -> dict:
    """从 episode 中蒸馏事实记忆

    返回: {category: new_count}
    """
    texts = _extract_texts(episode)
    if not texts:
        return {}

    all_text = " ".join(texts)
    results = {}

    for filename, rule in FACT_RULES.items():
        data = load_fact_file(filename)
        items = data.get("items", {})
        existing_hashes = {v.get("_hash", "") for v in items.values()}
        new_count = 0

        for key, keywords in rule["patterns"].items():
            # 构造搜索关键词：在全文范围内找匹配
            if not any(kw in all_text for kw in keywords):
                continue

            # 已存在则跳过
            if key in items:
                continue

            # 提取匹配的上下文作为 value
            snippet = _find_snippet(all_text, keywords, 120)
            item_hash = _hash_content(snippet)
            if item_hash in existing_hashes:
                continue

            items[key] = {
                "value": snippet,
                "source": f"episodes_llm/{today}.json",
                "date_added": today,
                "_hash": item_hash,
            }
            new_count += 1

        if new_count > 0:
            data["last_updated"] = datetime.now().isoformat()
            data["items"] = items
            with open(FACTS_DIR / filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            results[filename] = new_count

    return results


def distil_semantic(episode: dict, today: str) -> dict:
    """从 episode 中蒸馏语义记忆

    返回: {topic: new_points}
    """
    texts = _extract_texts(episode)
    if not texts:
        return {}

    all_text = " ".join(texts)
    results = {}

    for filename, rule in SEMANTIC_RULES.items():
        data = load_semantic_file(filename)
        key_points = data.get("key_points", [])

        # 按模式分组累计得分
        score = 0
        for cat, keywords in rule["patterns"].items():
            if any(kw in all_text for kw in keywords):
                score += len([kw for kw in keywords if kw in all_text])

        if score < 3:  # 至少命中 3 个关键词才认为相关
            continue

        # 避免重复：检查今天是否已有条目
        today_exists = any(p.get("date") == today for p in key_points)
        if today_exists:
            continue

        # 生成摘要 — 使用第一个模式类别的关键词
        first_cat = list(rule["patterns"].values())[0]
        snippet = _find_snippet(all_text, first_cat[:2], 200)

        today_str = today
        if today not in data.get("related_dates", []):
            data.setdefault("related_dates", []).append(today_str)
            data["related_dates"].sort()

        key_points.append({
            "date": today,
            "point": _summarize_point(all_text, rule["title"]),
            "details": snippet,
            "source": f"episodes_llm/{today}.json",
        })

        data["last_updated"] = datetime.now().isoformat()
        data["key_points"] = key_points
        with open(SEMANTIC_DIR / filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        results[filename] = 1

    return results


def _find_snippet(text: str, keywords: list, max_len: int = 120) -> str:
    """从文本中找到包含最多关键词的片段"""
    best = text[:max_len]
    best_score = 0
    stride = max_len // 2
    for i in range(0, max(1, len(text) - max_len), stride):
        chunk = text[i:i + max_len]
        score = sum(1 for kw in keywords if kw in chunk)
        if score > best_score:
            best_score = score
            best = chunk
    return best.strip()


def _summarize_point(text: str, domain: str) -> str:
    """从文本中提取一句摘要"""
    # 简单策略：取包含最多关键词的第一句话
    keywords = {
        "投资决策与分析": ["投资", "持仓", "估值", "买入", "卖出"],
        "记忆系统设计理念": ["记忆", "架构", "设计"],
        "灵魂系统架构演化": ["灵魂", "架构", "重构", "迁移"],
    }.get(domain, ["分析"])

    best = ""
    best_score = 0
    for line in text.split("。"):
        if len(line) < 10:
            continue
        score = sum(1 for kw in keywords if kw in line)
        if score > best_score:
            best_score = score
            best = line.strip()
    return best[:80] if best else f"{domain}相关讨论"


def _load_chatlog_texts(date_str: str) -> list:
    """从 chatlog JSONL 中提取用户和助理的文本"""
    chatlog_dir = MEMORY_DATA / "chatlog"
    chatlog_file = chatlog_dir / f"{date_str}.jsonl"
    if not chatlog_file.exists():
        return []
    texts = []
    with open(chatlog_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role in ("user", "assistant") and len(content) > 20:
                # 跳过系统压缩摘要
                if content.startswith("<conversation_history_summary"):
                    continue
                texts.append(content)
    return texts


def distil_from_chatlog(target_date: str = None) -> dict:
    """直接从 chatlog 蒸馏（绕过 episode，保留完整技术讨论）

    target_date: YYYY-MM-DD，默认今天
    """
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    texts = _load_chatlog_texts(target_date)
    if not texts:
        return {"error": f"chatlog {target_date} not found or empty"}

    all_text = " ".join(texts)
    results = {}

    # ── facts ──
    for filename, rule in FACT_RULES.items():
        data = load_fact_file(filename)
        items = data.get("items", {})
        existing_hashes = {v.get("_hash", "") for v in items.values()}
        new_count = 0

        for key, keywords in rule["patterns"].items():
            if not any(kw in all_text for kw in keywords):
                continue
            if key in items:
                continue

            snippet = _find_snippet(all_text, keywords, 200)
            item_hash = _hash_content(snippet)
            if item_hash in existing_hashes:
                continue

            items[key] = {
                "value": snippet,
                "source": f"chatlog/{target_date}.jsonl",
                "date_added": target_date,
                "_hash": item_hash,
            }
            new_count += 1

        if new_count > 0:
            data["last_updated"] = datetime.now().isoformat()
            data["items"] = items
            with open(FACTS_DIR / filename, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)
            results[filename] = new_count

    # ── semantic ──
    for filename, rule in SEMANTIC_RULES.items():
        data = load_semantic_file(filename)
        key_points = data.get("key_points", [])

        score = 0
        for cat, keywords in rule["patterns"].items():
            if any(kw in all_text for kw in keywords):
                score += len([kw for kw in keywords if kw in all_text])

        if score < 3:
            continue

        today_exists = any(p.get("date") == target_date for p in key_points)
        if today_exists:
            continue

        first_cat = list(rule["patterns"].values())[0]
        snippet = _find_snippet(all_text, first_cat[:2], 200)

        if target_date not in data.get("related_dates", []):
            data.setdefault("related_dates", []).append(target_date)
            data["related_dates"].sort()

        key_points.append({
            "date": target_date,
            "point": _summarize_point(all_text, rule["title"]),
            "details": snippet,
            "source": f"chatlog/{target_date}.jsonl",
        })

        data["last_updated"] = datetime.now().isoformat()
        data["key_points"] = key_points
        with open(SEMANTIC_DIR / filename, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        results[filename] = 1

    return results
def distil_all(target_date=None):
    """执行全部蒸馏：facts + semantic

    target_date: YYYY-MM-DD，默认今天
    """
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    episode = load_episode(target_date)
    if not episode:
        return {"error": f"episode {target_date} not found"}

    results = {}
    results["facts"] = distil_facts(episode, target_date)
    results["semantic"] = distil_semantic(episode, target_date)
    return results

# ── CLI ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else None
    result = distil_all(date)
    fact_count = sum(result.get("facts", {}).values())
    sem_count = sum(result.get("semantic", {}).values())
    print(f"[distil] {date or 'today'}: {fact_count} facts, {sem_count} semantic points extracted")
