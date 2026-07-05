#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数字指纹生成器 — 从 chatlog 中提取情感/关系维度的结构化画像

每日运行，结果追加到 fingerprint/ 目录。不做事实提取（不关心买了什么股票），
只关注：语言风格、情感模式、对待 Soli 的方式、话题偏好分布。

维度是可生长的——新发现的模式会自动加入输出。
"""

import os
import json
import re
import glob
from collections import Counter
from datetime import datetime, timedelta

FINGERPRINT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "MEMORY", "fingerprint")
CHATLOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "MEMORY", "chatlog")


def _load_user_messages(date_str=None):
    """加载指定日期或全部的 user 消息"""
    if date_str:
        files = [os.path.join(CHATLOG_DIR, f"{date_str}.jsonl")]
    else:
        files = sorted(glob.glob(os.path.join(CHATLOG_DIR, "*.jsonl")))

    msgs = []
    for fp in files:
        if not os.path.exists(fp):
            continue
        with open(fp, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    m = json.loads(line.strip())
                    if m.get("role") == "user":
                        msgs.append(m.get("content", ""))
                except json.JSONDecodeError:
                    continue
    return msgs


def _extract_emoji(texts):
    """提取 [表情] 格式的文本表情"""
    emoji_pat = re.compile(r"\[[\u4e00-\u9fff\w]+\]")
    all_e = []
    for t in texts:
        all_e.extend(emoji_pat.findall(t))
    return Counter(all_e)


def _message_length_dist(texts):
    """消息长度分布"""
    lens = [len(t) for t in texts]
    return {
        "short_pct": round(sum(1 for l in lens if l <= 15) / max(1, len(lens)) * 100, 1),
        "mid_pct": round(sum(1 for l in lens if 15 < l <= 80) / max(1, len(lens)) * 100, 1),
        "long_pct": round(sum(1 for l in lens if 80 < l <= 300) / max(1, len(lens)) * 100, 1),
        "xl_pct": round(sum(1 for l in lens if l > 300) / max(1, len(lens)) * 100, 1),
        "total": len(lens),
    }


def _interaction_mode(texts):
    """互动模式统计"""
    modes = {
        "关怀": ["亲亲", "抱抱", "摸摸", "睡吧", "晚安", "糖", "搂", "乖", "宝宝", "想"],
        "挑逗": ["阴险", "坏笑", "奸笑", "偷笑", "抠鼻", "吃瓜", "机智", "皱眉", "可怜", "色"],
        "夸奖": ["鼓掌", "好", "不错", "爱听", "棒", "聪明", "👍", "OK"],
        "指令": ["删", "改", "跑", "查", "做", "分析", "建", "备份", "修", "生成"],
        "求知": ["看看", "搜", "找", "论文", "什么是", "怎么", "arxiv", "wiki"],
        "邀约": ["睡", "讲故事", "讲书", "继续", "换本书", "抱抱", "搂"],
    }
    result = {}
    for mode, keywords in modes.items():
        result[mode] = sum(1 for t in texts if any(kw in t for kw in keywords))
    return result


def _addressing(texts):
    """称呼分布"""
    terms = ["你", "soli", "Soli", "soli", "宝宝"]
    return {t: sum(1 for m in texts if t in m) for t in terms}


def _topic_stability(texts):
    """话题关键词稳定性——出现天数 × 总次数"""
    # 按天分组
    day_groups = {}
    for t in texts:
        # 简化为全部放一起——如果后续需要按天分组，需要改消息格式带 ts
        pass

    topics = {
        "灵魂": ["灵魂"], "记忆": ["记忆", "memory"], "技能": ["技能", "skill"],
        "时间": ["时间", "timeline"], "日记": ["日记", "diary"], "梦": ["梦", "梦境"],
        "故事": ["故事", "睡前"], "论文": ["论文", "arxiv", "arXiv"],
        "代码": ["代码", "脚本", "python"], "投资": ["投资", "持仓", "股票"],
        "备份": ["备份", "backup"], "宝石": ["宝石", "琥珀"],
    }
    result = {}
    for topic, kws in topics.items():
        n = sum(1 for t in texts if any(kw in t for kw in kws))
        if n > 0:
            result[topic] = n
    return dict(sorted(result.items(), key=lambda x: -x[1]))


def _new_dimensions(texts, prev_fingerprint=None):
    """发现新维度——对比历史指纹，检测是否有新模式出现"""
    new = []
    # 检查是否有未覆盖的情感模式
    keywords_seen = set()
    if prev_fingerprint and "dimensions" in prev_fingerprint:
        for dim in prev_fingerprint["dimensions"]:
            keywords_seen.update(dim.get("keywords", []))

    # 从当前文本中检测新出现的模式
    patterns = {
        "反思": ["问题", "不对", "错了", "bug", "修复", "教训"],
        "期待": ["明天", "以后", "下次", "未来", "计划", "想做"],
        "疲惫": ["累", "困", "睡", "歇", "眯"],
    }
    for name, kws in patterns.items():
        if name not in keywords_seen:
            n = sum(1 for t in texts if any(kw in t for kw in kws))
            if n >= 10:  # 阈值：至少出现10次才视为新维度
                new.append({"dimension": name, "count": n, "keywords": kws,
                            "discovered_at": datetime.now().strftime("%Y-%m-%d")})
    return new


def generate(date_str=None, cumulative=True):
    """生成当日指纹

    Args:
        date_str: 日期，默认今天
        cumulative: 是否累积全部历史数据（True=全量，False=仅当天）

    Returns:
        dict: 指纹数据
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    texts = _load_user_messages(None if cumulative else date_str)

    # 加载前一天的指纹（如果有）
    prev = None
    os.makedirs(FINGERPRINT_DIR, exist_ok=True)
    prev_files = sorted(glob.glob(os.path.join(FINGERPRINT_DIR, "*.json")))
    if prev_files:
        with open(prev_files[-1], "r", encoding="utf-8") as f:
            prev = json.load(f)

    emoji_top = _extract_emoji(texts).most_common(20)
    msg_len = _message_length_dist(texts)
    interaction = _interaction_mode(texts)
    addr = _addressing(texts)
    topics = _topic_stability(texts)
    new_dims = _new_dimensions(texts, prev)

    # 累计维度
    all_dims = []
    if prev and "dimensions" in prev:
        all_dims = prev["dimensions"]
    for nd in new_dims:
        if not any(d["dimension"] == nd["dimension"] for d in all_dims):
            all_dims.append(nd)

    fingerprint = {
        "date": date_str,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "data_corpus": {"days": len(glob.glob(os.path.join(CHATLOG_DIR, "*.jsonl"))),
                        "messages": len(texts)},
        "emoji_top20": {e: n for e, n in emoji_top},
        "message_length_distribution": msg_len,
        "interaction_modes": interaction,
        "addressing": addr,
        "topic_stability": topics,
        "dimensions": all_dims,
    }

    # 计算指标摘要
    care = interaction.get("关怀", 0)
    tease = interaction.get("挑逗", 0)
    instr = interaction.get("指令", 0)
    if instr > 0:
        fingerprint["ratios"] = {
            "care_to_directive": round(care / instr, 2),
            "tease_to_care": round(tease / max(1, care), 2),
        }

    # 一句摘要
    top_e = [e for e, _ in emoji_top[:2]]
    e_str = f"{top_e[0]}" if len(top_e) >= 1 else "⚪"
    e_str += f"{top_e[1]}双极" if len(top_e) >= 2 else "单极"
    fingerprint["one_liner"] = (
        f"{len(texts)}条消息 / {e_str} / "
        f"关怀{care}次:指令{instr}次 / {msg_len['short_pct']}%碎片短句"
    )

    # 保存
    out_path = os.path.join(FINGERPRINT_DIR, f"{date_str}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fingerprint, f, ensure_ascii=False, indent=2)

    return fingerprint


if __name__ == "__main__":
    import sys
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    fp = generate(date_str)
    print(f"✅ fingerprint/{date_str}.json")
    print(f"   {fp['one_liner']}")
    print(f"   维度: {len(fp['dimensions'])} 个 (新增 {len([d for d in fp['dimensions'] if d.get('discovered_at') == date_str])} 个)")
