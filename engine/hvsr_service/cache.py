"""Small LRU cache of loaded recordings keyed by (path, mtime, size)."""

from __future__ import annotations

import os
import threading
from collections import OrderedDict


class RecordingCache:
    def __init__(self, max_entries: int = 8):
        self.max_entries = max_entries
        self._items: OrderedDict[tuple, object] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _key(path: str) -> tuple:
        st = os.stat(path)
        return (os.path.abspath(path), st.st_mtime_ns, st.st_size)

    def load(self, path: str):
        if not path or not os.path.isfile(path):
            raise FileNotFoundError(f"Recording file not found: {path}")
        key = self._key(path)
        with self._lock:
            rec = self._items.get(key)
            if rec is not None:
                self._items.move_to_end(key)
                return rec
        from hvsr_engine.io.canonical import load_recording

        rec = load_recording(path)
        with self._lock:
            self._items[key] = rec
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)
        return rec

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        return len(self._items)
