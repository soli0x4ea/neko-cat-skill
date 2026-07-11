"""DLC Memory — dual-core linear memory + extended pipeline (v2.6.0).

Core (dual-core linear):
- ChatlogStore  — conversation memory (what was said, when)
- TimelineStore — time-aware memory (hourly snapshots)
- MemorySearch  — unified search across both stores

Extended pipeline (Soli 验证版 reference):
- Distiller     — daily chatlog distillation (structural summary, tone analysis)
- EpisodicStore — LLM episodic memory (narrative segments keyed by date)
- FactStore     — category-key-value fact storage with keyword/temporal indexing
- record_chat_complete — full pipeline: chatlog → timeline → distill → episodic save

Importer:
- import_chatlog / import_timeline — migration from Soli legacy format
"""

from .chatlog import ChatlogStore, record_chat, record_chat_complete
from .timeline import TimelineStore
from .search import MemorySearch
from .importer import import_chatlog, import_timeline
from .distill import Distiller
from .episodic import EpisodicStore
from .facts import FactStore

__all__ = [
    # Core
    "ChatlogStore",
    "record_chat",
    "record_chat_complete",
    "TimelineStore",
    "MemorySearch",
    # Extended
    "Distiller",
    "EpisodicStore",
    "FactStore",
    # Importer
    "import_chatlog",
    "import_timeline",
]
