"""Pydantic request models. Nested engine parameter blocks are passed through as dicts
(extra="allow") so the engine stays the authority on their exact contents."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Passthrough(BaseModel):
    model_config = ConfigDict(extra="allow")


class InspectRequest(Passthrough):
    path: str


class ImportRequest(Passthrough):
    recording_id: str
    output_path: str
    sources: list[dict[str, Any]]
    format: Literal["ascii", "mseed", "saf", "seismic"]
    ascii: dict[str, Any] | None = None
    mseed: dict[str, Any] | None = None
    saf: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class DataRequest(Passthrough):
    path: str
    t_start: float | None = None
    t_end: float | None = None
    max_points: int = Field(default=4000, ge=10, le=200_000)
    components: list[str] = Field(default_factory=lambda: ["n", "e", "z"])


class SpectraRequest(Passthrough):
    path: str
    kind: Literal["fas", "psd", "spectrogram"] = "fas"


class PreviewRequest(Passthrough):
    input_path: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    t_start: float | None = None
    t_end: float | None = None
    max_points: int = Field(default=4000, ge=10, le=200_000)


class RunRequest(Passthrough):
    input_path: str
    output_path: str
    steps: list[dict[str, Any]] = Field(default_factory=list)


class FilterResponseRequest(Passthrough):
    fs: float = Field(gt=0)
    step: dict[str, Any]
    n_points: int = Field(default=1024, ge=16, le=65536)


class WindowsRequest(Passthrough):
    input_path: str
    params: dict[str, Any] = Field(default_factory=dict)
    window_overrides: dict[str, Any] | None = None


class AnalyzeRequest(Passthrough):
    input_path: str
    output_dir: str
    params: dict[str, Any] = Field(default_factory=dict)
    window_overrides: dict[str, Any] | None = None
    manual_peak: dict[str, Any] | None = None
    random_seed: int | None = None


class DirRequest(Passthrough):
    dir: str


class SelectPeakRequest(Passthrough):
    analysis_dir: str
    frequency: float | None = None


class FigureRequest(Passthrough):
    analysis_dir: str
    figure: Literal["hvsr", "spectra", "windows", "azimuthal", "peak_distribution"]
    format: Literal["png", "svg", "pdf"] = "png"
    output_path: str
    theme: Literal["light", "dark"] = "light"
    recording_path: str | None = None


class ReportRequest(Passthrough):
    analysis_dir: str
    output_path: str
    context: dict[str, Any] = Field(default_factory=dict)
    recording_path: str | None = None


class ModelRequest(Passthrough):
    layers: list[dict[str, Any]]
    freq_min: float = Field(default=0.2, gt=0)
    freq_max: float = Field(default=100.0, gt=0)
    n_freq: int = Field(default=200, ge=10, le=5000)
    vs30_offset_m: float = Field(default=0.0, ge=0)


class CurveImportRequest(Passthrough):
    path: str
