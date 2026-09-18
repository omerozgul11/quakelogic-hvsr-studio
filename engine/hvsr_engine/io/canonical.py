"""Canonical in-memory and on-disk representation of a three-component recording.

The on-disk format is a NumPy ``.npz`` archive with keys ``n``, ``e``, ``z`` (float64,
equal length) and ``meta`` (a JSON string). See docs/architecture.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from ..version import ENGINE_VERSION

TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
COMPONENTS = ("n", "e", "z")


def format_time(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(TIME_FORMAT)


def parse_time(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class Recording:
    n: np.ndarray
    e: np.ndarray
    z: np.ndarray
    fs: float
    start_time: str = "1970-01-01T00:00:00.000000Z"
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        self.n = np.asarray(self.n, dtype=np.float64)
        self.e = np.asarray(self.e, dtype=np.float64)
        self.z = np.asarray(self.z, dtype=np.float64)
        self.fs = float(self.fs)
        if self.meta is None:
            self.meta = {}

    @property
    def n_samples(self) -> int:
        return int(len(self.z))

    @property
    def duration_s(self) -> float:
        return self.n_samples / self.fs if self.fs > 0 else 0.0

    @property
    def dt(self) -> float:
        return 1.0 / self.fs

    def times(self) -> np.ndarray:
        return np.arange(self.n_samples, dtype=np.float64) / self.fs

    def component(self, name: str) -> np.ndarray:
        return getattr(self, name)

    def components(self) -> dict:
        return {"n": self.n, "e": self.e, "z": self.z}

    def copy(self) -> "Recording":
        return Recording(self.n.copy(), self.e.copy(), self.z.copy(), self.fs, self.start_time,
                         json.loads(json.dumps(self.meta)))

    def start_datetime(self) -> datetime:
        return parse_time(self.start_time)

    def end_time(self) -> str:
        return format_time(self.start_datetime() + timedelta(seconds=max(self.n_samples - 1, 0) / self.fs))

    def base_meta(self) -> dict:
        meta = dict(self.meta)
        meta.update({
            "fs": self.fs,
            "start_time": self.start_time,
            "end_time": self.end_time(),
            "n_samples": self.n_samples,
            "duration_s": self.duration_s,
            "engine_version": ENGINE_VERSION,
        })
        meta.setdefault("units", "counts")
        meta.setdefault("unit_kind", "raw")
        meta.setdefault("channels", {"n": "N", "e": "E", "z": "Z"})
        meta.setdefault("station", "")
        meta.setdefault("network", "")
        meta.setdefault("location", "")
        meta.setdefault("orientation_deg", 0.0)
        meta.setdefault("is_synthetic", False)
        return meta


def save_recording(rec: Recording, path: str | Path) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = rec.base_meta()
    np.savez_compressed(path, n=rec.n, e=rec.e, z=rec.z, meta=json.dumps(meta))
    return meta


def load_recording(path: str | Path) -> Recording:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Recording file not found: {path}")
    with np.load(path, allow_pickle=False) as data:
        meta = json.loads(str(data["meta"]))
        rec = Recording(data["n"], data["e"], data["z"], float(meta["fs"]), meta["start_time"], meta)
    return rec
