"""File inspection: format detection, delimiter/header guessing, MiniSEED trace listing."""
from __future__ import annotations

import csv
import hashlib
import io
import re
from pathlib import Path

import numpy as np

COMMENT_PREFIXES = ("#", "%", "//", "!", ";;")
DELIMITERS = [",", "\t", ";", "|"]
NUMBER_RE = re.compile(r"^[+-]?(\d+([.,]\d*)?|[.,]\d+)([eE][+-]?\d+)?$")
RATE_RE = re.compile(r"(sampl\w*[\s_-]*(rate|freq\w*)|fs|frequency)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(hz)?", re.I)
DT_RE = re.compile(r"\b(dt|delta|sample[\s_-]*interval)\s*[:=]?\s*([0-9]*\.?[0-9]+(?:[eE][-+]?\d+)?)\s*(s|sec)?\b", re.I)


def sha256_of(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_mseed(path: str | Path) -> bool:
    try:
        from obspy.io.mseed.core import _is_mseed
        return bool(_is_mseed(str(path)))
    except Exception:
        return False


def _decode(raw: bytes) -> tuple[str, str]:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace"), "latin-1"


def _is_number(tok: str, decimal: str = ".") -> bool:
    tok = tok.strip()
    if decimal == ",":
        tok = tok.replace(",", ".")
    return bool(NUMBER_RE.match(tok)) and not ("," in tok and decimal == ".")


def split_line(line: str, delimiter: str) -> list[str]:
    if delimiter == "whitespace":
        return line.strip().split()
    return [c.strip() for c in line.rstrip("\r\n").split(delimiter)]


def _numeric_fraction(rows: list[list[str]]) -> float:
    tokens = [t for r in rows for t in r if t != ""]
    if not tokens:
        return 0.0
    ok = sum(1 for t in tokens if NUMBER_RE.match(t.strip()) or _looks_datetime(t))
    return ok / len(tokens)


def detect_delimiter(lines: list[str]) -> str:
    """Pick the delimiter that splits the sample lines into a consistent number of
    numeric (or datetime) tokens. Decimal commas therefore do not fool the detector."""
    sample = [ln for ln in lines if ln.strip()]
    if not sample:
        return "whitespace"
    candidates = [d for d in DELIMITERS if all(d in ln for ln in sample)]
    best, best_score = "whitespace", -1.0
    for d in candidates + ["whitespace"]:
        rows = [split_line(ln, d) for ln in sample]
        ncols = {len(r) for r in rows}
        if d != "whitespace" and min(ncols) < 2:
            continue
        consistency = 10.0 if len(ncols) == 1 else (5.0 if len(ncols) == 2 else 0.0)
        score = 100.0 * _numeric_fraction(rows) + consistency + 0.1 * max(ncols)
        if score > best_score:
            best, best_score = d, score
    return best


def detect_decimal(rows: list[list[str]], delimiter: str) -> str:
    if delimiter == ",":
        return "."
    tokens = [t for r in rows for t in r]
    has_comma = sum(1 for t in tokens if re.match(r"^[+-]?\d+,\d+$", t.strip()))
    has_dot = sum(1 for t in tokens if re.match(r"^[+-]?\d*\.\d+", t.strip()))
    return "," if has_comma > has_dot else "."


def parse_datetimes(values, fmt: str | None = None):
    """Parse a list of timestamp strings to a tz-aware (UTC) pandas DatetimeIndex.

    Without an explicit format, ISO-8601 (with or without fractional seconds / zone) is
    tried first, then pandas' per-element inference."""
    import pandas as pd
    if fmt:
        return pd.to_datetime(values, format=fmt, utc=True)
    try:
        return pd.to_datetime(values, format="ISO8601", utc=True)
    except (ValueError, TypeError):
        return pd.to_datetime(values, format="mixed", utc=True)


def _looks_datetime(tok: str) -> bool:
    tok = tok.strip()
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$", tok)
                or re.match(r"^\d{2}/\d{2}/\d{4}[ T]\d{2}:\d{2}", tok))


