"""Import ASCII (TXT/CSV) and MiniSEED sources into a canonical recording, with validation.

The importer never interpolates gaps, resamples, rotates or invents components. The only
modification it performs is trimming the components to their common time overlap when
they start at different (whole-sample) times or have different lengths — and that is
reported as the warning ``trimmed_to_overlap``.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ..validation import check_regular_sampling, is_blocking, issue, validate_recording
from ..version import ENGINE_VERSION
from .canonical import Recording, format_time, parse_time, save_recording
from .inspect import parse_datetimes, sha256_of

COMPONENTS = ("n", "e", "z")


class _Component:
    def __init__(self, data: np.ndarray, fs: float | None, start: datetime | None, source: str):
        self.data = np.asarray(data, dtype=np.float64)
        self.fs = fs
        self.start = start
        self.source = source


# ---------------------------------------------------------------------------
# ASCII
# ---------------------------------------------------------------------------

def _read_ascii_table(path: str, ascii_cfg: dict) -> pd.DataFrame:
    delimiter = ascii_cfg.get("delimiter", ",")
    decimal = ascii_cfg.get("decimal", ".")
    header_rows = int(ascii_cfg.get("header_rows", 0) or 0)
    comment = ascii_cfg.get("comment_prefix")
    kwargs = dict(header=None, skiprows=None, dtype=str, engine="python", encoding_errors="replace",
                  skip_blank_lines=True)
    if delimiter == "whitespace":
        kwargs["sep"] = r"\s+"
    else:
        kwargs["sep"] = delimiter
    # read raw text, drop comment lines (any prefix length), then header rows
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        lines = fh.readlines()
    body = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if comment and s.startswith(comment):
            continue
        body.append(ln)
    body = body[header_rows:]
    if not body:
        raise ValueError("No data rows found after removing comments and header rows.")
    df = pd.read_csv(io.StringIO("".join(body)), **kwargs)
    return df


def _to_float(series: pd.Series, decimal: str) -> np.ndarray:
    s = series.astype(str).str.strip()
    if decimal == ",":
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce").to_numpy(dtype=np.float64)


def _clean_rate(fs):
    """Round a rate estimated from a time column to 9 significant digits (removes float noise)."""
    if fs is None:
        return None
    return float(f"{float(fs):.9g}")


def _time_from_table(df: pd.DataFrame, ascii_cfg: dict, issues: list, source: str):
    """Returns (fs, start_datetime or None)."""
    time_cfg = ascii_cfg.get("time") or {}
    mode = time_cfg.get("mode", "sample_rate")
    decimal = ascii_cfg.get("decimal", ".")
    if mode == "sample_rate":
        fs = time_cfg.get("sample_rate")
        if not fs or float(fs) <= 0:
            issues.append(issue("no_timing_information", "error",
                                f"{source}: no sample rate was given and no time column is defined. Enter the sample rate.",
                                {"source": source}))
            return None, None
        start = ascii_cfg.get("start_time")
        return float(fs), (parse_time(start) if start else None)
    col = time_cfg.get("column")
    if col is None or int(col) >= df.shape[1]:
        issues.append(issue("no_timing_information", "error", f"{source}: the time column index is missing or out of range.",
                            {"source": source}))
        return None, None
    col = int(col)
    if mode == "seconds_column":
        t = _to_float(df.iloc[:, col], decimal)
        if np.isnan(t).any():
            issues.append(issue("no_timing_information", "error", f"{source}: the time column contains non-numeric values."))
            return None, None
        fs, tissues = check_regular_sampling(t)
        fs = _clean_rate(fs)
        for it in tissues:
            it["details"]["source"] = source
        issues.extend(tissues)
        start_cfg = ascii_cfg.get("start_time")
        start = parse_time(start_cfg) if start_cfg else None
        if start is not None and len(t):
            from datetime import timedelta
            start = start + timedelta(seconds=float(t[0]))
        return fs, start
    if mode == "datetime_column":
        fmt = time_cfg.get("datetime_format") or None
        try:
            ts = pd.Series(parse_datetimes(df.iloc[:, col].astype(str).str.strip().tolist(), fmt))
        except Exception as exc:
            issues.append(issue("no_timing_information", "error", f"{source}: cannot parse the datetime column ({exc}).",
                                {"source": source}))
            return None, None
        if ts.isna().any():
            issues.append(issue("no_timing_information", "error", f"{source}: {int(ts.isna().sum())} unparsable timestamp(s)."))
            return None, None
        ns = ts.values.astype("datetime64[ns]").astype(np.int64)
        secs = (ns - ns[0]) / 1e9  # subtract in integer nanoseconds to keep sub-microsecond precision
        fs, tissues = check_regular_sampling(secs)
        for it in tissues:
            it["details"]["source"] = source
        issues.extend(tissues)
        if fs is not None:
            fs = _clean_rate(fs)
        return fs, ts.iloc[0].to_pydatetime()
    issues.append(issue("no_timing_information", "error", f"{source}: unknown time mode {mode!r}."))
    return None, None


def _import_ascii(request: dict, issues: list) -> dict[str, _Component]:
    ascii_cfg = request.get("ascii") or {}
    columns = ascii_cfg.get("columns") or {}
    decimal = ascii_cfg.get("decimal", ".")
    scale = float(ascii_cfg.get("scale_factor", 1.0) or 1.0)
    sources = request.get("sources") or []
    comps: dict[str, _Component] = {}
    tables: dict[str, tuple[pd.DataFrame, float | None, datetime | None]] = {}
    for src in sources:
        path = src["path"]
        role = src.get("role", "all")
        try:
            df = _read_ascii_table(path, ascii_cfg)
        except Exception as exc:
            issues.append(issue("parse_error", "error", f"Cannot parse {Path(path).name}: {exc}", {"path": path}))
            continue
        fs, start = _time_from_table(df, ascii_cfg, issues, Path(path).name)
        tables[role] = (df, fs, start)
        roles = COMPONENTS if role == "all" else (role,)
        for comp in roles:
            idx = columns.get(comp)
            if idx is None:
                continue
            idx = int(idx)
            if idx >= df.shape[1]:
                issues.append(issue("missing_component", "error",
                                    f"Column {idx + 1} for component {comp.upper()} does not exist in {Path(path).name} "
                                    f"({df.shape[1]} columns).", {"component": comp, "path": path}))
                continue
            data = _to_float(df.iloc[:, idx], decimal) * scale
            comps[comp] = _Component(data, fs, start, Path(path).name)
    for comp in COMPONENTS:
        if comp not in comps:
            issues.append(issue("missing_component", "error",
                                f"Component {comp.upper()} is not assigned to any column/file. All three components are required; "
                                "nothing is substituted.", {"component": comp}))
    return comps


# ---------------------------------------------------------------------------
# MiniSEED
# ---------------------------------------------------------------------------

def _import_mseed(request: dict, issues: list, fmt: str = "mseed") -> dict[str, _Component]:
    """MiniSEED (``fmt="mseed"``) or any ObsPy-readable seismic format (``fmt="seismic"``: GSE2, SEG-2, SAC, ...)."""
    import obspy
    cfg = request.get("mseed") or {}
    scale = float((request.get("ascii") or {}).get("scale_factor", 1.0) or cfg.get("scale_factor", 1.0) or 1.0)
    st = obspy.Stream()
    for src in request.get("sources") or []:
        try:
            st += obspy.read(src["path"], format="MSEED") if fmt == "mseed" else obspy.read(src["path"])
        except Exception as exc:
            label = "MiniSEED" if fmt == "mseed" else "a seismic data file"
            issues.append(issue("parse_error", "error", f"Cannot read {Path(src['path']).name} as {label}: {exc}"))
    comps: dict[str, _Component] = {}
    for comp in COMPONENTS:
        tid = cfg.get(comp)
        if not tid:
            issues.append(issue("missing_component", "error", f"No MiniSEED trace selected for component {comp.upper()}.",
                                {"component": comp}))
            continue
        sub = st.select(id=tid)
        if len(sub) == 0:
            issues.append(issue("missing_component", "error", f"Trace {tid} was not found in the selected files.",
                                {"component": comp, "trace_id": tid}))
            continue
        sub.sort(keys=["starttime"])
        rates = {float(tr.stats.sampling_rate) for tr in sub}
        if len(rates) > 1:
            issues.append(issue("sample_rate_mismatch", "error", f"Trace {tid} has segments with different sample rates {sorted(rates)}.",
                                {"component": comp, "rates": sorted(rates)}))
            continue
        if len(sub) > 1:
            gaps = sub.get_gaps()
            overlaps = [g for g in gaps if g[6] < 0]
            real_gaps = [g for g in gaps if g[6] > 0]
            code = "overlaps" if overlaps and not real_gaps else "gaps"
            issues.append(issue(code, "error",
                                f"Trace {tid} consists of {len(sub)} segments ({len(real_gaps)} gap(s), {len(overlaps)} overlap(s)). "
                                "Segments are never merged or interpolated; select a continuous segment or fix the source.",
                                {"component": comp, "segments": len(sub),
                                 "gaps": [{"start": str(g[4]), "end": str(g[5]), "seconds": float(g[6])} for g in gaps][:20]}))
            continue
        tr = sub[0]
        comps[comp] = _Component(np.asarray(tr.data, dtype=np.float64) * scale, float(tr.stats.sampling_rate),
                                 tr.stats.starttime.datetime.replace(tzinfo=timezone.utc), tid)
    return comps


# ---------------------------------------------------------------------------
# SESAME ASCII format
# ---------------------------------------------------------------------------

def _import_saf(request: dict, issues: list) -> dict[str, _Component]:
    from .saf import component_columns, read_saf
    cfg = request.get("saf") or {}
    scale = float(cfg.get("scale_factor", (request.get("ascii") or {}).get("scale_factor", 1.0)) or 1.0)
    comps: dict[str, _Component] = {}
    sources = request.get("sources") or []
    if not sources:
        return comps
    path = sources[0]["path"]
    try:
        info = read_saf(path)
    except Exception as exc:
        issues.append(issue("parse_error", "error", f"Cannot parse {Path(path).name} as SESAME ASCII (SAF): {exc}", {"path": path}))
        return comps
    fs = info["sample_rate"] or None
    if not fs:
        override = cfg.get("sample_rate")
        if override and float(override) > 0:
            fs = float(override)
        else:
            issues.append(issue("no_timing_information", "error", f"{Path(path).name}: SAMP_FREQ is missing from the SAF header.",
                                {"source": Path(path).name}))
            return comps
    cols = component_columns(info["channels"])
    for comp in COMPONENTS:
        idx = cfg.get(comp, cols.get(comp))
        if idx is None:
            issues.append(issue("missing_component", "error", f"Component {comp.upper()} could not be matched to a SAF channel "
                                f"(CH0_ID..CH2_ID = {info['channels']}).", {"component": comp}))
            continue
        idx = int(idx)
        if idx >= info["data"].shape[1]:
            issues.append(issue("missing_component", "error", f"SAF column {idx} does not exist.", {"component": comp}))
            continue
        start = parse_time(info["start_time"]) if info.get("start_time") else None
        comps[comp] = _Component(info["data"][:, idx] * scale, float(fs), start, Path(path).name)
    request.setdefault("_saf_info", {"station": info.get("station"), "units": info.get("units"), "channels": info["channels"]})
    if info["n_samples_declared"] and info["n_samples_declared"] != info["n_samples"]:
        issues.append(issue("length_mismatch", "info", f"SAF header declares NDAT = {info['n_samples_declared']} but the file holds "
                            f"{info['n_samples']} rows; the rows present are used.", {}))
    return comps


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------

def _align(comps: dict[str, _Component], issues: list) -> tuple[dict[str, np.ndarray], float, datetime | None, bool]:
    fs_values = {c.fs for c in comps.values() if c.fs}
    if len(fs_values) > 1:
        issues.append(issue("sample_rate_mismatch", "error",
                            f"The components have different sample rates: {sorted(fs_values)} Hz. Resample explicitly if intended.",
                            {"rates": {k: c.fs for k, c in comps.items()}}))
        return {}, 0.0, None, False
    fs = fs_values.pop() if fs_values else 0.0
    starts = {k: c.start for k, c in comps.items()}
    have_times = all(s is not None for s in starts.values())
    offsets = {k: 0 for k in comps}
    start = None
    assumed = False
    if have_times:
        t0 = min(starts.values())
        for k, s in starts.items():
            off = (s - t0).total_seconds() * fs
            if abs(off - round(off)) > 1e-3:
                issues.append(issue("time_misaligned", "error",
                                    f"Component {k.upper()} starts {off / fs:.6f} s after the earliest component, which is not a whole "
                                    "number of samples. Sub-sample shifts are never applied automatically.",
                                    {"component": k, "offset_s": off / fs}))
                return {}, fs, None, False
            offsets[k] = int(round(off))
        common_start_off = max(offsets.values())
        start = t0
        from datetime import timedelta
        start = t0 + timedelta(seconds=common_start_off / fs)
    else:
        any_start = next((s for s in starts.values() if s is not None), None)
        start = any_start
        if start is None:
            start = datetime(1970, 1, 1, tzinfo=timezone.utc)
            assumed = True
        common_start_off = 0
    # trim to common overlap
    ends = {k: offsets[k] + len(c.data) for k, c in comps.items()}
    common_end = min(ends.values())
    n_common = common_end - common_start_off
    if n_common < 2:
        issues.append(issue("time_misaligned", "error", "The components do not overlap in time.", {"offsets": offsets}))
        return {}, fs, None, False
    out = {}
    trimmed = {}
    for k, c in comps.items():
        i0 = common_start_off - offsets[k]
        out[k] = c.data[i0:i0 + n_common]
        removed = len(c.data) - n_common
        if removed:
            trimmed[k] = {"removed_samples": int(removed), "removed_start": int(i0), "removed_end": int(len(c.data) - i0 - n_common)}
    lengths = {len(c.data) for c in comps.values()}
    if len(lengths) > 1:
        issues.append(issue("length_mismatch", "info", f"Component lengths differ ({sorted(lengths)} samples).",
                            {"lengths": {k: len(c.data) for k, c in comps.items()}}))
    if trimmed:
        issues.append(issue("trimmed_to_overlap", "warning",
                            "Components were trimmed to their common time overlap "
                            f"({n_common} samples, {n_common / fs:.2f} s). Removed samples: "
                            + ", ".join(f"{k.upper()} {v['removed_samples']}" for k, v in trimmed.items()) + ".",
                            {"n_common": int(n_common), "trimmed": trimmed}))
    return out, fs, start, assumed


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def import_recording(request: dict) -> dict:
    issues: list[dict] = []
    fmt = request.get("format", "ascii")
    sources = request.get("sources") or []
    if not sources:
        issues.append(issue("missing_component", "error", "No source files were supplied."))
    if fmt == "ascii":
        comps = _import_ascii(request, issues)
    elif fmt in ("mseed", "seismic"):
        comps = _import_mseed(request, issues, fmt)
    elif fmt == "saf":
        comps = _import_saf(request, issues)
    else:
        issues.append(issue("parse_error", "error", f"Unknown format {fmt!r}."))
        comps = {}
    meta = None
    if not is_blocking(issues) and len(comps) == 3:
        arrays, fs, start, assumed = _align(comps, issues)
        if not is_blocking(issues) and arrays:
            metadata = request.get("metadata") or {}
            ascii_cfg = request.get("ascii") or {}
            saf_cfg = request.get("saf") or {}
            saf_info = request.get("_saf_info") or {}
            units = ascii_cfg.get("units") or (request.get("mseed") or {}).get("units") or saf_cfg.get("units") \
                or saf_info.get("units") or "counts"
            unit_kind = ascii_cfg.get("unit_kind") or (request.get("mseed") or {}).get("unit_kind") or saf_cfg.get("unit_kind") or "raw"
            if fmt in ("mseed", "seismic"):
                channels = {k: (request["mseed"].get(k) or "").split(".")[-1] for k in COMPONENTS}
                first = (request["mseed"].get("z") or "...").split(".")
                net, sta, loc = (first + ["", "", ""])[:3]
            elif fmt == "saf":
                ch = saf_info.get("channels") or ["V", "N", "E"]
                channels = {"z": ch[0] if len(ch) > 0 else "V", "n": ch[1] if len(ch) > 1 else "N", "e": ch[2] if len(ch) > 2 else "E"}
                net, sta, loc = "", saf_info.get("station") or "", ""
            else:
                channels = {"n": "N", "e": "E", "z": "Z"}
                net, sta, loc = "", "", ""
            rec = Recording(arrays["n"], arrays["e"], arrays["z"], fs, format_time(start), {
                "units": units, "unit_kind": unit_kind, "channels": channels,
                "station": metadata.get("station") or sta, "network": metadata.get("network") or net,
                "location": metadata.get("location") or loc,
                "orientation_deg": float(metadata.get("orientation_deg", 0.0) or 0.0),
                "is_synthetic": bool(metadata.get("is_synthetic", False)),
                "start_time_assumed": assumed,
                "source_files": [{"path": s["path"], "name": Path(s["path"]).name, "role": s.get("role", "all"),
                                  "sha256": sha256_of(s["path"]) if Path(s["path"]).exists() else None} for s in sources],
                "import_settings": {k: request.get(k) for k in ("format", "ascii", "mseed", "saf", "metadata")},
                "recording_id": request.get("recording_id"),
                "source_path": request.get("output_path"),
            })
            issues.extend(validate_recording(rec))
            if not is_blocking(issues):
                out_path = request.get("output_path")
                if out_path:
                    meta = save_recording(rec, out_path)
                else:
                    meta = rec.base_meta()
    ok = meta is not None and not is_blocking(issues)
    order = {"error": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda i: order.get(i["severity"], 3))
    return {"ok": ok, "meta": meta, "validation": {"blocking": is_blocking(issues), "issues": issues},
            "engine_version": ENGINE_VERSION}
