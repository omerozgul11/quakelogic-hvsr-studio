import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hvsr_engine.synthetic import synthetic_recording  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture(scope="session")
def syn_rec():
    """20-minute synthetic recording, f0 = 2.5 Hz, A0 = 5, seed 1."""
    return synthetic_recording(fs=100.0, duration_s=1200.0, f0=2.5, amplification=5.0, seed=1)


@pytest.fixture(scope="session")
def short_rec():
    return synthetic_recording(fs=100.0, duration_s=300.0, f0=2.5, amplification=5.0, seed=3)


@pytest.fixture
def examples_dir():
    if not EXAMPLES.exists():
        pytest.skip("examples/ not generated")
    return EXAMPLES


@pytest.fixture
def rng():
    return np.random.default_rng(42)
