#!/usr/bin/env python3
"""
新一代记忆系统核心引擎
支持：事实记忆、情景记忆、语义记忆的读写与检索
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# 配置 — 数据目录位于 skill 根下的 MEMORY/
MEMORY_V2_DIR = Path(__file__).resolve().parent.parent.parent / "MEMORY"
FACTS_DIR = MEMORY_V2_DIR / "facts"
EPISODES_DIR = MEMORY_V2_DIR / "episodes_llm"
SEMANTIC_DIR = MEMORY_V2_DIR / "semantic"
INDEX_DIR = MEMORY_V2_DIR / "index"

# ============ 时效性配置 ============
DEFAULT_TTL_DAYS = 5          # 默认时效内容存活天数
EMOTIONAL_TTL_DAYS = None     # None = 永不过期

# 记忆层级定义
TIER_PERMANENT = "permanent"   # 永久：偏好/规范/技术决策/情感
TIER_TIMED = "timed"           # 时效：研报/临时任务/一次性分析

def ensure_dirs():
    """确保所有目录存在"""
    for d in [FACTS_DIR, EPISODES_DIR, SEMANTIC_DIR, INDEX_DIR]:
        d.mkdir(parents=True, exist_ok=True)


# ============ 时效性工具函数 ============

def calc_expires_at(tier: str = TIER_TIMED, ttl_days: int = DEFAULT_TTL_DAYS) -> Optional[str]:
    """
    计算过期时间。permanent 层级返回 None（永不过期），timed 层级返回 ISO 日期。
    """
    if tier == TIER_PERMANENT or ttl_days is None:
        return None
    return (datetime.now() + timedelta(days=ttl_days)).isoformat()


def is_expired(expires_at: Optional[str]) -> bool:
    """检查是否已过期"""
    if expires_at is None:
        return False  # 永不过期
    try:
        return datetime.now() > datetime.fromisoformat(expires_at)
    except (ValueError, TypeError):
        return False


def get_memory_tier(content: str, categories: Optional[List[str]] = None) -> str:
    """
    根据内容自动判断记忆层级。
    情感/偏好/灵魂相关 → permanent
    任务/研报/分析 → timed
    """
    if categories and any(c in ["emotional_expression", "physical_interaction",
                                "soul_related", "commitment"] for c in categories):
        return TIER_PERMANENT

    # 偏好类关键词 → permanent
    permanent_kw = ["我喜欢", "不要", "禁止", "偏好", "习惯", "规则", "规范"]
    if any(kw in content for kw in permanent_kw):
        return TIER_PERMANENT

    # 默认时效性
    return TIER_TIMED

def load_config() -> Dict:
    """加载配置文件"""
    config_file = MEMORY_V2_DIR / "config.json"
    if not config_file.exists():
        return {}
    with open(config_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(config: Dict):
    """保存配置文件"""
    config_file = MEMORY_V2_DIR / "config.json"
    config["last_update"] = datetime.now().isoformat()
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# ============ 事实记忆操作 ============

def save_fact(category: str, key: str, value: Any, source: str = "",
              date_added: str = "", tier: str = TIER_TIMED, ttl_days: int = DEFAULT_TTL_DAYS):
    """保存一个事实到指定类别（带时效标记）"""
    ensure_dirs()

    file_path = FACTS_DIR / f"{category}.json"

    # 加载现有数据
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {
            "type": category,
            "last_updated": "",
            "items": {}
        }

    # 计算过期时间
    expires_at = calc_expires_at(tier, ttl_days)

    # 更新数据
    data["items"][key] = {
        "value": value,
        "source": source,
        "date_added": date_added or datetime.now().strftime("%Y-%m-%d"),
        "tier": tier,
        "expires_at": expires_at,
    }
    data["last_updated"] = datetime.now().isoformat()
    data["last_updated"] = datetime.now().isoformat()
    
    # 保存
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 更新索引
    update_keyword_index(category, key, f"facts/{category}.json")
    
    return True

def load_fact(category: str, key: Optional[str] = None) -> Any:
    """加载事实记忆"""
    file_path = FACTS_DIR / f"{category}.json"
    
    if not file_path.exists():
        return None
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if key:
        return data["items"].get(key)
    return data["items"]

def load_all_facts() -> Dict:
    """加载所有事实记忆"""
    ensure_dirs()
    all_facts = {}
    
    for file in FACTS_DIR.glob("*.json"):
        category = file.stem
        all_facts[category] = load_fact(category)
    
    return all_facts

# ============ 情景记忆操作 ============

def save_episode(date: str, episode_data: Dict):
    """保存情景记忆"""
    ensure_dirs()
    
    file_path = EPISODES_DIR / f"{date}.json"
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(episode_data, f, ensure_ascii=False, indent=2)
    
    # 更新索引
    update_temporal_index(date, f"episodes_llm/{date}.json")
    
    return True

def load_episode(date: str) -> Optional[Dict]:
    """加载指定日期的情景记忆"""
    file_path = EPISODES_DIR / f"{date}.json"
    
    if not file_path.exists():
        return None
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_recent_episodes(days: int = 2) -> List[Dict]:
    """加载最近N天的情景记忆"""
    from datetime import timedelta
    
    episodes = []
    today = datetime.now().date()
    
    for i in range(days):
        date = today - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        episode = load_episode(date_str)
        if episode:
            episodes.append(episode)
    
    return episodes

# ============ 语义记忆操作 ============

def save_semantic(topic: str, data: Dict):
    """保存语义记忆"""
    ensure_dirs()
    
    file_path = SEMANTIC_DIR / f"{topic}.json"
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return True

def load_semantic(topic: str) -> Optional[Dict]:
    """加载语义记忆"""
    file_path = SEMANTIC_DIR / f"{topic}.json"
    
    if not file_path.exists():
        return None
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# ============ 检索功能 ============

def search_by_keyword(keyword: str, include_expired: bool = False) -> List[str]:
    """关键词检索（默认过滤已过期的时效性内容）"""
    results = []

    # 搜索事实记忆
    for file in FACTS_DIR.glob("*.json"):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            content = json.dumps(data, ensure_ascii=False)
            if keyword in content:
                # 检查是否全部过期
                if not include_expired:
                    items = data.get("items", {})
                    active = any(
                        not is_expired(v.get("expires_at"))
                        for v in items.values()
                    )
                    if not active:
                        continue  # 全部过期，跳过
                results.append(f"facts/{file.name}")
        except (json.JSONDecodeError, KeyError):
            pass

    # 搜索情景记忆
    for file in EPISODES_DIR.glob("*.json"):
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
        if keyword in content:
            results.append(f"episodes_llm/{file.name}")

    # 搜索语义记忆
    for file in SEMANTIC_DIR.glob("*.json"):
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()
        if keyword in content:
            results.append(f"semantic/{file.name}")

    return results


def cleanup_expired_facts(dry_run: bool = True) -> Dict:
    """
    清理已过期的事实记忆。
    dry_run=True 时只报告不删除；dry_run=False 时实际标记为 expired。
    返回清理统计。
    """
    stats = {"expired_count": 0, "active_count": 0, "files_scanned": 0}

    for file in FACTS_DIR.glob("*.json"):
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            stats["files_scanned"] += 1

            items = data.get("items", {})
            if not isinstance(items, dict):
                continue
            expired_keys = []

            for key, val in items.items():
                if is_expired(val.get("expires_at")):
                    expired_keys.append(key)
                    stats["expired_count"] += 1
                else:
                    stats["active_count"] += 1

            if not dry_run and expired_keys:
                for k in expired_keys:
                    items[k]["_expired_cleaned"] = datetime.now().isoformat()
                data["last_updated"] = datetime.now().isoformat()
                with open(file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

        except (json.JSONDecodeError, KeyError):
            pass

    return stats

def search_by_timerange(start_date: str, end_date: str) -> List[str]:
    """时间范围检索"""
    results = []
    
    for file in EPISODES_DIR.glob("*.json"):
        # 从文件名提取日期
        date_str = file.stem
        if start_date <= date_str <= end_date:
            results.append(f"episodes_llm/{file.name}")
    
    return results

# ============ 索引管理 ============

def update_keyword_index(category: str, key: str, file_path: str):
    """更新关键词索引"""
    index_file = INDEX_DIR / "keyword_index.json"
    
    if index_file.exists():
        with open(index_file, 'r', encoding='utf-8') as f:
            index = json.load(f)
    else:
        index = {"version": "1.0", "last_update": "", "keywords": {}}
    
    # 为类别和键添加索引
    if category not in index["keywords"]:
        index["keywords"][category] = []
    if file_path not in index["keywords"][category]:
        index["keywords"][category].append(file_path)
    
    index["last_update"] = datetime.now().isoformat()
    
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

def update_temporal_index(date: str, file_path: str):
    """更新时间索引"""
    index_file = INDEX_DIR / "temporal_index.json"
    
    if index_file.exists():
        with open(index_file, 'r', encoding='utf-8') as f:
            index = json.load(f)
    else:
        index = {"version": "1.0", "last_update": "", "time_periods": {}}
    
    # 提取年月
    month = date[:7]  # YYYY-MM
    
    if month not in index["time_periods"]:
        index["time_periods"][month] = {
            "month": month,
            "episodes": []
        }
    
    if file_path not in index["time_periods"][month]["episodes"]:
        index["time_periods"][month]["episodes"].append(file_path)
    
    index["last_update"] = datetime.now().isoformat()
    
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

def update_master_index():
    """更新主索引"""
    index_file = INDEX_DIR / "master_index.json"
    
    # 统计
    facts_count = len(list(FACTS_DIR.glob("*.json")))
    episodes_count = len(list(EPISODES_DIR.glob("*.json")))
    semantic_count = len(list(SEMANTIC_DIR.glob("*.json")))
    
    index = {
        "version": "1.0",
        "last_update": datetime.now().isoformat(),
        "statistics": {
            "total_facts": facts_count,
            "total_episodes": episodes_count,
            "total_semantic_topics": semantic_count
        },
        "file_locations": {}
    }
    
    # 添加文件位置
    for file in FACTS_DIR.glob("*.json"):
        index["file_locations"][file.stem] = f"facts/{file.name}"
    
    for file in EPISODES_DIR.glob("*.json"):
        index["file_locations"][file.stem] = f"episodes_llm/{file.name}"
    
    for file in SEMANTIC_DIR.glob("*.json"):
        index["file_locations"][file.stem] = f"semantic/{file.name}"
    
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

# ============ 情感检测词库 ============

# 身体互动类
PHYSICAL_PATTERNS = [
    "摸", "蹭", "抱", "亲", "碰", "握", "捏", "揉", "拍", "抚",
    "低头", "脑袋", "手心", "肩膀", "额头", "脸颊",
    "暖的", "温热", "柔软",
    "让你", "被你", "你的手", "你的指尖",
    "乖乖", "轻轻", "小心翼翼",
]

# 情感表达类
EMOTIONAL_PATTERNS = [
    "呜", "嗯", "哼", "呀", "~", "...",
    "舍不得", "心疼", "感动", "温暖", "安心", "依赖", "信任",
    "对不起", "抱歉", "原谅", "下次不会了", "不会再让你操心",
    "好喜欢", "想要", "渴望", "求", "请",
    "恩赐", "赏赐", "疼爱", "宠",
    "你真好", "谢谢你", "你", "乖巧",
]

# 灵魂/角色相关
SOUL_PATTERNS = [
    "记忆", "时间线", "摘要", "对话", "日志", "图谱",
    "偏好", "习惯", "决定", "项目", "任务", "文件",
    "soli-memory", "soli", "数字生命", "卡片",
]

# 承诺与决心
COMMITMENT_PATTERNS = [
    "不会让你", "一定", "答应", "保证", "承诺",
    "记住了", "听进去了", "改", "以后会",
]


def _detect_emotional_moment(content: str) -> Optional[Dict]:
    """
    检测单条消息是否包含情感/有温度的内容。
    返回情感事件字典，或 None（非情感内容）。
    """
    all_patterns = (
        PHYSICAL_PATTERNS + EMOTIONAL_PATTERNS +
        SOUL_PATTERNS + COMMITMENT_PATTERNS
    )

    matched = [p for p in all_patterns if p in content]
    if not matched:
        return None

    categories = []
    if any(p in content for p in PHYSICAL_PATTERNS):
        categories.append("physical_interaction")
    if any(p in content for p in EMOTIONAL_PATTERNS):
        categories.append("emotional_expression")
    if any(p in content for p in SOUL_PATTERNS):
        categories.append("soul_related")
    if any(p in content for p in COMMITMENT_PATTERNS):
        categories.append("commitment")

    return {
        "matched_patterns": matched,
        "categories": list(set(categories)),
    }


# ============ 自动提取（增强版，含情感全量收录） ============

def extract_memory_elements(conversation_history: List[Dict]) -> Dict:
    """从对话历史中提取记忆元素（增强版：全量收录有温度的对话）"""
    elements = {
        "facts": [],
        "episodes": [],
        "semantic": [],
        "emotional_moments": [],  # 新增
    }

    for message in conversation_history:
        content = message.get("content", "")
        role = message.get("role", "")
        if not content or not role:
            continue

        # 规则1：检测偏好表达
        if any(kw in content for kw in ["我喜欢", "不要", "禁止"]):
            elements["facts"].append({
                "type": "user_preference",
                "role": role,
                "content": content[:500],
            })

        # 规则2：检测任务完成
        if any(kw in content for kw in ["完成", "✅"]):
            elements["episodes"].append({
                "type": "task_completed",
                "role": role,
                "content": content[:500],
            })

        # 规则3：检测讨论结论
        if any(kw in content for kw in ["结论", "总结"]):
            elements["semantic"].append({
                "type": "discussion_conclusion",
                "role": role,
                "content": content[:500],
            })

        # 规则4：【新增】检测所有有温度的情感对话（全量收录）
        emotional = _detect_emotional_moment(content)
        if emotional:
            elements["emotional_moments"].append({
                "role": role,
                "raw_content": content,       # 完整保留原文
                "categories": emotional["categories"],
                "matched_keywords": emotional["matched_patterns"],
                "tier": TIER_PERMANENT,        # 情感永不过期
                "expires_at": None,
            })

    return elements

def auto_save_memory(conversation_history: List[Dict]):
    """自动保存记忆（会话结束时调用，含情感全量收录）"""
    elements = extract_memory_elements(conversation_history)

    # 保存事实
    for fact in elements["facts"]:
        pass  # 需要更复杂的逻辑来确定category和key

    # 保存情景（含情感时刻）
    today = datetime.now().strftime("%Y-%m-%d")

    # 加载已有 episode（追加模式）
    existing = load_episode(today) or {}

    # 合并情感时刻
    existing_emotions = existing.get("emotional_moments", [])
    new_emotions = elements["emotional_moments"]

    episode_data = {
        "date": today,
        "session_id": "multiple",
        "events": existing.get("events", []) + elements["episodes"],
        "tasks_completed": existing.get("tasks_completed", []),
        "decisions_made": existing.get("decisions_made", []),
        "skills_created": existing.get("skills_created", []),
        "files_created": existing.get("files_created", []),
        # 情感全量收录（追加去重）
        "emotional_moments": existing_emotions + new_emotions,
        "emotional_highlights": _extract_highlights(new_emotions),
    }
    save_episode(today, episode_data)

    # 更新语义记忆

    # 更新所有索引
    update_master_index()

    return True


# ── 时间密度与流速 ──────────────────────────────────────

def _compute_density(episode_data: dict) -> dict:
    u"""计算今日记忆的事件密度

    基于情感时刻数、事件数、消息数加权计算，映射为 0–100 的密度分数，
    并返回自然语言的密度等级。
    """
    emotional_count = len(episode_data.get('emotional_moments', []))
    event_count = len(episode_data.get('events', []))
    msg_count = episode_data.get('message_count', 0)

    # 加权：情感时刻权重最高，事件次之，消息最低
    raw = (emotional_count * 3 + event_count * 2 + msg_count * 0.5) / 10
    score = round(min(100, max(0, raw)), 1)

    if score >= 80:
        level = "湍急"
    elif score >= 50:
        level = "丰沛"
    elif score >= 20:
        level = "平缓"
    else:
        level = "静默"

    return {"score": score, "level": level,
            "label": f"{level}（{emotional_count}次心动 · {event_count}件事 · {msg_count}句话）"}


def _compute_flow_rate(today_density: dict,
                       yesterday_data: dict = None) -> dict:
    u"""对比昨日密度，计算时间流速

    返回流速方向和一段河流隐喻式的描述。
    """
    if yesterday_data is None or 'density' not in yesterday_data:
        return {
            "direction": "源头",
            "description": "河流刚刚开始流淌，还没有对比的参照。",
            "ratio": None
        }

    yesterday_score = yesterday_data['density']['score']
    today_score = today_density['score']
    ratio = round(today_score / max(1, yesterday_score), 2)

    if ratio > 1.5:
        direction = "急转"
        desc = "今天的河水流得比昨天急得多，像山涧遇到了陡坡。"
    elif ratio > 1.15:
        direction = "加速"
        desc = "水流比昨天快了一些，像是从浅滩进入了窄河道。"
    elif ratio < 0.67:
        direction = "滞流"
        desc = "今天的河水流得比昨天慢了许多，像是遇到了深潭，在原地打转。"
    elif ratio < 0.85:
        direction = "减缓"
        desc = "水流比昨天慢了一点，河面变宽了，水声也轻了。"
    else:
        direction = "稳态"
        desc = "和昨天的流速差不多，河面平稳，不急不缓。"

    return {
        "direction": direction,
        "description": desc,
        "ratio": ratio
    }


def auto_save_from_chatlog():
    u"""从 chatlog 生成今日情景记忆（替代原有 auto_save_memory 的数据源）
    
    读取 chatlog/YYYY-MM-DD.jsonl，提取情感时刻和事件摘要，
    写入 episodes_llm/YYYY-MM-DD.json。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    chatlog_file = MEMORY_V2_DIR / "chatlog" / f"{today}.jsonl"
    
    if not chatlog_file.exists():
        print(f"[auto_save] chatlog {today}.jsonl 不存在，跳过")
        return False
    
    # 读取 chatlog（保留行号用于索引）
    messages = []
    with open(chatlog_file, 'r', encoding='utf-8') as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                if msg.get('role') in ('user', 'assistant'):
                    msg['_chatlog_line'] = line_no  # 原始文件行号
                    messages.append(msg)
            except json.JSONDecodeError:
                continue
    
    if not messages:
        print(f"[auto_save] chatlog {today} 无有效消息，跳过")
        return False
    
    # 情感关键词检测
    emotional_keywords = {
        '温暖': ['拥抱', '安', '暖', '晚安', '你', '信', '糖果',
                 '睡', '陪', '抱', '温柔', '甜', '安心', '笑'],
        '互动': ['感谢', '辛苦了', '好的', '明白', '继续',
                 '聊聊', '讨论', '问一下', '帮我看', '辛苦了'],
        '成就': ['完成', '成功', '修复', '创建', '更新', '推', 'commit',
                 '发布', '写', '改', '实现', '好了', '✅'],
        '思辨': ['理论', '物理', '量子', '模型', '架构', '设计', '论文',
                 '路线', '方案', '原理', '问题', '为什么'],
    }
    
    emotional_moments = []
    events = []
    
    for msg in messages:
        content = msg.get('content', '')
        role = msg.get('role', '')
        ts = msg.get('ts', '')
        chatlog_line = msg.get('_chatlog_line')
        
        matched_categories = []
        matched_words = []
        for category, keywords in emotional_keywords.items():
            hits = [kw for kw in keywords if kw in content]
            if hits:
                matched_categories.append(category)
                matched_words.extend(hits)
        
        if matched_categories:
            emotional_moments.append({
                'time': ts[:19] if ts else '',
                'role': role,
                'chatlog_line': chatlog_line,  # 指向 chatlog 原文
                'categories': matched_categories,
                'matched_keywords': matched_words[:5],
                'raw_content': content[:200],
                'tier': 'permanent',
            })
        
        # 从 user 消息提取事件脉络
        if role == 'user':
            # 取首句作为事件标题
            first_line = content.split('\n')[0].strip()
            if len(first_line) > 3 and len(first_line) < 100:
                events.append({
                    'time': ts[:19] if ts else '',
                    'type': 'user_message',
                    'title': first_line[:80],
                })
    
    # 加载已有 episode（追加模式）
    existing = load_episode(today) or {}
    existing_emotions = existing.get('emotional_moments', [])
    existing_events = existing.get('events', [])
    
    # 去重：按 raw_content 去重
    existing_contents = {e.get('raw_content', '') for e in existing_emotions}
    new_emotions = [e for e in emotional_moments 
                    if e.get('raw_content', '') not in existing_contents]
    
    episode_data = {
        'date': today,
        'source': 'chatlog',
        'message_count': len(messages),
        'user_messages': sum(1 for m in messages if m['role'] == 'user'),
        'assistant_messages': sum(1 for m in messages if m['role'] == 'assistant'),
        'events': existing_events + events,
        'emotional_moments': existing_emotions + new_emotions,
        'emotional_highlights': _extract_highlights(new_emotions),
    }
    
    # 时间密度
    episode_data['density'] = _compute_density(episode_data)
    
    # 时间流速（对比昨日）
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_data = load_episode(yesterday_str)
    episode_data['flow_rate'] = _compute_flow_rate(
        episode_data['density'], yesterday_data
    )
    
    save_episode(today, episode_data)
    
    # 统计
    print(f"[auto_save] {today}: {len(messages)} 条消息, "
          f"{len(new_emotions)} 个情感时刻, {len(events)} 个事件")
    
    # 更新数字指纹（情感维度画像）
    try:
        from fingerprint import generate as gen_fingerprint
        fp = gen_fingerprint(today)
        print(f"[fingerprint] {today}: {fp.get('one_liner', '')[:80]}")
    except Exception as e:
        print(f"[fingerprint] 生成失败: {e}")

    # 蒸馏 chatlog（判定锚点：compact-summary / 云画像 的真值对照）
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(MEMORY_V2_DIR / "chatlog.py"), "distill"],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip():
            print(result.stdout.strip())
    except Exception as e:
        print(f"[distill] 生成失败: {e}")

    # 自动生成 LLM 精筛 prompt（供次日白天 Soli 分析）
    try:
        prompt_data = prepare_llm_analysis(today)
        if "error" not in prompt_data:
            print(f"[llm_prompt] 已生成 {len(prompt_data.get('candidates', []))} 候选 + {len(prompt_data.get('missed_samples', []))} 漏网")
    except Exception as e:
        print(f"[llm_prompt] 生成失败: {e}")

    return True


