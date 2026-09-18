"""Lazy facade over hvsr_engine so that a partially available engine yields clear errors
(and so the service module imports even if the scientific package is being rebuilt)."""

from __future__ import annotations

import importlib

from .errors import ServiceError


def _mod(name: str):
    try:
        return importlib.import_module(f"hvsr_engine.{name}")
    except ImportError as exc:
        raise ServiceError("engine_unavailable", f"hvsr_engine.{name} is not available: {exc}", 500) from exc


def versions() -> dict:
    return _mod("version").versions()


def engine_version() -> str:
    return _mod("version").ENGINE_VERSION


def inspect_file(path: str) -> dict:
    return _mod("io.inspect").inspect_file(path)


def import_recording(request: dict) -> dict:
    return _mod("io.importer").import_recording(request)


def load_recording(path: str):
    return _mod("io.canonical").load_recording(path)


def save_recording(rec, path: str):
    return _mod("io.canonical").save_recording(rec, path)


def recording_display(rec, **kwargs) -> dict:
    return _mod("display").recording_display(rec, **kwargs)


def compute_spectra(rec, params: dict) -> dict:
    return _mod("spectra").compute_spectra(rec, params)


def apply_steps(rec, steps: list, progress=None):
    return _mod("preprocessing").apply_steps(rec, steps, progress=progress)


def filter_response(fs: float, step: dict, n_points: int = 1024) -> dict:
    return _mod("preprocessing").filter_response(fs, step, n_points=n_points)


def screen_windows(rec, params: dict, window_overrides: dict | None) -> dict:
    return _mod("windows").screen_windows(rec, params, window_overrides)


def analyze(rec, params: dict, **kwargs):
    return _mod("hvsr").analyze(rec, params, **kwargs)


def write_result(result, output_dir: str):
    return _mod("hvsr").write_result(result, output_dir)


def load_result(output_dir: str) -> dict:
    return _mod("hvsr").load_result(output_dir)


def window_curves(output_dir: str) -> dict:
    return _mod("hvsr").window_curves(output_dir)


def select_peak(output_dir: str, frequency: float | None) -> dict:
    return _mod("hvsr").select_peak(output_dir, frequency)


def figure(result: dict, kind: str, fmt: str, output_path: str, **kwargs) -> str:
    return _mod("reporting.figures").figure(result, kind, fmt, output_path, **kwargs)


def build_report(result: dict, context: dict, output_path: str, analysis_dir: str, **kwargs) -> str:
    return _mod("reporting.pdf").build_report(result, context, output_path, analysis_dir, **kwargs)


def model_hvsr(layers: list, freq_min: float, freq_max: float, n_freq: int, vs30_offset_m: float = 0.0) -> dict:
    return _mod("modelling").model_hvsr(layers, freq_min, freq_max, n_freq, vs30_offset_m)


def read_curve_file(path: str) -> dict:
    return _mod("io.curves").read_curve_file(path)
