"""Professional PDF analysis report built with reportlab (platypus).

The report is generated entirely from the ``result.json`` dictionary plus a
``context`` dictionary supplied by the application layer (project, station,
recording, source files, processing steps, app version). It never touches the
network and uses only the fonts that ship with reportlab.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .figures import figure as render_figure

NAVY = colors.HexColor("#3a3c41")  # QuakeLogic charcoal (brand secondary)
LOGO_PATH = Path(__file__).with_name("assets") / "quakelogic-logo.png"
ORANGE = colors.HexColor("#F26522")
GREY = colors.HexColor("#5F6B7A")
LIGHT = colors.HexColor("#F1F3F6")
LINE = colors.HexColor("#D5D8DC")

COMPANY_LINE = ("QuakeLogic Inc. · 2008 Opportunity Dr., Suite 130, Roseville, CA 95678, USA · "
                "Phone +1 (916) 899-0391 · sales@quakelogic.net · products.quakelogic.net")
DISCLAIMER = (
    "This report was generated automatically by QuakeLogic HVSR Studio from the data, processing settings and "
    "window selection described above. The horizontal-to-vertical spectral ratio (HVSR) is an empirical, "
    "single-station method: its results depend on the quality of the recording, on ambient-vibration conditions "
    "at the time of measurement and on the processing choices recorded in this report. The H/V amplitude is a "
    "spectral ratio and must not be interpreted as a direct measurement of site amplification, and an H/V peak "
    "frequency does not determine a unique subsurface velocity profile. Interpretation for engineering, "
    "geotechnical or regulatory purposes must be performed by a qualified professional, who should verify the "
    "data, the processing settings and the reported quality indicators. QuakeLogic Inc. provides this software "
    "and the report as is, without warranty of any kind, and accepts no liability for decisions made on the "
    "basis of this report."
)
M_PER_FT = 0.3048
IN_PER_M = 39.37007874015748


def copyright_line(generated: str | None = None) -> str:
    year = (generated or "")[:4]
    if not (year.isdigit() and len(year) == 4):
        year = str(_dt.datetime.now(_dt.timezone.utc).year)
    return f"© {year} QuakeLogic Inc. All rights reserved."


def unit_system_label(system: str | None) -> str:
    return "US customary (SAE)" if system == "us" else "Metric (SI)"


def format_elevation(metres, system: str | None) -> str | None:
    """Elevation in the chosen unit system with the other system in parentheses."""
    try:
        m = float(metres)
    except (TypeError, ValueError):
        return None
    ft = m / M_PER_FT
    if system == "us":
        return f"{ft:,.1f} ft ({m:,.2f} m)"
    return f"{m:,.2f} m ({ft:,.1f} ft)"


def display_amplitude_unit(units: str | None, unit_kind: str | None, system: str | None) -> tuple[str, float]:
    """(label, factor) to show an SI amplitude unit in the chosen system; counts/unknown unchanged."""
    label = (units or "counts").strip() or "counts"
    if system != "us" or unit_kind not in ("velocity", "acceleration", "displacement"):
        return label, 1.0
    u = label.replace(" ", "").replace("²", "^2").replace("/s2", "/s^2")
    prefixes = {"": 1.0, "m": 1e-3, "c": 1e-2, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "n": 1e-9, "k": 1e3}
    import re as _re
    if u.lower() == "gal":
        return "in/s²", 1e-2 * IN_PER_M
    match = _re.fullmatch(r"([mcunkµμ]?)m(/s(\^2)?)?", u)
    if not match:
        return label, 1.0
    factor = prefixes.get(match.group(1) or "", 1.0) * IN_PER_M
    target = "in/s²" if match.group(3) else ("in/s" if match.group(2) else "in")
    return target, factor

PASS = colors.HexColor("#2E7D32")
FAIL = colors.HexColor("#C62828")

SESAME_CITATION = (
    "SESAME (2004). Guidelines for the implementation of the H/V spectral ratio technique on "
    "ambient vibrations: measurements, processing and interpretation. SESAME European research "
    "project, WP12 – Deliverable D23.12, European Commission – Research General Directorate, "
    "Project No. EVG1-CT-2000-00026 SESAME, December 2004."
)

DEFAULT_INTERPRETATION_NOTES = [
    "The H/V spectral ratio amplitude is not a direct measurement of site amplification.",
    "HVSR alone does not constrain a unique subsurface shear-wave velocity profile; any inversion "
    "requires independent constraints and explicit assumptions.",
    "Dispersion bands shown in this report are statistical dispersion measures of the window "
    "ensemble (standard deviation or percentiles), not confidence intervals.",
    "Peak frequency variability statistics describe the spread of window-level peaks; the bootstrap "
    "interval (when present) is a percentile interval of the resampled mean-curve peak.",
]


# --------------------------------------------------------------------------- helpers
def _fmt(v: Any, nd: int = 3) -> str:
    if v is None:
        return "–"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int,)) and not isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        if v != v:  # NaN
            return "–"
        if abs(v) >= 1e5 or (abs(v) < 1e-3 and v != 0):
            return f"{v:.3e}"
        return f"{v:.{nd}f}"
    if isinstance(v, (list, tuple)):
        return ", ".join(_fmt(x, nd) for x in v)
    if isinstance(v, dict):
        return "; ".join(f"{k}={_fmt(x, nd)}" for k, x in v.items())
    return str(v)


def _esc(s: Any) -> str:
    s = "" if s is None else str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    st = {
        "title": ParagraphStyle("qlTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=20,
                                leading=24, textColor=NAVY, alignment=TA_LEFT, spaceAfter=2),
        "subtitle": ParagraphStyle("qlSubtitle", parent=base["Normal"], fontName="Helvetica", fontSize=10,
                                   leading=13, textColor=GREY, spaceAfter=10),
        "h1": ParagraphStyle("qlH1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=13.5,
                             leading=17, textColor=NAVY, spaceBefore=12, spaceAfter=6),
        "h2": ParagraphStyle("qlH2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=10.5,
                             leading=13, textColor=NAVY, spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("qlBody", parent=base["Normal"], fontName="Helvetica", fontSize=9,
                               leading=12, textColor=colors.HexColor("#1F2933")),
        "small": ParagraphStyle("qlSmall", parent=base["Normal"], fontName="Helvetica", fontSize=7.5,
                                leading=9.5, textColor=GREY),
        "cell": ParagraphStyle("qlCell", parent=base["Normal"], fontName="Helvetica", fontSize=8,
                               leading=10, textColor=colors.HexColor("#1F2933")),
        "cellb": ParagraphStyle("qlCellB", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8,
                                leading=10, textColor=NAVY),
        "mono": ParagraphStyle("qlMono", parent=base["Normal"], fontName="Courier", fontSize=7.5,
                               leading=9.5, textColor=colors.HexColor("#1F2933")),
        "caption": ParagraphStyle("qlCaption", parent=base["Normal"], fontName="Helvetica-Oblique",
                                  fontSize=8, leading=10, textColor=GREY, spaceBefore=2, spaceAfter=8),
    }
    return st


def _table(rows: list[list[Any]], st: dict, col_widths=None, header: bool = True, zebra: bool = True,
           status_col: int | None = None) -> Table:
    data = []
    for i, row in enumerate(rows):
        cells = []
        for j, c in enumerate(row):
            if isinstance(c, Paragraph):
                cells.append(c)
            else:
                style = st["cellb"] if (header and i == 0) else st["cell"]
                cells.append(Paragraph(_esc(c), style))
        data.append(cells)
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0, hAlign="LEFT")
    ts = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        ts += [("BACKGROUND", (0, 0), (-1, 0), LIGHT), ("LINEBELOW", (0, 0), (-1, 0), 0.8, NAVY)]
    if zebra:
        for i in range(1 if header else 0, len(rows)):
            if (i - (1 if header else 0)) % 2 == 1:
                ts.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FAFBFC")))
    if status_col is not None:
        for i in range(1 if header else 0, len(rows)):
            val = str(rows[i][status_col]).lower()
            if val.startswith("pass"):
                ts.append(("TEXTCOLOR", (status_col, i), (status_col, i), PASS))
            elif val.startswith("fail"):
                ts.append(("TEXTCOLOR", (status_col, i), (status_col, i), FAIL))
    t.setStyle(TableStyle(ts))
    return t


def _kv_table(pairs: list[tuple[str, Any]], st: dict, widths=(1.9 * inch, 4.9 * inch)) -> Table:
    rows = [[Paragraph(_esc(k), st["cellb"]), Paragraph(_esc(_fmt(v)), st["cell"])] for k, v in pairs]
    t = Table(rows, colWidths=list(widths), hAlign="LEFT")
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    return t


def _config_hash(result: dict) -> str:
    payload = json.dumps(result.get("params") or {}, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


class _PageDecorator:
    def __init__(self, title: str, generated: str):
        self.title = title
        self.generated = generated

    def __call__(self, canvas, doc):
        canvas.saveState()
        w, h = letter
        # header
        if LOGO_PATH.exists():
            # Official wordmark (739 × 120 px) scaled to 1.6 in wide, baseline-aligned with the header text.
            canvas.drawImage(str(LOGO_PATH), 0.75 * inch, h - 0.62 * inch, width=1.6 * inch, height=0.26 * inch, mask="auto")
            canvas.setFillColor(NAVY)
            canvas.setFont("Helvetica-Bold", 9)
            canvas.drawString(0.75 * inch + 1.72 * inch, h - 0.55 * inch, "HVSR Studio")
        else:
            canvas.setFillColor(NAVY)
            canvas.setFont("Helvetica-Bold", 10)
            canvas.drawString(0.75 * inch, h - 0.55 * inch, "QuakeLogic HVSR Studio")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GREY)
        canvas.drawRightString(w - 0.75 * inch, h - 0.55 * inch, self.title[:90])
        canvas.setStrokeColor(ORANGE)
        canvas.setLineWidth(1.2)
        canvas.line(0.75 * inch, h - 0.65 * inch, w - 0.75 * inch, h - 0.65 * inch)
        # footer
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(0.75 * inch, 0.7 * inch, w - 0.75 * inch, 0.7 * inch)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GREY)
        canvas.drawString(0.75 * inch, 0.52 * inch,
                          f"{copyright_line(self.generated)}   ·   Generated {self.generated} · HVSR analysis report")
        canvas.drawRightString(w - 0.75 * inch, 0.52 * inch, f"Page {doc.page}")
        canvas.restoreState()


# --------------------------------------------------------------------------- report
def build_report(result: dict, context: dict, output_path: str, analysis_dir: str,
                 recording=None, progress: Callable[[float, str], None] | None = None) -> str:
    """Build the PDF analysis report and return ``output_path``."""
    context = context or {}
    st = _styles()
    generated = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _prog(frac: float, msg: str) -> None:
        if progress:
            progress(frac, msg)

    project = context.get("project") or {}
    station = context.get("station") or {}
    recording_ctx = context.get("recording") or {}
    source_files = context.get("source_files") or []
    steps = context.get("processing_steps") or []
    app_version = context.get("app_version", "–")
    unit_system = context.get("unit_system") or "metric"

    params = result.get("params") or {}
    inp = result.get("input") or {}
    windows = result.get("windows") or {}
    peaks = result.get("peaks") or {}
    sel = peaks.get("selected") or {}
    pv = result.get("peak_variability") or {}
    sesame = result.get("sesame")
    flags = result.get("quality_flags") or []
    curves = result.get("curves") or {}
    sel_key = curves.get("selected") or "geometric"
    sel_curve = curves.get(sel_key) or {}
    is_synth = bool(inp.get("is_synthetic") or recording_ctx.get("is_synthetic"))

    title = f"HVSR analysis — {recording_ctx.get('name') or inp.get('station') or 'recording'}"
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
    doc = SimpleDocTemplate(output_path, pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.9 * inch, bottomMargin=0.9 * inch,
                            title=title, author="QuakeLogic HVSR Studio", subject="HVSR analysis report")
    story: list[Any] = []

    # ---- Title block
    story.append(Paragraph("HVSR Analysis Report", st["title"]))
    sub = (f"{_esc(project.get('name', 'Project'))} · Station {_esc(station.get('code') or inp.get('station') or '–')} · "
           f"Recording {_esc(recording_ctx.get('name') or '–')} · Generated {generated}")
    story.append(Paragraph(sub, st["subtitle"]))
    if is_synth:
        story.append(Paragraph("<b>SYNTHETIC DATA NOTICE:</b> the analysed recording is a synthetic example, "
                               "not a field measurement. Results demonstrate the workflow only.",
                               ParagraphStyle("syn", parent=st["body"], textColor=FAIL)))
        story.append(Spacer(1, 6))

    # ---- 1 Summary
    story.append(Paragraph("1. Summary", st["h1"]))
    status = peaks.get("status", "–")
    verdict = "–"
    if sesame:
        verdict = (f"reliability {'PASSED' if sesame.get('reliability_passed') else 'FAILED'}; "
                   f"clear-peak criteria {sesame.get('clarity_passed_count', 0)}/6 "
                   f"({'PASSED' if sesame.get('clarity_passed') else 'NOT PASSED'})")
    summary_pairs = [
        ("Selected peak frequency f0", f"{_fmt(sel.get('frequency'))} Hz" if sel.get("frequency") is not None else "none selected"),
        ("Peak amplitude A0 (H/V)", _fmt(sel.get("amplitude"))),
        ("Peak selection", sel.get("source", "–")),
        ("Peak status", f"{status}: {peaks.get('message', '')}"),
        ("Mean curve", f"{sel_key} — band: {sel_curve.get('band', '–')}"),
        ("Windows", f"{windows.get('count_accepted', '–')} accepted of {windows.get('count_total', '–')} "
                    f"({windows.get('count_rejected', '–')} rejected), {windows.get('length_s', '–')} s, "
                    f"overlap {windows.get('overlap', '–')}"),
        ("SESAME (2004) criteria", verdict),
        ("Quality flags", "; ".join(f"[{f.get('severity', '')}] {f.get('message', '')}" for f in flags) or "none"),
    ]
    story.append(_kv_table(summary_pairs, st))
    _prog(0.1, "summary")

    # ---- 2 Station & recording
    story.append(Paragraph("2. Station and recording metadata", st["h1"]))
    meta_pairs = [
        ("Project", project.get("name")),
        ("Project description", project.get("description")),
        ("Station code", station.get("code") or inp.get("station")),
        ("Station name", station.get("name")),
        ("Latitude / longitude", f"{_fmt(station.get('latitude'), 5)} / {_fmt(station.get('longitude'), 5)}"
         if station.get("latitude") is not None else None),
        ("Elevation", format_elevation(station.get("elevation"), unit_system)),
        ("Sensor N-axis azimuth (°)", station.get("sensor_orientation_deg")),
        ("Recording", recording_ctx.get("name")),
        ("Sampling rate (Hz)", recording_ctx.get("sample_rate", inp.get("fs"))),
        ("Start time (UTC)", recording_ctx.get("start_time", inp.get("start_time"))),
        ("Duration (s)", recording_ctx.get("duration_s", inp.get("duration_s"))),
        ("Samples per component", recording_ctx.get("n_samples", inp.get("n_samples"))),
        ("Recorded units", recording_ctx.get("units")),
        ("Report unit system", unit_system_label(unit_system) + (
            f" — amplitudes shown as {display_amplitude_unit(recording_ctx.get('units'), recording_ctx.get('unit_kind'), unit_system)[0]}"
            if display_amplitude_unit(recording_ctx.get("units"), recording_ctx.get("unit_kind"), unit_system)[1] != 1.0 else "")),
        ("Channels", recording_ctx.get("channels")),
        ("Synthetic data", is_synth),
        ("Analysed file", inp.get("path")),
        ("Analysed file SHA-256", inp.get("sha256")),
    ]
    story.append(_kv_table([(k, v) for k, v in meta_pairs if v not in (None, "", "–")], st))
    if source_files:
        story.append(Paragraph("Source files", st["h2"]))
        rows = [["File", "Role", "Size (bytes)", "SHA-256"]]
        for f in source_files:
            rows.append([f.get("name") or f.get("path", "–"), f.get("role", "–"), _fmt(f.get("size_bytes")),
                         Paragraph(_esc(f.get("sha256", "–")), st["mono"])])
        story.append(_table(rows, st, col_widths=[2.2 * inch, 0.6 * inch, 0.9 * inch, 3.1 * inch]))
    survey = context.get("survey") or {}
    if any(v not in (None, "", []) for k, v in survey.items() if k != "photos") or survey.get("photos"):
        story.append(Paragraph("Survey", st["h2"]))
        survey_pairs = [
            ("Survey date", survey.get("date")),
            ("Client", survey.get("client")),
            ("Place ID", survey.get("place_id")),
            ("Address", survey.get("address")),
            ("Latitude / longitude", f"{_fmt(survey.get('latitude'), 5)} / {_fmt(survey.get('longitude'), 5)}"
             + (f" ({survey.get('datum')})" if survey.get("datum") else "")
             if survey.get("latitude") is not None or survey.get("longitude") is not None else None),
            ("Elevation", format_elevation(survey.get("elevation_m"), unit_system)),
            ("Weather", survey.get("weather")),
            ("Notes", survey.get("notes")),
        ]
        story.append(_kv_table([(k, v) for k, v in survey_pairs if v not in (None, "", "–")], st))
        photo_cells = []
        for ph in (survey.get("photos") or [])[:2]:
            path = ph.get("path") or ph.get("file") if isinstance(ph, dict) else ph
            if not path:
                continue
            path = str(path)
            if not os.path.isabs(path):
                path = os.path.join(analysis_dir, path)
            if not os.path.isfile(path):
                continue
            try:
                from reportlab.lib.utils import ImageReader
                iw, ih = ImageReader(path).getSize()
                max_w, max_h = 3.3 * inch, 2.6 * inch
                scale = min(max_w / iw, max_h / ih)
                img = Image(path, width=iw * scale, height=ih * scale)
                caption = (ph.get("caption") if isinstance(ph, dict) else "") or os.path.basename(path)
                photo_cells.append([img, Paragraph(_esc(caption), st["caption"])])
            except Exception:
                continue
        if photo_cells:
            story.append(Spacer(1, 4))
            cells = [[Table([[cell[0]], [cell[1]]], colWidths=[3.4 * inch]) for cell in photo_cells]]
            t = Table(cells, colWidths=[3.4 * inch] * len(photo_cells), hAlign="LEFT")
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.append(t)
    _prog(0.2, "metadata")

    # ---- 3 Processing settings
    story.append(Paragraph("3. Processing settings", st["h1"]))
    story.append(Paragraph("Pre-processing steps (applied in order)", st["h2"]))
    if steps:
        rows = [["#", "Operation", "Parameters"]]
        for i, s in enumerate(steps, 1):
            if s.get("enabled", True) is False:
                continue
            rows.append([str(i), s.get("op", "–"), _fmt(s.get("params") or {})])
        story.append(_table(rows, st, col_widths=[0.4 * inch, 1.4 * inch, 5.0 * inch]))
    else:
        story.append(Paragraph("No pre-processing steps were applied; the analysis used the imported "
                               "recording as-is (per-window detrend and taper only).", st["body"]))
    story.append(Paragraph("HVSR parameters", st["h2"]))
    hv_pairs = [
        ("Window length / overlap", f"{_fmt(params.get('window_length_s'))} s / {_fmt(params.get('overlap'))}"),
        ("Per-window detrend / taper", f"{params.get('detrend', '–')} / {_fmt(params.get('taper_percent'))} % per side"),
        ("Smoothing", _fmt(params.get("smoothing"))),
        ("Frequency range / points", f"{_fmt(params.get('freq_min'))}–{_fmt(params.get('freq_max'))} Hz, "
                                     f"{params.get('n_freq', '–')} log-spaced"),
        ("Horizontal combination", f"{params.get('horizontal_method', '–')} ({params.get('combination_stage', '–')})"),
        ("Mean method", params.get("mean_method")),
        ("Peak search", _fmt(params.get("peak"))),
        ("Vertical floor (masking)", _fmt(params.get("vertical_floor"))),
        ("Minimum valid windows per bin", params.get("min_valid_windows")),
        ("Transient screening", _fmt(params.get("screening"))),
        ("Bootstrap", _fmt(params.get("bootstrap"))),
        ("Azimuthal", _fmt(params.get("azimuthal"))),
    ]
    story.append(_kv_table(hv_pairs, st))
    _prog(0.3, "settings")

    # ---- 4 Window statistics
    story.append(Paragraph("4. Window statistics", st["h1"]))
    scr = params.get("screening") or {}
    story.append(_kv_table([
        ("Total windows", windows.get("count_total")),
        ("Accepted", windows.get("count_accepted")),
        ("Rejected", windows.get("count_rejected")),
        ("Screening enabled", scr.get("enabled")),
        ("STA/LTA", _fmt(scr.get("sta_lta"))),
        ("Amplitude criterion", _fmt(scr.get("amplitude"))),
        ("Masking policy", (result.get("masking") or {}).get("policy")),
        ("Invalid frequency bins", len((result.get("masking") or {}).get("invalid_bins") or [])),
    ], st))
    rejected = [w for w in windows.get("items") or [] if not w.get("accepted")]
    if rejected:
        story.append(Paragraph("Rejected windows", st["h2"]))
        rows = [["#", "Start (s)", "End (s)", "Reason", "STA/LTA max", "STA/LTA min", "Amp. ratio"]]
        for w in rejected[:80]:
            rows.append([str(w.get("index")), _fmt(w.get("start_s"), 1), _fmt(w.get("end_s"), 1),
                         w.get("reason") or "–", _fmt(w.get("sta_lta_max"), 2), _fmt(w.get("sta_lta_min"), 2),
                         _fmt(w.get("amp_ratio"), 2)])
        if len(rejected) > 80:
            rows.append(["…", f"{len(rejected) - 80} more", "", "", "", "", ""])
        story.append(_table(rows, st, col_widths=[0.4 * inch, 0.8 * inch, 0.8 * inch, 1.3 * inch,
                                                    1.0 * inch, 1.0 * inch, 1.0 * inch]))
    _prog(0.4, "windows")

    # ---- 5 Figures
    story.append(PageBreak())
    story.append(Paragraph("5. Figures", st["h1"]))
    tmpdir = tempfile.mkdtemp(prefix="hvsr_report_")
    fig_specs = [
        ("hvsr", "H/V spectral ratio: mean curve, dispersion band, accepted window curves and selected peak."),
        ("spectra", "Mean smoothed Fourier amplitude spectra of the three components over accepted windows."),
    ]
    if recording is not None:
        fig_specs.append(("windows", "Three-component waveforms with accepted (green) and rejected (red) windows."))
    fig_specs.append(("peak_distribution", "Distribution of window-level peak frequencies with median, "
                                           "16th/84th percentiles and bootstrap interval."))
    if result.get("azimuthal"):
        fig_specs.append(("azimuthal", "Azimuthal H/V versus frequency and azimuth."))
    window_curves = None
    try:
        from ..hvsr import window_curves as _wc  # optional, only for the faint per-window traces
        window_curves = _wc(analysis_dir) if analysis_dir and os.path.isdir(analysis_dir) else None
    except Exception:
        window_curves = None
    n_fig = len(fig_specs)
    for i, (kind, caption) in enumerate(fig_specs):
        caption = f"Figure {i + 1}. {caption}"
        path = os.path.join(tmpdir, f"{kind}.png")
        try:
            render_figure(result, kind, "png", path, recording=recording, theme="light",
                          window_curves=window_curves if kind == "hvsr" else None,
                          unit_system=unit_system, units=recording_ctx.get("units"),
                          unit_kind=recording_ctx.get("unit_kind"))
            img = Image(path, width=6.8 * inch, height=4.25 * inch, kind="proportional")
            story.append(KeepTogether([img, Paragraph(caption, st["caption"])]))
        except Exception as exc:  # a missing figure must not abort the report
            story.append(Paragraph(f"{caption} — not rendered: {_esc(exc)}", st["caption"]))
        _prog(0.4 + 0.4 * (i + 1) / n_fig, f"figure {kind}")

    # ---- 6 Peak & variability
    story.append(Paragraph("6. Peak and variability", st["h1"]))
    cands = peaks.get("candidates") or []
    if cands:
        rows = [["Rank", "Frequency (Hz)", "Amplitude (H/V)", "Prominence"]]
        for c in cands:
            rows.append([str(c.get("rank", "–")), _fmt(c.get("frequency")), _fmt(c.get("amplitude")),
                         _fmt(c.get("prominence"))])
        story.append(_table(rows, st, col_widths=[0.7 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch]))
    else:
        story.append(Paragraph("No candidate peaks were found in the search range.", st["body"]))
    story.append(Spacer(1, 4))
    boot = pv.get("bootstrap") or {}
    story.append(_kv_table([
        ("Search range (Hz)", _fmt(peaks.get("search_range"))),
        ("Selected peak", f"f0 = {_fmt(sel.get('frequency'))} Hz, A0 = {_fmt(sel.get('amplitude'))} "
                          f"({sel.get('source', '–')})" if sel else "none"),
        ("Window-level peaks (n)", pv.get("n")),
        ("Median f0 (Hz)", pv.get("median")),
        ("16th / 84th percentile (Hz)", f"{_fmt(pv.get('p16'))} / {_fmt(pv.get('p84'))}"),
        ("Std of window f0 (Hz)", pv.get("std")),
        ("Std of ln f0", pv.get("std_ln")),
        ("Definition", pv.get("definition")),
        ("Bootstrap", (f"{boot.get('n_resamples')} resamples, seed {boot.get('seed')}: f0 in "
                       f"[{_fmt(boot.get('f0_p2_5'))}, {_fmt(boot.get('f0_p97_5'))}] Hz, A0 in "
                       f"[{_fmt(boot.get('a0_p2_5'))}, {_fmt(boot.get('a0_p97_5'))}] — {boot.get('definition', '')}")
         if boot else "disabled"),
    ], st))
    _prog(0.85, "peaks")

    # ---- 7 SESAME
    story.append(Paragraph("7. SESAME (2004) reliability and clear-peak criteria", st["h1"]))
    if sesame:
        rows = [["ID", "Criterion", "Value", "Threshold", "Result"]]
        for crit in (sesame.get("reliability") or []) + (sesame.get("clarity") or []):
            rows.append([crit.get("id", "–"), f"{crit.get('label', '')} {('— ' + crit['detail']) if crit.get('detail') else ''}",
                         _fmt(crit.get("value")), _fmt(crit.get("threshold")),
                         "PASS" if crit.get("passed") else "FAIL"])
        story.append(_table(rows, st, col_widths=[0.45 * inch, 3.45 * inch, 1.0 * inch, 1.0 * inch, 0.9 * inch],
                            status_col=4))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"Reliability: {'passed' if sesame.get('reliability_passed') else 'not passed'} (all three criteria "
            f"required). Clear peak: {sesame.get('clarity_passed_count', 0)} of 6 criteria fulfilled "
            f"({'passed' if sesame.get('clarity_passed') else 'not passed'}; at least 5 of 6 required). "
            f"Criteria are evaluated on the geometric (log) mean curve and its log standard deviation.", st["body"]))
        story.append(Paragraph("Reference: " + _esc(sesame.get("reference") or SESAME_CITATION), st["small"]))
    else:
        story.append(Paragraph("SESAME criteria were not evaluated for this analysis.", st["body"]))

    # ---- 8 Interpretation limitations
    story.append(Paragraph("8. Interpretation limitations", st["h1"]))
    notes = list(result.get("interpretation_notes") or DEFAULT_INTERPRETATION_NOTES)
    if is_synth:
        notes.append("The input is a synthetic example; no geological interpretation applies.")
    for n in notes:
        story.append(Paragraph("• " + _esc(n), st["body"]))

    # ---- 9 Reproducibility
    story.append(Paragraph("9. Reproducibility", st["h1"]))
    versions = result.get("versions") or {}
    story.append(_kv_table([
        ("Application version", app_version),
        ("Engine version", result.get("engine_version")),
        ("Library versions", _fmt(versions)),
        ("Random seed", result.get("random_seed")),
        ("Computed at", result.get("computed_at")),
        ("Elapsed (s)", result.get("elapsed_s")),
        ("Analysis directory", analysis_dir),
        ("Result files", "result.json, curves.npz, exports/*.csv, exports/summary.json, exports/config.json"),
        ("Configuration hash (SHA-256/16)", _config_hash(result)),
        ("Report generated", generated),
    ], st))

    # ---- 10 Disclaimer
    story.append(Paragraph("10. Disclaimer", st["h1"]))
    disclaimer_text = DISCLAIMER
    if is_synth:
        disclaimer_text += (" Synthetic data notice: the analysed recording is a synthetic example generated to "
                            "demonstrate the workflow; it is not a field measurement.")
    box = Table([[Paragraph(_esc(disclaimer_text), st["body"])]], colWidths=[6.8 * inch])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(box)
    story.append(Spacer(1, 8))
    story.append(Paragraph(_esc(COMPANY_LINE), st["small"]))
    story.append(Paragraph(_esc(copyright_line(generated)), st["small"]))

    doc.build(story, onFirstPage=_PageDecorator(title, generated), onLaterPages=_PageDecorator(title, generated))
    _prog(1.0, "done")
    return output_path