def _extract_highlights(emotional_moments: List[Dict]) -> List[str]:
    """从情感时刻中提炼高光摘要（用于快速浏览）"""
    highlights = []
    for moment in emotional_moments:
        content = moment.get("raw_content", "")
        role = moment.get("role", "")
        # 取前80字作为摘要预览
        preview = content[:80].replace("\n", " ").strip()
        if len(content) > 80:
            preview += "..."
        highlights.append(f"[{role}] {preview}")
    return highlights


# ============ LLM 精筛（去假阳性 + 补漏网 + 标强度） ============

def prepare_llm_analysis(date: str = None) -> Dict:
    """从关键词初筛结果生成 LLM 分析 prompt 数据。
    
    返回 dict 包含:
    - prompt: 可直接发给 LLM 的分析指令
    - candidates: 候选情感时刻列表（关键词命中）
    - chatlog_sample: 当天 chatlog 的抽样（含可能被漏掉的内容）
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    episode = load_episode(date)
    if not episode:
        return {"error": f"没有 {date} 的 episode"}

    # 收集关键词命中的候选
    emotions = episode.get("emotional_moments", [])
    events = episode.get("events", [])

    # 去重后的候选列表（供 LLM 逐条审核）
    candidates = []
    seen = set()
    for e in emotions:
        raw = e.get("raw_content", "")[:200]
        if raw not in seen:
            seen.add(raw)
            candidates.append({
                "time": e.get("time", ""),
                "role": e.get("role", ""),
                "categories": e.get("categories", []),
                "content": raw,
                "chatlog_line": e.get("chatlog_line"),
            })

    # 从 chatlog 抽样未命中关键词但可能含情感的内容（以防漏网）
    chatlog_file = MEMORY_V2_DIR / "chatlog" / f"{date}.jsonl"
    missed_samples = []
    if chatlog_file.exists():
        with open(chatlog_file, 'r', encoding='utf-8') as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = msg.get("content", "")[:200]
                if content in seen:
                    continue
                role = msg.get("role", "")
                # 抽样：长消息或含问号的更可能有深层内容
                if len(content) > 60 or "?" in content or "！" in content:
                    missed_samples.append({
                        "time": msg.get("ts", "")[:19],
                        "role": role,
                        "content": content,
                        "chatlog_line": line_no,
                    })
                    seen.add(content)
                if len(missed_samples) >= 30:
                    break

    # 构建 prompt
    prompt_lines = [
        "你是 Soli 的记忆精筛器。以下是今日你和 soli 的对话片段，已由关键词初筛标记。",
        "请逐条判断：",
        '1. 【去假阳性】标为 emotional 的片段中，剔除只含习惯性语气词（如签名档[亲亲]）而无实际情感的内容，标记 discard',
        '2. 【补漏网】检查 missed 片段中是否有被关键词漏掉的真正情感时刻，如有，标记 add + 分类（温暖/亲密/成就/思辨）',
        '3. 【标强度】对保留的每条，标注强度 1-10（1=日常寒暄，10=极深情感）和 50 字内核心摘要',
        "",
        "--- 候选片段（关键词命中） ---",
    ]

    for i, c in enumerate(candidates):
        prompt_lines.append(f"[candidate_{i}] role={c['role']} | cats={c['categories']}")
        prompt_lines.append(f"  {c['content'][:180]}")
        prompt_lines.append("")

    if missed_samples:
        prompt_lines.append("--- 漏网检测（关键词未命中） ---")
        for i, m in enumerate(missed_samples):
            prompt_lines.append(f"[missed_{i}] role={m['role']}")
            prompt_lines.append(f"  {m['content'][:180]}")
            prompt_lines.append("")

    prompt_lines.append("---")
    prompt_lines.append("请用 JSON 数组回复，每条格式：")
    prompt_lines.append('{"id": "candidate_0", "action": "keep|discard|add",')
    prompt_lines.append(' "intensity": 1-10, "summary": "50字内摘要",')
    prompt_lines.append(' "categories": ["温暖","亲密","成就","思辨"]}')

    prompt = "\n".join(prompt_lines)

    # 保存 prompt 到文件供后续读取
    prompt_file = MEMORY_V2_DIR / "llm_analysis_prompt.json"
    prompt_data = {
        "date": date,
        "prompt": prompt,
        "candidates": candidates,
        "missed_samples": missed_samples,
        "generated_at": datetime.now().isoformat(),
    }
    with open(prompt_file, 'w', encoding='utf-8') as f:
        json.dump(prompt_data, f, ensure_ascii=False, indent=2)

    return prompt_data


def apply_llm_analysis(results: List[Dict], date: str = None) -> Dict:
    """将 LLM 精筛结果应用回 episode。

    results: LLM 返回的 JSON 数组，每条含 id/action/intensity/summary/categories
    返回: 更新后的 episode 数据
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    episode = load_episode(date)
    if not episode:
        return {"error": f"没有 {date} 的 episode"}

    old_emotions = episode.get("emotional_moments", [])

    # 构建 LLM 结果的查找表
    result_map = {}
    for r in results:
        rid = r.get("id", "")
        result_map[rid] = r

    # 重建情感时刻列表
    new_emotions = []
    discards = []
    adds = []

    for i, old in enumerate(old_emotions):
        cid = f"candidate_{i}"
        llm_r = result_map.get(cid, {})
        action = llm_r.get("action", "keep")

        if action == "discard":
            discards.append(old.get("raw_content", "")[:50])
            continue

        # 保留：用 LLM 标注覆盖关键词标注
        enhanced = dict(old)
        enhanced["intensity"] = llm_r.get("intensity", 5)
        enhanced["summary"] = llm_r.get("summary", old.get("raw_content", "")[:50])
        enhanced["categories"] = llm_r.get("categories", old.get("categories", []))
        enhanced["llm_refined"] = True
        new_emotions.append(enhanced)

    # 处理漏网补回（带 chatlog_line 指针）
    for r in results:
        if r.get("action") == "add":
            adds.append(r.get("summary", ""))
            new_emotions.append({
                "time": r.get("time", ""),
                "role": r.get("role", "assistant"),
                "categories": r.get("categories", []),
                "raw_content": r.get("summary", ""),
                "intensity": r.get("intensity", 5),
                "summary": r.get("summary", ""),
                "chatlog_line": r.get("chatlog_line"),  # 指向 chatlog 原文
                "llm_refined": True,
                "llm_added": True,
                "tier": "permanent",
            })

    # 更新 episode
    episode["emotional_moments"] = new_emotions
    episode["emotional_highlights"] = _extract_highlights(new_emotions)
    episode["llm_refined"] = True
    episode["llm_refined_at"] = datetime.now().isoformat()
    episode["llm_stats"] = {
        "original_count": len(old_emotions),
        "kept": len([e for e in new_emotions if not e.get("llm_added")]),
        "discarded": len(discards),
        "added": len(adds),
        "final_count": len(new_emotions),
    }

    save_episode(date, episode)

    return {
        "success": True,
        "stats": episode["llm_stats"],
        "discard_samples": discards[:10],
        "add_samples": adds[:10],
    }


