import numpy as np
import pytest
from soul_analyzer.hmm_states import (
    quantize_iki, decode_states, compute_transitions,
    STATES, fit_or_prior
)

def test_quantize_iki_bins():
    assert quantize_iki(50)   == 0  # FAST
    assert quantize_iki(99)   == 0  # FAST
    assert quantize_iki(100)  == 1  # NORMAL
    assert quantize_iki(299)  == 1  # NORMAL
    assert quantize_iki(300)  == 2  # SLOW
    assert quantize_iki(999)  == 2  # SLOW
    assert quantize_iki(1000) == 3  # VERY_SLOW
    assert quantize_iki(5000) == 3  # VERY_SLOW

def test_decode_states_length_matches_input():
    ikis = [80, 120, 250, 400, 1200]
    states = decode_states(ikis)
    assert len(states) == len(ikis)

def test_decode_states_labels_valid():
    ikis = [60, 150, 500, 1500, 80, 100]
    states = decode_states(ikis)
    for s in states:
        assert s in STATES

def test_decode_states_all_fast_mostly_flow_or_anxious():
    ikis = [60] * 30  # all FAST
    states = decode_states(ikis)
    flow_or_anxious = sum(1 for s in states if s in ('FLOW', 'ANXIOUS'))
    assert flow_or_anxious > 15

def test_decode_states_all_very_slow_mostly_thinking():
    ikis = [1500] * 30  # all VERY_SLOW
    states = decode_states(ikis)
    thinking = sum(1 for s in states if s == 'THINKING')
    assert thinking > 15

def test_decode_empty():
    assert decode_states([]) == []

def test_compute_transitions_counts():
    states = ['FLOW', 'FLOW', 'THINKING', 'FLOW']
    t = compute_transitions(states)
    assert abs(t.get('FLOW→FLOW', 0) - 1/3) < 0.01
    assert abs(t.get('FLOW→THINKING', 0) - 1/3) < 0.01
    assert abs(t.get('THINKING→FLOW', 0) - 1/3) < 0.01

def test_compute_transitions_empty():
    assert compute_transitions([]) == {}
    assert compute_transitions(['FLOW']) == {}

def test_fit_or_prior_returns_model():
    model = fit_or_prior([80, 150, 400, 1200] * 10)
    assert model is not None
