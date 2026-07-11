"""DLC Memory — Distiller: daily chatlog summary (v2.6.0 extended).

Reads ChatlogStore JSONL → generates daily_distill/YYYY-MM-DD.json.
Produces structural metadata only — no fact extraction (that's facts.py).

Soli 验证版参考: chatlog.py _distill_today() + cmd_distill()
"""

import json
import os
import re
from datetime import datetime


class Distiller:
    """Daily chatlog distillation — structural summary without specific facts.

    Generates:
        - time_range (first→last message)
        - total_messages / turns
        - user_snippets (deduplicated first-60-char keys, max 20)
        - top_tones ([emoji/tag] patterns from user messages, max 8)
        - message_style (short/medium/long breakdown)
        - identity_anchor (first assistant message's opening)
    """

    def __init__(self, chatlog_dir: str, distill_dir: str):
        self.chatlog_dir = os.path.abspath(chatlog_dir)
        self.distill_dir = os.path.abspath(distill_dir)
        os.makedirs(self.distill_dir, exist_ok=True)

    # ── core ─────────────────────────────────────────────────

    def distill_day(self, date_str: str = None) -> dict | None:
        """Distill a single day's chatlog into a structural summary.

        Args:
            date_str: "YYYY-MM-DD" — if None, use today.

        Returns:
            dict with keys: date, time_range, total_messages, turns,
            user_snippets, top_tones, message_style, identity_anchor.
            None if no records exist.
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        chatlog_path = os.path.join(self.chatlog_dir, f"{date_str}.jsonl")
        if not os.path.isfile(chatlog_path):
            return None

        records = []
        try:
            with open(chatlog_path, "r", encoding="utf-8") as f:
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

        # Time range
        first_ts = records[0].get("ts", 0)
        last_ts = records[-1].get("ts", 0)
        time_range = ""
        if first_ts and last_ts:
            t1 = datetime.fromtimestamp(first_ts).strftime("%H:%M") if isinstance(first_ts, (int, float)) else "?"
            t2 = datetime.fromtimestamp(last_ts).strftime("%H:%M") if isinstance(last_ts, (int, float)) else "?"
            time_range = f"{t1} ~ {t2}"

        # Role stats
        user_msgs = [r for r in records if r.get("role") == "user"]
        asst_msgs = [r for r in records if r.get("role") == "assistant"]

        # User message snippets (dedup by first 60 chars, max 20)
        seen = set()
        user_snippets = []
        for r in user_msgs:
            content = r.get("content", "").strip()
            key = content[:60]
            if key and key not in seen:
                seen.add(key)
                snippet = content[:80].replace("\n", " ")
                user_snippets.append(snippet)
                if len(user_snippets) >= 20:
                    break

        # Tone tags — extract [xxx] patterns from user messages
        tone_pattern = re.compile(r'\[([^\]]+)\]')
        tone_counts = {}
        for r in user_msgs:
            content = r.get("content", "")
            for tag in tone_pattern.findall(content):
                if len(tag) <= 8 and not tag.startswith("http"):
                    tone_counts[tag] = tone_counts.get(tag, 0) + 1

        top_tones = dict(sorted(tone_counts.items(), key=lambda x: -x[1])[:8])

        # Message length characteristics
        user_lens = [len(r.get("content", "")) for r in user_msgs]
        short_msgs = sum(1 for l in user_lens if l <= 30)
        medium_msgs = sum(1 for l in user_lens if 30 < l <= 200)
        long_msgs = sum(1 for l in user_lens if l > 200)

        # Identity anchor — first 120 chars of first assistant message
        identity_anchor = ""
        if asst_msgs:
            first_asst = asst_msgs[0].get("content", "").strip()
            identity_anchor = first_asst[:120].replace("\n", " ")

        return {
            "date": date_str,
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

    def save_distill(self, date_str: str = None) -> str | None:
        """Distill and save to daily_distill/YYYY-MM-DD.json.

        Returns the file path if saved, None if nothing to distill.
        """
        data = self.distill_day(date_str)
        if data is None:
            return None

        d = data["date"]
        out_path = os.path.join(self.distill_dir, f"{d}.json")
        os.makedirs(self.distill_dir, exist_ok=True)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return out_path

    # ── query ────────────────────────────────────────────────

    def load_distill(self, date_str: str) -> dict | None:
        """Load a previously saved daily distill file."""
        fpath = os.path.join(self.distill_dir, f"{date_str}.json")
        if not os.path.isfile(fpath):
            return None
        with open(fpath, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_distills(self) -> list[str]:
        """List all dates that have distill files."""
        if not os.path.isdir(self.distill_dir):
            return []
        dates = []
        for fname in sorted(os.listdir(self.distill_dir)):
            if fname.endswith(".json") and not fname.startswith("."):
                dates.append(fname.replace(".json", ""))
        return dates

    def recent_summaries(self, n: int = 7) -> list[dict]:
        """Return the N most recent daily distill summaries."""
        dates = self.list_distills()
        results = []
        for d in dates[-n:]:
            summary = self.load_distill(d)
            if summary:
                results.append({
                    "date": d,
                    "turns": summary.get("turns", 0),
                    "top_tones": summary.get("top_tones", {}),
                    "time_range": summary.get("time_range", ""),
                })
        return results