def inspect_ascii(path: Path, max_lines: int = 400) -> dict:
    size = path.stat().st_size
    with open(path, "rb") as fh:
        raw = fh.read(min(size, 512 * 1024))
    text, encoding = _decode(raw)
    all_lines = text.splitlines()
    if size > len(raw):
        all_lines = all_lines[:-1]  # last line may be truncated
    lines = all_lines[:max_lines]
    comment_prefix = None
    rate_hint = None
    header_comment_lines = 0
    for ln in lines:
        s = ln.strip()
        if not s:
            header_comment_lines += 1
            continue
        pref = next((p for p in COMMENT_PREFIXES if s.startswith(p)), None)
        if pref:
            comment_prefix = comment_prefix or pref
            header_comment_lines += 1
            m = RATE_RE.search(s)
            if m and rate_hint is None:
                rate_hint = float(m.group(3))
            m2 = DT_RE.search(s)
            if m2 and rate_hint is None:
                dt = float(m2.group(2))
                if dt > 0:
                    rate_hint = 1.0 / dt
            continue
        break
    body = [ln for ln in lines if ln.strip() and not (comment_prefix and ln.strip().startswith(comment_prefix))]
    delimiter = detect_delimiter(body[min(len(body) - 1, 5):] or body)
    rows = [split_line(ln, delimiter) for ln in body]
    decimal = detect_decimal(rows[2:60], delimiter)
    # header rows = leading non-numeric rows (after comments)
    header_rows = 0
    for r in rows:
        numeric = [t for t in r if t]
        if numeric and all(_is_number(t, decimal) or _looks_datetime(t) for t in numeric):
            break
        header_rows += 1
    header = rows[header_rows - 1] if header_rows else None
    data_rows = rows[header_rows:]
    n_cols = max((len(r) for r in data_rows[:50]), default=0)
    columns = []
    for c in range(n_cols):
        vals = [r[c] for r in data_rows[:50] if len(r) > c]
        numeric = bool(vals) and all(_is_number(v, decimal) for v in vals)
        is_dt = bool(vals) and all(_looks_datetime(v) for v in vals)
        name = header[c] if header and len(header) > c and header[c] else f"column_{c + 1}"
        columns.append({"index": c, "name": name, "numeric": numeric, "datetime": is_dt, "sample": vals[:5]})
    time_guess = {"index": None, "kind": None, "sample_rate_estimate": None}
    for col in columns:
        vals = [r[col["index"]] for r in data_rows[:200] if len(r) > col["index"]]
        if col["datetime"] and len(vals) > 2:
            try:
                t = parse_datetimes(vals)
                dt = np.diff(t.values.astype("datetime64[ns]").astype(np.int64)) / 1e9
                med = float(np.median(dt))
                if med > 0:
                    time_guess = {"index": col["index"], "kind": "datetime", "sample_rate_estimate": round(1.0 / med, 6)}
                    break
            except Exception:
                pass
        elif col["numeric"] and len(vals) > 2:
            arr = np.array([float(v.replace(",", ".")) if decimal == "," else float(v) for v in vals])
            dt = np.diff(arr)
            if np.all(dt > 0):
                med = float(np.median(dt))
                if med > 0 and np.all(np.abs(dt - med) / med < 1e-3) and med < 10:
                    time_guess = {"index": col["index"], "kind": "seconds", "sample_rate_estimate": round(1.0 / med, 6)}
                    break
    avg_len = max(1.0, len(raw) / max(1, len(all_lines)))
    return {
        "encoding": encoding, "delimiter": delimiter, "decimal": decimal,
        "header_rows": header_rows, "comment_prefix": comment_prefix,
        "comment_lines": header_comment_lines,
        "columns": columns, "n_columns": n_cols,
        "n_rows_estimate": int(size / avg_len) - header_comment_lines - header_rows,
        "preview_lines": lines[:40],
        "preview_rows": data_rows[:20],
        "time_column_guess": time_guess,
        "sample_rate_hint": rate_hint,
    }


