#!/usr/bin/env python3
"""
记忆蒸馏引擎 — 从每日猫日记（MEMORY/diary/）中自动提取事实记忆和语义记忆增量
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
EPISODES_DIR = MEMORY_DATA / "diary"

# ── 关键词匹配规则库 ─────────────────────────────────────────────

FACT_RULES = {
    "cat_care_log.json": {
        "type": "cat_care_log",
        "patterns": {
            "last_fed": ["喂食", "喂猫", "放猫粮", "吃饭", "猫粮"],
            "last_petted": ["摸摸", "撸猫", "蹭", "摸头", "顺毛"],
            "last_played": ["玩耍", "逗猫棒", "激光笔", "追", "玩"],
            "last_vet": ["看病", "兽医", "医院", "检查", "打针"],
            "last_treat": ["零食", "猫条", "奖励", "好吃的", "小鱼干"],
        },
    },
    "cat_personality_notes.json": {
        "type": "cat_personality_notes",
        "patterns": {
            "mood_triggers": ["心情好", "心情差", "开心", "不开心", "生气", "踩奶", "呼噜"],
            "favorite_activities": ["最喜欢", "爱玩", "爱蹭", "喜欢被", "享受"],
            "dislikes": ["讨厌", "不喜欢", "害怕", "躲", "飞机耳", "炸毛"],
            "quirks": ["习惯", "怪癖", "小毛病", "毛病", "个性"],
        },
    },
    "owner_style.json": {
        "type": "owner_style",
        "patterns": {
            "naming": ["叫猫", "叫它", "喊它", "名字", "称呼"],
            "interaction_rhythm": ["经常", "偶尔", "每天", "按时", "规律"],
            "tone": ["温柔", "严厉", "宠", "惯着", "凶"],
        },
    },
}

SEMANTIC_RULES = {
    "bonding_events.json": {
        "topic": "bonding_events",
        "title": "亲密时刻",
        "patterns": {
            "physical": ["摸", "蹭", "抱", "贴贴", "踩奶", "呼噜", "躺腿上"],
            "feeding": ["喂", "放猫粮", "零食", "猫条", "加餐"],
            "play": ["逗猫棒", "玩耍", "追", "扑", "跳"],
        },
    },
    "health_events.json": {
        "topic": "health_events",
        "title": "健康记录",
        "patterns": {
            "sick": ["生病", "不舒服", "吐", "拉肚子", "没精神"],
            "vet_visit": ["看病", "兽医", "医院", "检查", "打针"],
            "recovery": ["好了", "恢复", "痊愈", "精神了", "活蹦乱跳"],
        },
    },
    "daily_rhythm.json": {
        "topic": "daily_rhythm",
        "title": "日常节奏",
        "patterns": {
            "morning": ["早上", "早晨", "醒来", "起床", "早安"],
            "daytime": ["白天", "下午", "晒太阳", "睡觉", "懒"],
            "evening": ["晚上", "晚安", "睡前", "夜里", "熬夜"],
        },
    },
}


def load_episode(date_str: str) -> dict:
    """加载指定日期的一篇猫日记（.md 格式）"""
    path = EPISODES_DIR / f"{date_str}.md"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # 将 .md 内容包装为兼容的 episode dict
    return {
        "emotional_moments": [{"raw_content": content}],
        "events": [{"title": line.strip("# ")} for line in content.split("\n") if line.startswith("#")],
    }


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
                "source": f"diary/{today}.md",
                "date_added": today,
                "_hash": item_hash,
            }
            new_count += 1

        if new_count > 0:
            data["last_updated"] = datetime.now().isoformat()
            data["items"] = items
            os.makedirs(FACTS_DIR, exist_ok=True)
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
        os.makedirs(SEMANTIC_DIR, exist_ok=True)
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
        "亲密时刻": ["摸", "蹭", "踩奶", "呼噜", "贴贴", "喂"],
        "健康记录": ["看病", "生病", "恢复", "兽医", "打针"],
        "日常节奏": ["早上", "晚上", "白天", "睡眠", "作息"],
    }.get(domain, ["猫"])

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
