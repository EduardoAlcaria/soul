from __future__ import annotations
import numpy as np
from hmmlearn.hmm import CategoricalHMM
from typing import Any

STATES = ['FLOW', 'THINKING', 'ANXIOUS', 'EXPLORING']
_N_STATES = 4
_MIN_OBS_FOR_TRAINING = 200

_PRIOR_START = np.array([0.50, 0.30, 0.10, 0.10])

_PRIOR_TRANS = np.array([
    [0.80, 0.10, 0.05, 0.05],  # FLOW →
    [0.60, 0.25, 0.05, 0.10],  # THINKING →
    [0.30, 0.20, 0.40, 0.10],  # ANXIOUS →
    [0.30, 0.30, 0.10, 0.30],  # EXPLORING →
])

_PRIOR_EMIT = np.array([
    [0.50, 0.35, 0.10, 0.05],  # FLOW emits FAST/NORMAL/SLOW/VERY_SLOW
    [0.05, 0.20, 0.35, 0.40],  # THINKING emits (dominates VERY_SLOW)
    [0.45, 0.40, 0.10, 0.05],  # ANXIOUS emits (dominates FAST)
    [0.10, 0.35, 0.40, 0.15],  # EXPLORING emits (dominates SLOW)
])


def quantize_iki(iki_ms: float) -> int:
    if iki_ms < 100:
        return 0  # FAST
    if iki_ms < 300:
        return 1  # NORMAL
    if iki_ms < 1000:
        return 2  # SLOW
    return 3       # VERY_SLOW


def _make_prior_model() -> CategoricalHMM:
    model = CategoricalHMM(n_components=_N_STATES, n_iter=1)
    model.startprob_ = _PRIOR_START.copy()
    model.transmat_ = _PRIOR_TRANS.copy()
    model.emissionprob_ = _PRIOR_EMIT.copy()
    return model


def fit_or_prior(ikis: list[float]) -> CategoricalHMM:
    if len(ikis) < _MIN_OBS_FOR_TRAINING:
        return _make_prior_model()

    obs = np.array([quantize_iki(x) for x in ikis]).reshape(-1, 1)
    model = CategoricalHMM(n_components=_N_STATES, n_iter=50, random_state=42, init_params='')
    model.startprob_ = _PRIOR_START.copy()
    model.transmat_ = _PRIOR_TRANS.copy()
    model.emissionprob_ = _PRIOR_EMIT.copy()
    try:
        model.fit(obs)
    except Exception:
        return _make_prior_model()
    return model


def decode_states(ikis: list[float], model: CategoricalHMM | None = None) -> list[str]:
    if not ikis:
        return []
    if model is None:
        model = fit_or_prior(ikis)
    obs = np.array([quantize_iki(x) for x in ikis]).reshape(-1, 1)
    _, state_indices = model.decode(obs, algorithm='viterbi')
    return [STATES[i] for i in state_indices]


def compute_transitions(states: list[str]) -> dict[str, float]:
    if len(states) < 2:
        return {}
    counts: dict[str, int] = {}
    for i in range(1, len(states)):
        key = f"{states[i-1]}→{states[i]}"
        counts[key] = counts.get(key, 0) + 1
    total = sum(counts.values())
    return {k: round(v / total, 3) for k, v in counts.items()}