SEISMIC_SUFFIXES = {".gse", ".gse2", ".seg", ".sg2", ".seg2", ".sac", ".msd", ".mseed", ".miniseed", ".seed", ".sacb"}


def inspect_stream(st) -> dict:
    """Trace listing of an ObsPy Stream (MiniSEED, GSE2, SEG-2, SAC, ...)."""
    ids = sorted({tr.id for tr in st})
    traces = []
    for tid in ids:
        sub = st.select(id=tid)
        sub.sort(keys=["starttime"])
        gaps = sub.get_gaps()
        traces.append({
            "id": tid, "network": sub[0].stats.network, "station": sub[0].stats.station,
            "location": sub[0].stats.location, "channel": sub[0].stats.channel,
            "starttime": str(sub[0].stats.starttime), "endtime": str(sub[-1].stats.endtime),
            "sampling_rate": float(sub[0].stats.sampling_rate),
            "npts": int(sum(tr.stats.npts for tr in sub)), "segments": len(sub),
            "has_gaps": bool(gaps) or len(sub) > 1,
            "gaps": [{"start": str(g[4]), "end": str(g[5]), "seconds": float(g[6])} for g in gaps][:20],
            "sampling_rates": sorted({float(tr.stats.sampling_rate) for tr in sub}),
        })
    fmt = getattr(st[0].stats, "_format", None) if len(st) else None
    return {"traces": traces, "n_traces": len(st), "format_detected": fmt}


def inspect_mseed(path: Path) -> dict:
    import obspy
    return inspect_stream(obspy.read(str(path), format="MSEED"))


def inspect_seismic(path: Path) -> dict | None:
    """Try ObsPy's auto-detection for any other seismic format; None when nothing can read it."""
    try:
        import obspy
        st = obspy.read(str(path))
    except Exception:
        return None
    if len(st) == 0:
        return None
    return inspect_stream(st)


def inspect_saf(path: Path) -> dict:
    from .saf import component_columns, read_saf
    info = read_saf(path, header_only=True)
    cols = component_columns(info["channels"])
    sta = info.get("station") or "SAF"
    traces = []
    for idx, cid in enumerate(info["channels"]):
        traces.append({"id": f"SAF.{sta}..{cid or idx}", "network": "SAF", "station": sta, "location": "",
                       "channel": cid or str(idx), "starttime": info.get("start_time"), "endtime": None,
                       "sampling_rate": info["sample_rate"], "npts": info["n_samples_declared"], "segments": 1,
                       "has_gaps": False, "gaps": [], "sampling_rates": [info["sample_rate"]], "column": idx})
    return {"sample_rate": info["sample_rate"], "n_samples": info["n_samples_declared"], "start_time": info.get("start_time"),
            "channels": info["channels"], "station": sta, "units": info.get("units"), "header": info["header"],
            "comments": info["comments"], "columns": cols, "traces": traces}


def inspect_file(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")
    out = {"path": str(p), "name": p.name, "size_bytes": p.stat().st_size, "sha256": sha256_of(p), "format": "unknown",
           "ascii": None, "mseed": None, "saf": None}
    if is_mseed(p):
        out["format"] = "mseed"
        out["mseed"] = inspect_mseed(p)
        return out
    from .saf import is_saf
    if is_saf(p):
        out["format"] = "saf"
        out["saf"] = inspect_saf(p)
        out["mseed"] = {"traces": out["saf"]["traces"], "n_traces": 3, "format_detected": "SAF"}
        return out
    with open(p, "rb") as fh:
        head = fh.read(4096)
    binary = b"\x00" in head
    looks_seismic = binary or p.suffix.lower() in SEISMIC_SUFFIXES or b"WID2" in head or b"CHK2" in head
    if looks_seismic:
        seismic = inspect_seismic(p)
        if seismic:
            out["format"] = "seismic"
            out["mseed"] = seismic
            return out
    if binary:
        return out
    out["format"] = "ascii"
    out["ascii"] = inspect_ascii(p)
    return out
