import sqlite3
import time
from typing import Any

from .stats import compute_iki_stats, compute_digraph_latencies, compute_wpm_by_context, compute_pause_stats, compute_velocity
from .signals import compute_signals
from .hmm_states import decode_states, compute_transitions, fit_or_prior


def build_profile(conn: sqlite3.Connection, session_ids: list[int] | None = None) -> dict[str, Any]:
    idf = f"AND id IN ({','.join(str(i) for i in session_ids)})" if session_ids else ''
    sf  = f"AND session_id IN ({','.join(str(i) for i in session_ids)})" if session_ids else ''

    sessions_n = conn.execute(
        f"SELECT COUNT(*) FROM sessions WHERE ended_at IS NOT NULL {idf}"
    ).fetchone()[0]

    total_keys = conn.execute(
        f"SELECT COUNT(*) FROM keystrokes WHERE 1=1 {sf}"
    ).fetchone()[0]

    # Stats layer
    velocity   = compute_velocity(conn, session_ids)
    pause_stats = compute_pause_stats(conn, session_ids)
    digraphs   = compute_digraph_latencies(conn, session_ids)
    iki_stats  = compute_iki_stats(conn, session_ids)

    # Signals layer
    signals = compute_signals(conn, session_ids)

    # HMM layer — decode IKI sequence into cognitive states
    key_rows = conn.execute(
        f"SELECT ts, session_id FROM keystrokes "
        f"WHERE is_delete = 0 AND char IS NOT NULL AND length(char) = 1 {sf} "
        f"ORDER BY session_id, ts"
    ).fetchall()

    ikis: list[float] = []
    for i in range(1, len(key_rows)):
        if key_rows[i]['session_id'] != key_rows[i - 1]['session_id']:
            continue
        gap = key_rows[i]['ts'] - key_rows[i - 1]['ts']
        if 0 < gap < 1000:
            ikis.append(float(gap))

    model = fit_or_prior(ikis) if ikis else None
    state_seq = decode_states(ikis, model) if ikis else []

    counts = {'FLOW': 0, 'THINKING': 0, 'ANXIOUS': 0, 'EXPLORING': 0}
    for s in state_seq:
        counts[s] += 1
    total_states = len(state_seq) or 1

    cognitive_states = {
        'flow_pct':      round(counts['FLOW']      / total_states, 3),
        'anxious_pct':   round(counts['ANXIOUS']   / total_states, 3),
        'exploring_pct': round(counts['EXPLORING'] / total_states, 3),
        'stuck_pct':     round(counts['THINKING']  / total_states, 3),
    }

    return {
        'sessions_analyzed':  sessions_n,
        'total_keystrokes':   total_keys,
        'velocity':           velocity,
        'pauses':             pause_stats,
        'digraph_latencies':  digraphs,
        'iki':                iki_stats,
        'wpm_by_context':     signals['wpm_by_context'],
        'fatigue_curve':      signals['fatigue_curve'],
        'cognitive_signals': {
            'anxiety_bursts':        signals['anxiety_bursts'],
            'exploration_sequences': signals['exploration_sequences'],
            'stuck_moments':         signals['stuck_moments'],
        },
        'cognitive_states':   cognitive_states,
        'hmm_transitions':    compute_transitions(state_seq),
        'difficulty_triggers': signals['difficulty_triggers'],
        'generated_at':       int(time.time() * 1000),
    }
