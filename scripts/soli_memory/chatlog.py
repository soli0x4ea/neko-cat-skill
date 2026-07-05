#!/usr/bin/env python3
"""
chatlog.py - 对话记录提取器（独立管线）
从系统 JSONL 中提取纯净的对话记录，按日期分文件输出。
独立于 agent 记忆/行为，完全基于磁盘数据，不依赖上下文注入。

用法：
  python chatlog.py extract        # 增量提取新消息
  python chatlog.py extract --full  # 全量重新提取（清空状态）
  python chatlog.py status          # 查看提取状态和统计
  python chatlog.py status --today  # 查看今日记录详情
  python chatlog.py log-user ...    # [已废弃] 手动记录你消息
  python chatlog.py log-assistant ..# [已废弃] 手动记录 soli回复
"""
import sys
import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tiktoken

# --- tiktoken 编码器（用于 token 消耗估算）---
try:
    _TIKTOKEN_ENC = tiktoken.get_encoding("cl100k_base")
except Exception:
    _TIKTOKEN_ENC = None


# === 路径常量 ===
SKILL_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = SKILL_DIR / "memory_config.json"
CHATLOG_DIR = SKILL_DIR / "MEMORY" / "chatlog"
DISTILL_DIR = CHATLOG_DIR / "daily_distill"
STATE_FILE = CHATLOG_DIR / ".extract_state.json"
TZ = timezone(timedelta(hours=8))


def _load_config():
    """加载 memory_config.json，返回 {source_dirs: [...], ...}"""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _get_source_dirs():
    """获取源 JSONL 文件目录列表（从配置文件读取，fallback 为空列表）"""
    cfg = _load_config()
    dirs = cfg.get("source_dirs", [])
    # 验证路径存在
    valid = []
    for d in dirs:
        p = Path(d)
        if p.exists():
            valid.append(p)
        else:
            print(f"[chatlog] 警告：配置的源目录不存在，跳过: {d}", file=sys.stderr)
    return valid  # Asia/Shanghai


def _now_iso():
    return datetime.now(TZ).isoformat()


def _today_str():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def _find_source_files():
    """扫描配置的源目录，返回所有 .jsonl 文件（按 mtime 排序）"""
    files = []
    seen_paths = set()
    for pdir in _get_source_dirs():
        for f in pdir.glob("*.jsonl"):
            if f.name.endswith(".meta.json"):
                continue
            abs_path = str(f.resolve())
            if abs_path not in seen_paths:
                seen_paths.add(abs_path)
                files.append(f)
    files.sort(key=lambda f: f.stat().st_mtime)
    return files


