"""DLC Memory — EpisodicStore: LLM-generated episodic memory (v2.6.0 extended).

Stores episodic memory segments (LLM-generated narrative chunks) keyed by date.
Each episode file contains:
    - date / message_count / time_range
    - segments[] with time + title + summary + tags
    - day_summary (LLM-generated 2-3 sentence daily recap)

Soli 验证版参考: memory_v2.py save_episode/load_episode + episodes_llm/ format
"""

import json
import os
from datetime import datetime


class EpisodicStore:
    """LLM episodic memory — narrative segments keyed by date.

    File layout:
        <root_dir>/YYYY-MM-DD.json

    Format (aligned with Soli episodes_llm):
        {
          "date": "2026-07-11",
          "message_count": 150,
          "time_range": "00:05 ~ 23:58",
          "segments": [
            {
              "time": "上午",
              "title": "系统抢修",
              "summary": "凌晨代理502导致chatlog中断...",
              "tags": ["修复", "自动化"],
              "msg_count": 45
            }
          ],
          "day_summary": "今日共N段叙事。上午抢修自动化集群..."
        }
    """

    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        os.makedirs(self.root_dir, exist_ok=True)

    # ── file paths ───────────────────────────────────────────

    def _episode_file(self, date_str: str) -> str:
        return os.path.join(self.root_dir, f"{date_str}.json")

    # ── save ─────────────────────────────────────────────────

    def save(self, episode_data: dict, date_str: str = None) -> str:
        """Save an episodic memory file.

        Args:
            episode_data: dict with date, message_count, time_range,
                         segments[], day_summary.
            date_str: override date (if episode_data has no 'date' key).

        Returns:
            File path of saved episode.
        """
        d = episode_data.get("date") or date_str or datetime.now().strftime("%Y-%m-%d")
        episode_data["date"] = d

        os.makedirs(self.root_dir, exist_ok=True)
        fpath = self._episode_file(d)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(episode_data, f, ensure_ascii=False, indent=2)

        return fpath

    def update_segments(self, date_str: str, new_segments: list[dict],
                        day_summary: str = None) -> str:
        """Append or merge new segments into an existing episode file.

        Segments with duplicate titles are merged (latter overwrites former).
        """
        existing = self.load(date_str) or {
            "date": date_str,
            "message_count": 0,
            "time_range": "",
            "segments": [],
            "day_summary": "",
        }

        # Merge segments by title
        title_map = {s["title"]: s for s in existing["segments"]}
        for ns in new_segments:
            title_map[ns["title"]] = ns

        existing["segments"] = sorted(
            title_map.values(),
            key=lambda s: s.get("time", ""),
        )

        if day_summary:
            existing["day_summary"] = day_summary

        # Recalculate message_count if segments have msg_count
        total_msgs = sum(s.get("msg_count", 0) for s in existing["segments"])
        if total_msgs > 0:
            existing["message_count"] = total_msgs

        return self.save(existing)

    # ── load ─────────────────────────────────────────────────

    def load(self, date_str: str) -> dict | None:
        """Load episodic memory for a specific date."""
        fpath = self._episode_file(date_str)
        if not os.path.isfile(fpath):
            return None
        with open(fpath, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_range(self, start: str, end: str) -> list[dict]:
        """Load episodes in date range [start, end] (inclusive)."""
        from datetime import date, timedelta
        results = []
        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
        current = s
        while current <= e:
            ep = self.load(current.isoformat())
            if ep:
                results.append(ep)
            current += timedelta(days=1)
        return results

    def recent(self, n: int = 7) -> list[dict]:
        """Return N most recent episode files."""
        if not os.path.isdir(self.root_dir):
            return []
        files = sorted([
            f for f in os.listdir(self.root_dir)
            if f.endswith(".json") and not f.startswith(".")
        ])
        results = []
        for f in files[-n:]:
            ep = self.load(f.replace(".json", ""))
            if ep:
                results.append(ep)
        return results

    # ── query ────────────────────────────────────────────────

    def list_dates(self) -> list[str]:
        """List all dates with episode files."""
        if not os.path.isdir(self.root_dir):
            return []
        return sorted([
            f.replace(".json", "")
            for f in os.listdir(self.root_dir)
            if f.endswith(".json") and not f.startswith(".")
        ])

    def missing_dates(self, distill_dates: list[str]) -> list[str]:
        """Find dates with distill but no episode (needs LLM generation)."""
        episode_dates = set(self.list_dates())
        today = datetime.now().strftime("%Y-%m-%d")
        return [
            d for d in distill_dates
            if d not in episode_dates and d != today
        ]

    def search_segments(self, keyword: str, max_results: int = 20) -> list[dict]:
        """Search across all episode segments for a keyword."""
        results = []
        kw = keyword.lower()
        for ep in self.recent(90):  # up to ~3 months
            for seg in ep.get("segments", []):
                text = json.dumps(seg, ensure_ascii=False).lower()
                if kw in text:
                    results.append({"date": ep["date"], **seg})
                    if len(results) >= max_results:
                        return results
        return results

    # ── stats ────────────────────────────────────────────────

    def stats(self) -> dict:
        """Aggregate stats across all episodes."""
        dates = self.list_dates()
        total_segments = 0
        total_messages = 0
        for d in dates:
            ep = self.load(d)
            if ep:
                total_segments += len(ep.get("segments", []))
                total_messages += ep.get("message_count", 0)
        return {
            "total_days": len(dates),
            "total_segments": total_segments,
            "total_messages": total_messages,
            "span_start": dates[0] if dates else None,
            "span_end": dates[-1] if dates else None,
        }
