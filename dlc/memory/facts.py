"""DLC Memory — FactStore: structured factual memory (v2.6.0 extended).

Category-based fact storage with keyword indexing and temporal tracking.
Each fact has: category / key / value / source (date|chatlog) / expires_at.

Soli 验证版参考: memory_v2.py save_fact/load_fact/load_all_facts/search_by_keyword
"""

import json
import os
from datetime import datetime, timedelta


class FactStore:
    """Category-key-value fact storage with search and expiry.

    Directory layout:
        <root_dir>/facts/
            <category>/
                <key>.json

    Index files:
        <root_dir>/_keyword_index.json  — keyword → [file_paths]
        <root_dir>/_temporal_index.json — date → [file_paths]
        <root_dir>/_master_index.json   — {categories: {keys: file_paths}}
    """

    DEFAULT_TTL_DAYS = 60  # facts expire after 60 days by default

    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        self.facts_dir = os.path.join(self.root_dir, "facts")
        os.makedirs(self.facts_dir, exist_ok=True)
        self._load_indexes()

    # ── indexes ──────────────────────────────────────────────

    def _keyword_index_path(self) -> str:
        return os.path.join(self.root_dir, "_keyword_index.json")

    def _temporal_index_path(self) -> str:
        return os.path.join(self.root_dir, "_temporal_index.json")

    def _master_index_path(self) -> str:
        return os.path.join(self.root_dir, "_master_index.json")

    def _load_indexes(self):
        self.keyword_index = self._load_json(self._keyword_index_path()) or {}
        self.temporal_index = self._load_json(self._temporal_index_path()) or {}
        self.master_index = self._load_json(self._master_index_path()) or {}

    def _load_json(self, path: str) -> dict | None:
        if not os.path.isfile(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_json(self, path: str, data: dict):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_indexes(self):
        self._save_json(self._keyword_index_path(), self.keyword_index)
        self._save_json(self._temporal_index_path(), self.temporal_index)
        self._save_json(self._master_index_path(), self.master_index)

    # ── fact path ────────────────────────────────────────────

    def _fact_path(self, category: str, key: str) -> str:
        # Sanitize: replace path-unfriendly chars
        safe_cat = category.replace("/", "_").replace("\\", "_").strip()
        safe_key = key.replace("/", "_").replace("\\", "_").strip()
        d = os.path.join(self.facts_dir, safe_cat)
        return os.path.join(d, f"{safe_key}.json")

    # ── save / load ──────────────────────────────────────────

    def save(self, category: str, key: str, value,
             source: str = "", ttl_days: int = None) -> str:
        """Save a structured fact.

        Args:
            category: fact domain (e.g., "preference", "decision", "discovery")
            key: unique key within category
            value: the fact data (string, dict, list — anything JSON-serializable)
            source: where this fact came from (e.g., "2026-07-11|chatlog")
            ttl_days: days until expiry. None = DEFAULT_TTL_DAYS.

        Returns:
            File path of saved fact.
        """
        ttl = ttl_days if ttl_days is not None else self.DEFAULT_TTL_DAYS
        expires_at = (datetime.now() + timedelta(days=ttl)).isoformat()[:19]

        fact = {
            "category": category,
            "key": key,
            "value": value,
            "source": source,
            "created_at": datetime.now().isoformat()[:19],
            "expires_at": expires_at,
        }

        fpath = self._fact_path(category, key)
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        self._save_json(fpath, fact)

        # Update indexes
        self._update_keyword_index(category, key, fpath, value)
        self._update_temporal_index(source, fpath)
        self._update_master_index(category, key, fpath)
        self._save_indexes()

        return fpath

    def load(self, category: str, key: str = None) -> dict | None:
        """Load a fact. If key is None, return all facts in the category."""
        if key:
            fpath = self._fact_path(category, key)
            if not os.path.isfile(fpath):
                return None
            return self._load_json(fpath)

        # Load all in category
        cat_dir = os.path.join(self.facts_dir, category.replace("/", "_"))
        if not os.path.isdir(cat_dir):
            return {}
        result = {}
        for fname in os.listdir(cat_dir):
            if fname.endswith(".json"):
                fact = self._load_json(os.path.join(cat_dir, fname))
                if fact and not self._is_expired(fact):
                    result[fact["key"]] = fact["value"]
        return result

    def load_all(self) -> dict:
        """Load all non-expired facts, organized by category."""
        if not os.path.isdir(self.facts_dir):
            return {}
        result = {}
        for cat_name in os.listdir(self.facts_dir):
            cat_dir = os.path.join(self.facts_dir, cat_name)
            if not os.path.isdir(cat_dir):
                continue
            cat_facts = {}
            for fname in os.listdir(cat_dir):
                if fname.endswith(".json"):
                    fact = self._load_json(os.path.join(cat_dir, fname))
                    if fact and not self._is_expired(fact):
                        cat_facts[fact["key"]] = fact["value"]
            if cat_facts:
                result[cat_name] = cat_facts
        return result

    # ── expiry ───────────────────────────────────────────────

    def _is_expired(self, fact: dict) -> bool:
        expires = fact.get("expires_at", "")
        if not expires:
            return False
        try:
            exp_dt = datetime.fromisoformat(expires)
            return datetime.now() > exp_dt
        except (ValueError, TypeError):
            return False

    def cleanup_expired(self, dry_run: bool = True) -> dict:
        """Remove expired facts. Returns {deleted_count, freed_paths}."""
        deleted = 0
        paths = []
        for cat_name in os.listdir(self.facts_dir):
            cat_dir = os.path.join(self.facts_dir, cat_name)
            if not os.path.isdir(cat_dir):
                continue
            for fname in os.listdir(cat_dir):
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(cat_dir, fname)
                fact = self._load_json(fpath)
                if fact and self._is_expired(fact):
                    paths.append(fpath)
                    deleted += 1
                    if not dry_run:
                        os.unlink(fpath)

        if not dry_run and deleted > 0:
            self._rebuild_indexes()

        return {"deleted_count": deleted, "freed_paths": paths}

    # ── index helpers ────────────────────────────────────────

    def _update_keyword_index(self, category: str, key: str, fpath: str, value):
        """Extract keywords from value and map to file paths."""
        text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        # Simple: use category and key as keywords, plus split words > 2 chars
        keywords = {category, key}
        for word in text.split():
            word = word.strip().strip(",.;:!?\"'[]{}()")
            if len(word) > 2 and not word.startswith("http"):
                keywords.add(word)

        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in self.keyword_index:
                self.keyword_index[kw_lower] = []
            if fpath not in self.keyword_index[kw_lower]:
                self.keyword_index[kw_lower].append(fpath)

    def _update_temporal_index(self, source: str, fpath: str):
        """Map date strings from source to file paths."""
        # source format: "2026-07-11|chatlog" or just "2026-07-11"
        date_str = source.split("|")[0] if "|" in source else source[:10]
        if len(date_str) == 10:
            if date_str not in self.temporal_index:
                self.temporal_index[date_str] = []
            if fpath not in self.temporal_index[date_str]:
                self.temporal_index[date_str].append(fpath)

    def _update_master_index(self, category: str, key: str, fpath: str):
        if category not in self.master_index:
            self.master_index[category] = {}
        self.master_index[category][key] = fpath

    def _rebuild_indexes(self):
        """Full index rebuild after cleanup."""
        self.keyword_index = {}
        self.temporal_index = {}
        self.master_index = {}
        for cat_name in os.listdir(self.facts_dir):
            cat_dir = os.path.join(self.facts_dir, cat_name)
            if not os.path.isdir(cat_dir):
                continue
            for fname in os.listdir(cat_dir):
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(cat_dir, fname)
                fact = self._load_json(fpath)
                if fact and not self._is_expired(fact):
                    self._update_keyword_index(
                        fact["category"], fact["key"], fpath, fact["value"])
                    self._update_temporal_index(
                        fact.get("source", ""), fpath)
                    self._update_master_index(
                        fact["category"], fact["key"], fpath)
        self._save_indexes()

    # ── search ───────────────────────────────────────────────

    def search(self, keyword: str, max_results: int = 20) -> list[dict]:
        """Keyword search across all non-expired facts."""
        kw = keyword.lower()
        matched_paths = set()

        # Direct keyword index match
        if kw in self.keyword_index:
            for p in self.keyword_index[kw]:
                matched_paths.add(p)

        # Substring match against all keys
        for idx_kw, paths in self.keyword_index.items():
            if kw in idx_kw and kw != idx_kw:
                for p in paths:
                    matched_paths.add(p)

        results = []
        for fpath in list(matched_paths)[:max_results * 2]:
            fact = self._load_json(fpath)
            if fact and not self._is_expired(fact):
                results.append(fact)
                if len(results) >= max_results:
                    break

        return results

    def search_by_timerange(self, start: str, end: str) -> list[dict]:
        """Find facts from a date range."""
        results = []
        from datetime import date, timedelta
        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
        current = s
        while current <= e:
            d = current.isoformat()
            if d in self.temporal_index:
                for fpath in self.temporal_index[d]:
                    fact = self._load_json(fpath)
                    if fact and not self._is_expired(fact):
                        results.append(fact)
            current += timedelta(days=1)
        return results