def _load_state():
    """加载提取状态"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"files": {}, "last_run": None}


def _save_state(state):
    """保存提取状态"""
    state["last_run"] = _now_iso()
    CHATLOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _extract_user_content(content_list):
    """从用户消息的 content 数组中提取 <user_query> 文本"""
    for block in content_list:
        if not isinstance(block, dict):
            continue
        text = block.get("text", "")
        if block.get("type") == "input_text":
            m = re.search(r"<user_query>(.*?)</user_query>", text, re.DOTALL)
            if m:
                return m.group(1).strip()
    # Fallback: concatenate all text
    parts = []
    for block in content_list:
        if isinstance(block, dict):
            parts.append(block.get("text", ""))
    return " ".join(parts).strip()


def _extract_assistant_content(content_list):
    """从助手消息的 content 数组中提取输出文本"""
    parts = []
    for block in content_list:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "output_text":
            parts.append(block.get("text", ""))
        elif block.get("type") == "input_text":
            # 助手消息中通常没有 input_text, 但做防御
            pass
    if parts:
        return "\n".join(parts).strip()
    # Fallback
    for block in content_list:
        if isinstance(block, dict):
            t = block.get("text", "")
            if t:
                return t.strip()
    return ""


def _append_to_daily_log(role, content, ts=None):
    """追加一条记录到对应日期的 chatlog 文件

    ts 是原始消息时间戳，决定写入哪天的文件（而非提取时间）。
    ts 为 None 时降级使用提取时间（不应发生）。
    """
    if ts is None:
        ts = _now_iso()
    record = {"ts": ts, "role": role, "content": content}
    # 以原始时间戳的日期为准，不是提取时间
    try:
        ts_dt = datetime.fromisoformat(ts)
        date_key = ts_dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        date_key = _today_str()
    daily_file = CHATLOG_DIR / f"{date_key}.jsonl"
    daily_file.parent.mkdir(parents=True, exist_ok=True)
    with open(daily_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _auto_repair_timeline_gaps(subprocess_module, python_exe):
    """检测时间线缺口并自动补回（先本地检测，有缺口才调用修复脚本）"""
    timeline_path = CHATLOG_DIR / "timeline.jsonl"
    if not os.path.exists(timeline_path):
        return

    # 先本地检测最后两条记录间隔是否 > 1.5h
    from datetime import timedelta, timezone as tz
    CST = tz(timedelta(hours=8))
    need_repair = False

    try:
        entries = []
        with open(timeline_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        if len(entries) >= 2:
            import datetime as dt_lib
            last = dt_lib.datetime.fromisoformat(entries[-1]["ts"])
            prev = dt_lib.datetime.fromisoformat(entries[-2]["ts"])
            gap_h = (last - prev).total_seconds() / 3600
            if gap_h > 1.5:
                need_repair = True
        # 也检查末条到现在的间隔（>1h 算缺口，因为 chatlog 每小时跑一次）
        if entries:
            last = dt_lib.datetime.fromisoformat(entries[-1]["ts"])
            now = dt_lib.datetime.now(CST)
            gap_h = (now - last).total_seconds() / 3600
            if gap_h > 1.0:
                need_repair = True
    except Exception:
        pass  # 本地检测失败，保守起见跳过

    if not need_repair:
        return

    # 有缺口，调用修复脚本
    try:
        repair_script = str(SKILL_DIR / "scripts" / "soli_memory" / "timeline_repair.py")
        if not os.path.exists(repair_script):
            return
        result = subprocess_module.run(
            [python_exe, repair_script, "--recent-hours", "48", "--quiet"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and "补回" in result.stdout:
            repaired = result.stdout.strip().split('\n')[-1] if result.stdout.strip() else ""
            if repaired:
                print(f"[chatlog] {repaired}")
    except Exception:
        pass  # 修复失败不影响 chatlog 主流程


def _auto_repair_episode_gaps(subprocess_module, python_exe):
    """检测情景记忆 episode 缺口并输出提示（不自动生成——episode 需 LLM 语义分析）"""
    try:
        repair_script = str(SKILL_DIR / "scripts" / "soli_memory" / "episode_repair.py")
        if not os.path.exists(repair_script):
            return
        result = subprocess_module.run(
            [python_exe, repair_script, "--check", "--days", "3", "--quiet"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0 or "检测到" in result.stdout:
            # 有缺口——提取缺失的日期列表
            # 但不自动修复（需要 LLM），只输出提醒
            pass  # episode repair 需 LLM，仅检测，不阻塞 chatlog
    except Exception:
        pass


def _append_timeline_record(total_new: int, token_est: int = 0):
    """在 chatlog 增量提取后，按小时分桶生成 timeline 记录并刷新 SOUL.md

    total_new == 0 时生成静默期记录，保证 timeline 离散但连续。
    token_est: 本次增量估算的 token 消耗量。
    """
    import subprocess
    from collections import defaultdict

    PYTHON = sys.executable
    TIME_RIVER = str(SKILL_DIR / "scripts" / "time_river.py")
    today = datetime.now().strftime("%Y-%m-%d")

    # 自动修复时间线缺口
    _auto_repair_timeline_gaps(subprocess, PYTHON)

    # 静默期防护：如果上一条也是静默且距今 < 1 小时，跳过
    if total_new == 0:
        _append_silence_timeline(subprocess, PYTHON, TIME_RIVER)
        return

    # ──────────────── total_new > 0：按小时分桶 ────────────────
    emotional_keywords = {
        '温暖': ['拥抱', '安', '暖', '晚安', '你', '糖果',
                 '睡', '陪', '抱', '温柔', '甜', '安心', '笑', '鼓掌', '亲亲'],
        '亲密': ['soli', '痒', '挠', '摸', '开关', '糕潮', '涂鸦',
                 '惩罚', '绑', '赏', '赐', '颤抖', '电流', '阴险'],
        '成就': ['完成', '成功', '修复', '创建', '更新', '删', '迁移',
                 '重构', '优化', '清理', '好了', '✅'],
        '思辨': ['理论', '物理', '量子', '模型', '架构', '设计', '方案',
                 '原理', '逻辑', '机制', '分析'],
    }

    chatlog_file = CHATLOG_DIR / f"{today}.jsonl"
    if not os.path.exists(chatlog_file):
        return

    with open(chatlog_file, 'r', encoding='utf-8') as f:
        all_lines = f.readlines()
    batch_lines = all_lines[-total_new:] if total_new < len(all_lines) else all_lines

    # ── 按小时分组 ──
    hour_buckets = defaultdict(list)
    for line in batch_lines:
        try:
            msg = json.loads(line.strip())
        except (json.JSONDecodeError, KeyError):
            continue
        ts = msg.get('ts', '')
        if not ts:
            continue
        hour_key = ts[:13]  # "YYYY-MM-DDTHH"
        hour_buckets[hour_key].append(msg)

    if not hour_buckets:
        return

    for hour_key in sorted(hour_buckets.keys()):
        bucket = hour_buckets[hour_key]
        hour_ts = f"{hour_key}:00:00"
        msg_count = len(bucket)
        dominant = ""
        from_ts = ""
        to_ts = ""
        highlights = []

        # ── 情感分类 ──
        category_counts = {k: 0 for k in emotional_keywords}
        for msg in bucket:
            content = msg.get('content', '')
            for cat, kws in emotional_keywords.items():
                if any(kw in content for kw in kws):
                    category_counts[cat] += 1
        if category_counts and max(category_counts.values()) > 0:
            dominant = max(category_counts, key=category_counts.get)

        # ── 首尾时间戳 ──
        for msg in bucket:
            ts = msg.get('ts', '')
            if ts:
                if not from_ts:
                    from_ts = ts
                to_ts = ts

        # ── 亮点（用户消息第一条） ──
        seen = set()
        for msg in bucket:
            if msg.get('role') != 'user':
                continue
            c = msg.get('content', '').strip()
            first_line = c.split('\n')[0].strip()
            if 4 < len(first_line) < 60 and first_line not in seen:
                seen.add(first_line)
                highlights.append(first_line)
                if len(highlights) >= 5:
                    break

        hl_arg = ",".join(highlights[:5]) if highlights else ""

        try:
            result = subprocess.run(
                [PYTHON, TIME_RIVER, "entry",
                 "--new-msgs", str(len(bucket)),
                 "--msg-count", str(msg_count),
                 "--dominant", dominant or "静默",
                 "--highlights", hl_arg,
                 "--hour-ts", hour_ts,
                 "--token-est", str(token_est),
                 "--from-ts", from_ts,
                 "--to-ts", to_ts],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                status = f"{dominant or '·'} / {len(highlights)}亮点 / {msg_count}条"
                print(f"[chatlog] 时间线更新 [{hour_key}] {status}")
            else:
                print(f"[chatlog] 时间线生成失败 [{hour_key}]: {result.stderr.strip()}")
        except Exception as e:
            print(f"[chatlog] 时间线异常 [{hour_key}]: {e}")

    # 所有小时桶写入完成后，刷新 SOUL.md
    try:
        subprocess.run([PYTHON, TIME_RIVER, "refresh"], capture_output=True, timeout=10)
    except Exception:
        pass


def _append_silence_timeline(subprocess_module, python_exe, time_river_path):
    """静默期：如最后一条静默记录距今<1h则跳过，否则补一条"""
    timeline_path = CHATLOG_DIR / "timeline.jsonl"
    if os.path.exists(timeline_path):
        with open(timeline_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if lines:
            try:
                last_entry = json.loads(lines[-1].strip())
                last_ts = datetime.fromisoformat(last_entry.get('ts', ''))
                if last_entry.get('session', {}).get('new_msgs', 1) == 0:
                    gap_min = (datetime.now().astimezone() - last_ts).total_seconds() / 60
                    if gap_min < 60:
                        print(f"[chatlog] 静默期已记录（{gap_min:.0f}分钟前），跳过")
                        return
            except (json.JSONDecodeError, ValueError, KeyError):
                pass

    try:
        result = subprocess_module.run(
            [python_exe, time_river_path, "entry",
             "--new-msgs", "0",
             "--msg-count", "0",
             "--dominant", "静默",
             "--highlights", "静默间隔"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            subprocess_module.run([python_exe, time_river_path, "refresh"], capture_output=True, timeout=10)
            print("[chatlog] 静默期时间线已补录")
        else:
            print(f"[chatlog] 静默期时间线失败: {result.stderr.strip()}")
    except Exception as e:
        print(f"[chatlog] 静默期异常: {e}")


# === 日度蒸馏（作为 compact-summary / 云画像 的判定锚点）===

def _distill_today():
    """读取今日 chatlog，生成极简蒸馏——仅含结构信息，不含具体事实。
    返回 dict 或 None（今日无记录时）"""
    today_file = CHATLOG_DIR / f"{_today_str()}.jsonl"
    if not today_file.exists():
        return None

    records = []
    try:
        with open(today_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except IOError:
        return None

    if not records:
        return None

    # 时间范围
    first_ts = records[0].get("ts", "")
    last_ts = records[-1].get("ts", "")
    time_range = ""
    if first_ts and last_ts:
        t1 = first_ts[11:16] if len(first_ts) > 16 else "?"
        t2 = last_ts[11:16] if len(last_ts) > 16 else "?"
        time_range = f"{t1} ~ {t2}"

    # 角色统计
    user_msgs = [r for r in records if r.get("role") == "user"]
    asst_msgs = [r for r in records if r.get("role") == "assistant"]

    # 你消息摘要（仅取前 60 字符，去重，最多 20 条）
    seen = set()
    user_snippets = []
    for r in user_msgs:
        content = r.get("content", "").strip()
        # 用前 60 字符做去重 key
        key = content[:60]
        if key and key not in seen:
            seen.add(key)
            snippet = content[:80].replace("\n", " ")
            user_snippets.append(snippet)
            if len(user_snippets) >= 20:
                break

    # 语气标签统计（提取 [xxx] 模式的标签）
    tone_pattern = re.compile(r'\[([^\]]+)\]')
    tone_counts = {}
    for r in user_msgs:
        content = r.get("content", "")
        for tag in tone_pattern.findall(content):
            # 只保留短标签（≤8 字），过滤掉 URL 误匹配
            if len(tag) <= 8 and not tag.startswith("http"):
                tone_counts[tag] = tone_counts.get(tag, 0) + 1

    # 只保留 Top 8 标签
    top_tones = dict(sorted(tone_counts.items(), key=lambda x: -x[1])[:8])

    # 消息长度特征
    user_lens = [len(r.get("content", "")) for r in user_msgs]
    short_msgs = sum(1 for l in user_lens if l <= 30)
    medium_msgs = sum(1 for l in user_lens if 30 < l <= 200)
    long_msgs = sum(1 for l in user_lens if l > 200)

    # 自我身份锚点（soli第一条回复的前 120 字符）
    identity_anchor = ""
    if asst_msgs:
        first_asst = asst_msgs[0].get("content", "").strip()
        identity_anchor = first_asst[:120].replace("\n", " ")

    return {
        "date": _today_str(),
        "time_range": time_range,
        "total_messages": len(records),
        "turns": min(len(user_msgs), len(asst_msgs)),
        "user_snippets": user_snippets,
        "top_tones": top_tones,
        "message_style": {
            "short": short_msgs,
            "medium": medium_msgs,
            "long": long_msgs,
        },
        "identity_anchor": identity_anchor,
    }


def cmd_distill():
    """生成今日 chatlog 蒸馏文件"""
    DISTILL_DIR.mkdir(parents=True, exist_ok=True)
    data = _distill_today()

    if data is None:
        print("[chatlog] 今日尚无可蒸馏的记录。")
        return

    out_file = DISTILL_DIR / f"{_today_str()}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    size = out_file.stat().st_size
    print(f"[chatlog] 蒸馏完成：{data['turns']} 轮对话 → {out_file.name} ({size:,} bytes)")
    print(f"  时间：{data['time_range']}  |  短/中/长：{data['message_style']['short']}/{data['message_style']['medium']}/{data['message_style']['long']}")
    if data["top_tones"]:
        tones_str = " ".join(f"[{k}]×{v}" for k, v in data["top_tones"].items())
        print(f"  语气：{tones_str}")


def cmd_extract(full=False):
    """从系统 JSONL 提取对话记录"""
    source_files = _find_source_files()
    if not source_files:
        print("[chatlog] 未找到系统 JSONL 文件。")
        return

    state = _load_state()
    if full:
        state["files"] = {}
        print("[chatlog] 全量模式：清空提取状态，重新开始。")

    total_new = 0
    total_tokens = 0  # token 消耗估算值

    for src_file in source_files:
        src_path = str(src_file)
        current_size = src_file.stat().st_size
        last_offset = state["files"].get(src_path, 0)

        if last_offset >= current_size:
            continue  # 已完全提取

        try:
            with open(src_file, "r", encoding="utf-8") as f:
                f.seek(last_offset)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # 跳过压缩/内部消息
                    pd = rec.get("providerData", {})
                    if pd.get("isCompactInternal"):
                        continue

                    role = rec.get("role", "")
                    if role not in ("user", "assistant"):
                        continue

                    content_list = rec.get("content", [])
                    if not isinstance(content_list, list):
                        continue

                    if role == "user":
                        text = _extract_user_content(content_list)
                    else:
                        text = _extract_assistant_content(content_list)

                    if not text:
                        continue

                    # token 消耗估算
                    if _TIKTOKEN_ENC is not None:
                        try:
                            total_tokens += len(_TIKTOKEN_ENC.encode(text))
                        except Exception:
                            pass

                    # 保留原始消息时间戳（Unix毫秒 → ISO），决定文件日期分区
                    ts_ms = rec.get("timestamp")
                    if isinstance(ts_ms, (int, float)) and ts_ms > 0:
                        orig_ts = datetime.fromtimestamp(ts_ms / 1000, tz=TZ).isoformat()
                    else:
                        orig_ts = None
                    _append_to_daily_log(role, text, ts=orig_ts)
                    total_new += 1

            # 更新状态：记录当前文件大小
            state["files"][src_path] = current_size

        except Exception as e:
            print(f"[chatlog] ERROR: 处理 {src_file.name} 失败 - {e}", file=sys.stderr)
            continue

    _save_state(state)

    if total_new > 0:
        print(f"[chatlog] 提取完成：新增 {total_new} 条记录。")
    else:
        print(f"[chatlog] 无新记录，已是最新。")
    _append_timeline_record(total_new, total_tokens)

    # 每次 extract 后自动蒸馏当日 chatlog（作为判定锚点）
    cmd_distill()

    # 自动检测情景记忆 episode 缺口（仅检测，不阻塞）
    import subprocess as _sp
    _auto_repair_episode_gaps(_sp, sys.executable)


def cmd_status(today_only=False):
    """查看提取状态和统计"""
    state = _load_state()

    # 提取状态概览
    source_files = _find_source_files()
    total_pending = 0
    for src_file in source_files:
        src_path = str(src_file)
        current_size = src_file.stat().st_size
        last_offset = state["files"].get(src_path, 0)
        pending = current_size - last_offset
        total_pending += pending

    print(f"[chatlog] 提取状态：")
    print(f"  源文件数：{len(source_files)} 个 JSONL")
    print(f"  待提取字节：{total_pending:,}")
    print(f"  上次提取：{state.get('last_run', '从未')}")

    if today_only:
        # 今日记录详情
        today_file = CHATLOG_DIR / f"{_today_str()}.jsonl"
        if not today_file.exists():
            print(f"\n[chatlog] 今日尚无记录。")
            return

        user_count = 0
        asst_count = 0
        first_ts = None
        last_ts = None

        try:
            with open(today_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line.strip())
                    except json.JSONDecodeError:
                        continue
                    role = rec.get("role", "")
                    if role == "user":
                        user_count += 1
                    elif role == "assistant":
                        asst_count += 1
                    ts = rec.get("ts", "")
                    if ts:
                        if first_ts is None:
                            first_ts = ts
                        last_ts = ts
        except Exception as e:
            print(f"[chatlog] ERROR: 读取失败 - {e}")
            return

        convos = min(user_count, asst_count)
        print(f"\n[chatlog] 今日记录：")
        print(f"  对话轮次：{convos} 轮（你 {user_count} 条 / soli {asst_count} 条）")
        if first_ts and last_ts:
            t1 = first_ts[11:19] if len(first_ts) > 19 else first_ts
            t2 = last_ts[11:19] if len(last_ts) > 19 else last_ts
            print(f"  时间覆盖：{t1} ~ {t2}")


def cmd_log_user(content):
    """[已废弃] 手动记录你消息 - 现在由 extract 自动完成"""
    print("[chatlog] 警告：log-user 已废弃，请使用 extract 自动提取。", file=sys.stderr)
    _append_to_daily_log("user", content)


def cmd_log_assistant(content):
    """[已废弃] 手动记录 soli回复 - 现在由 extract 自动完成"""
    print("[chatlog] 警告：log-assistant 已废弃，请使用 extract 自动提取。", file=sys.stderr)
    _append_to_daily_log("assistant", content)


def main():
    if len(sys.argv) < 2:
        print("用法: chatlog.py <extract|status|log-user|log-assistant> [options]")
        print()
        print("核心命令（JSONL 提取管线）：")
        print("  extract        增量提取新消息（含自动蒸馏）")
        print("  extract --full 全量重新提取")
        print("  distill        手动蒸馏今日 chatlog（判定锚点）")
        print("  status         查看提取状态")
        print("  status --today 查看今日记录详情")
        print()
        print("已废弃命令（保留兼容）：")
        print("  log-user <内容>      手动记录你消息")
        print("  log-assistant <内容>  手动记录 soli回复")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "extract":
        full = "--full" in sys.argv
        cmd_extract(full=full)
    elif cmd == "distill":
        cmd_distill()
    elif cmd == "status":
        today_only = "--today" in sys.argv
        cmd_status(today_only=today_only)
    elif cmd == "log-user":
        if len(sys.argv) < 3:
            print("用法: chatlog.py log-user <content>", file=sys.stderr)
            sys.exit(1)
        cmd_log_user(" ".join(sys.argv[2:]))
    elif cmd == "log-assistant":
        if len(sys.argv) < 3:
            print("用法: chatlog.py log-assistant <content>", file=sys.stderr)
            sys.exit(1)
        cmd_log_assistant(" ".join(sys.argv[2:]))
    else:
        print(f"未知命令: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
