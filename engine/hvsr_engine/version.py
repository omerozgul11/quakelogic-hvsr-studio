"""Engine version and dependency versions (recorded in every result)."""
from __future__ import annotations

import platform

ENGINE_VERSION = "1.1.0"
# Release date of this version: licences include updates released up to their maintenance date.
RELEASE_DATE = "2026-10-10"


def versions() -> dict:
    import matplotlib
    import numpy
    import obspy
    import pandas
    import scipy

    return {
        "engine": ENGINE_VERSION,
        "python": platform.python_version(),
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "obspy": obspy.__version__,
        "pandas": pandas.__version__,
        "matplotlib": matplotlib.__version__,
    }