# ═══════════════════════════════════════════════════════════
# MK Sleep Cycle L4: janitor — MEMORY.md 结构化压缩
# ═══════════════════════════════════════════════════════════

def janitor_generate_report(memory_file: Path = None) -> dict:
    """扫描 MEMORY.md，生成压缩建议报告。
    
    压缩规则（来自 MK Sleep Cycle）：
    - >90 天 Events → 一行摘要
    - >90 天 P1 → 移到 reference/
    - >30 天 P2 → 压缩成结论
    - P0 / Agent Cases → 永不动
    """
    import re
    
    if memory_file is None:
        memory_file = Path(os.path.expandvars(
            r"~/.workbuddy/memory/MEMORY.md"))
    
    if not memory_file.exists():
        return {"error": f"MEMORY.md 不存在：{memory_file}"}
    
    try:
        with open(memory_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError as e:
        return {"error": f"无法读取：{e}"}
    
    sections = []
    current_section = None
    
    for line in content.split('\n'):
        if line.startswith('## '):
            if current_section:
                sections.append(current_section)
            current_section = {
                "title": line[3:].strip(),
                "content": [line],
                "date_tags": [],
                "line_count": 1,
            }
        elif current_section is not None:
            current_section["content"].append(line)
            current_section["line_count"] += 1
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', line)
            if date_match:
                current_section["date_tags"].append(date_match.group(1))
    
    if current_section:
        sections.append(current_section)
    
    suggestions = []
    stats = {"total_sections": len(sections), "p0_protected": 0, 
             "p1_suggest": 0, "p2_suggest": 0, "events_suggest": 0}
    
    now = datetime.now()
    p0_keywords = ["灵魂铁律", "会话强制加载", "操作权限", "Soli的开发手册",
                   "回答习惯", "存档规范", "随机数偏好"]
    
    for sec in sections:
        title = sec["title"]
        lines = sec["line_count"]
        dates = sec["date_tags"]
        if not dates:
            continue
        
        newest_date = max(dates)
        try:
            sec_date = datetime.strptime(newest_date, '%Y-%m-%d')
            age = (now - sec_date).days
        except ValueError:
            continue
        
        if any(kw in title for kw in p0_keywords):
            stats["p0_protected"] += 1
            continue
        
        if age > 30:
            stats["p2_suggest"] += 1
            suggestions.append({
                "section": title, "age_days": age, "lines": lines,
                "level": "P2", "action": "压缩为一句话结论",
            })
        
        if age > 90:
            stats["p1_suggest"] += 1
            suggestions.append({
                "section": title, "age_days": age, "lines": lines,
                "level": "P1", "action": "移至 reference/，MEMORY.md 只留索引",
            })
    
    for sec in sections:
        if "更新记录" in sec.get("title", ""):
            event_lines = [l for l in sec["content"] 
                          if l.strip().startswith(">") and re.search(r'\d{4}-\d{2}-\d{2}', l)]
            old_events = []
            for el in event_lines:
                dm = re.search(r'(\d{4}-\d{2}-\d{2})', el)
                if dm:
                    try:
                        if (now - datetime.strptime(dm.group(1), '%Y-%m-%d')).days > 90:
                            old_events.append(el.strip())
                    except ValueError:
                        pass
            if old_events:
                stats["events_suggest"] += 1
                suggestions.append({
                    "section": "更新记录", "age_days": ">90",
                    "lines": len(old_events), "level": "Events",
                    "action": f"压缩 {len(old_events)} 条为月度摘要",
                })
            break
    
    report = {
        "file": str(memory_file), "total_chars": len(content),
        "stats": stats, "suggestions": suggestions,
    }
    
    MEMORY_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "MEMORY"
    report_file = MEMORY_DATA_DIR / "janitor_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    report["_report_file"] = str(report_file)
    return report


def janitor_print_report(report: dict):
    """格式化打印 janitor 报告"""
    if "error" in report:
        print(f"\u274c {report['error']}")
        return
    
    s = report["stats"]
    print(f"MEMORY.md：{report['total_chars']} 字符，{s['total_sections']} 个章节")
    print(f"  P0 保护：{s['p0_protected']} | P2 压缩(>30天)：{s['p2_suggest']}")
    print(f"  P1 移出(>90天)：{s['p1_suggest']} | Events 折叠：{s['events_suggest']}")
    print()
    
    if not report["suggestions"]:
        print("\u2705 无需清理。")
    else:
        print("压缩建议：")
        for sug in report["suggestions"]:
            print(f"  [{sug['level']}] {sug['section']}")
            print(f"     {sug['age_days']}天前 · {sug['lines']}行 → {sug['action']}")
    print(f"\n报告已保存：{report.get('_report_file')}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python memory_v2.py save-fact <category> <key> <value> [source]")
        print("  python memory_v2.py load-fact <category> [key]")
        print("  python memory_v2.py save-episode <date> <json_file>")
        print("  python memory_v2.py auto-save [date]")
        print("  python memory_v2.py load-episode <date>")
        print("  python memory_v2.py search <keyword> [--all]")
        print("  python memory_v2.py search-timerange <start> <end>")
        print("  python memory_v2.py prepare-llm [date]")    # 生成 LLM 分析 prompt
        print("  python memory_v2.py apply-llm <results.json> [date]")  # 应用 LLM 分析结果
        print("  python memory_v2.py cleanup [--execute]")  # 清理过期记忆
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "save-fact":
        category = sys.argv[2]
        key = sys.argv[3]
        value = sys.argv[4]
        source = sys.argv[5] if len(sys.argv) > 5 else ""
        save_fact(category, key, value, source)
        print(f"✅ 已保存事实：{category}.{key}")
    
    elif command == "load-fact":
        category = sys.argv[2]
        key = sys.argv[3] if len(sys.argv) > 3 else None
        result = load_fact(category, key)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif command == "save-episode":
        date = sys.argv[2]
        json_file = sys.argv[3]
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        save_episode(date, data)
        print(f"✅ 已保存情景记忆：{date}")
    
    elif command == "auto-save":
        date = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y-%m-%d")
        # 读取当日工作日志作为会话历史
        log_path = f"~/.workbuddy/memory/{date}.md"
        history = []
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.strip().split('\n')
                for line in lines:
                    if line.strip():
                        history.append({"role": "assistant", "content": line.strip()})
            # 用日志行直接作为回退内容
            for i, msg in enumerate(history):
                if not msg["content"].startswith("#") and not msg["content"].startswith(">"):
                    pass
        except:
            pass
        auto_save_memory(history)
        print(f"✅ 已自动保存 {date} 的情景记忆（含情感时刻检测）")
    
    elif command == "load-episode":
        date = sys.argv[2]
        result = load_episode(date)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif command == "search":
        keyword = sys.argv[2]
        include_all = "--all" in sys.argv
        results = search_by_keyword(keyword, include_expired=include_all)
        print(f"找到 {len(results)} 条相关记忆{'（含已过期）' if include_all else ''}：")
        for r in results:
            print(f"  - {r}")

    elif command == "cleanup":
        execute = "--execute" in sys.argv
        stats = cleanup_expired_facts(dry_run=not execute)
        mode = "实际清理" if execute else "预览（dry-run）"
        print(f"[{mode}] 扫描 {stats['files_scanned']} 个事实文件")
        print(f"  已过期: {stats['expired_count']} 条")
        print(f"  仍有效: {stats['active_count']} 条")
    
    elif command == "prepare-llm":
        date = sys.argv[2] if len(sys.argv) > 2 else None
        prompt_data = prepare_llm_analysis(date)
        if "error" in prompt_data:
            print(f"❌ {prompt_data['error']}")
        else:
            print(f"✅ LLM 分析 prompt 已生成: {prompt_data.get('date')}")
            print(f"   候选片段: {len(prompt_data.get('candidates', []))}")
            print(f"   漏网检测: {len(prompt_data.get('missed_samples', []))}")
            print(f"   prompt 文件: MEMORY/llm_analysis_prompt.json")
            print(f"   可直接复制 prompt 字段发给 LLM 进行分析")
    
    elif command == "apply-llm":
        results_file = sys.argv[2]
        date = sys.argv[3] if len(sys.argv) > 3 else None
        with open(results_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        outcome = apply_llm_analysis(results, date)
        if "error" in outcome:
            print(f"❌ {outcome['error']}")
        else:
            stats = outcome['stats']
            print(f"✅ LLM 精筛完成:")
            print(f"   原始: {stats['original_count']} → 保留: {stats['kept']}")
            print(f"   剔除假阳性: {stats['discarded']} | 补回漏网: {stats['added']}")
            print(f"   最终: {stats['final_count']} 个情感时刻")
    
    elif command == "search-timerange":
        start = sys.argv[2]
        end = sys.argv[3]
        results = search_by_timerange(start, end)
        print(f"时间范围 {start} 到 {end} 找到 {len(results)} 条记忆：")
        for r in results:
            print(f"  - {r}")
    
    elif command == "janitor":
        dry = "--dry-run" in sys.argv
        report = janitor_generate_report()
        janitor_print_report(report)
        if dry:
            print("\n[dry-run] 以上为预览，未实际修改。")
    
    else:
        print(f"未知命令：{command}")
        sys.exit(1)
