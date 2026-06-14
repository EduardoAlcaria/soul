import sqlite3
from typing import Any
import numpy as np


def _p(arr: list[float], pct: float) -> int:
    if not arr:
        return 0
    return int(np.percentile(arr, pct * 100))


def compute_iki_stats(conn: sqlite3.Connection, session_ids: list[int] | None = None) -> dict[str, Any]:
    sf = _session_filter(session_ids)
    rows = conn.execute(
        f"SELECT char, ts, context, session_id FROM keystrokes "
        f"WHERE is_delete = 0 AND char IS NOT NULL AND length(char) = 1 "
        f"{sf} ORDER BY session_id, ts"
    ).fetchall()

    iki_all: list[float] = []
    iki_by_ctx: dict[str, list[float]] = {}

    for i in range(1, len(rows)):
        if rows[i]['session_id'] != rows[i - 1]['session_id']:
            continue
        gap = rows[i]['ts'] - rows[i - 1]['ts']
        if 0 < gap < 1000:
            iki_all.append(gap)
            ctx = rows[i]['context'] or 'other'
            iki_by_ctx.setdefault(ctx, []).append(gap)

    def stats(arr: list[float]) -> dict[str, int]:
        return {'p25': _p(arr, 0.25), 'p50': _p(arr, 0.5), 'p75': _p(arr, 0.75), 'p90': _p(arr, 0.9)}

    return {
        'overall': stats(iki_all),
        'by_context': {
            ctx: {**stats(ikis), 'count': len(ikis)}
            for ctx, ikis in iki_by_ctx.items()
        },
    }


def compute_digraph_latencies(conn: sqlite3.Connection, session_ids: list[int] | None = None, min_count: int = 5) -> list[dict[str, Any]]:
    sf = _session_filter(session_ids)
    rows = conn.execute(
        f"SELECT char, ts, session_id FROM keystrokes "
        f"WHERE is_delete = 0 AND char IS NOT NULL AND length(char) = 1 "
        f"{sf} ORDER BY session_id, ts"
    ).fetchall()

    digraph_map: dict[str, list[float]] = {}
    for i in range(1, len(rows)):
        if rows[i]['session_id'] != rows[i - 1]['session_id']:
            continue
        gap = rows[i]['ts'] - rows[i - 1]['ts']
        if 0 < gap < 500:
            pair = rows[i - 1]['char'] + rows[i]['char']
            digraph_map.setdefault(pair, []).append(gap)

    result = []
    for pair, gaps in digraph_map.items():
        if len(gaps) < min_count:
            continue
        result.append({
            'pair': pair,
            'p50': _p(gaps, 0.5),
            'p90': _p(gaps, 0.9),
            'count': len(gaps),
        })
    result.sort(key=lambda x: -x['count'])
    return result[:50]


def compute_wpm_by_context(conn: sqlite3.Connection, session_ids: list[int] | None = None) -> dict[str, int]:
    sf = _session_filter(session_ids)
    rows = conn.execute(
        f"SELECT wpm, context FROM bursts WHERE 1=1 {sf}"
    ).fetchall()

    by_ctx: dict[str, list[float]] = {}
    for r in rows:
        ctx = r['context'] or 'other'
        by_ctx.setdefault(ctx, []).append(r['wpm'])

    return {ctx: round(float(np.mean(wpms))) for ctx, wpms in by_ctx.items()}


def compute_pause_stats(conn: sqlite3.Connection, session_ids: list[int] | None = None) -> dict[str, Any]:
    sf = _session_filter(session_ids)
    rows = conn.execute(
        f"SELECT duration_ms FROM pauses WHERE 1=1 {sf} ORDER BY duration_ms"
    ).fetchall()

    durations = [r['duration_ms'] for r in rows]
    micro  = [d for d in durations if d < 1000]
    think  = [d for d in durations if 1000 <= d < 5000]
    deep   = [d for d in durations if 5000 <= d < 15000]
    stuck  = [d for d in durations if d >= 15000]

    return {
        'micro_p50':  _p(micro, 0.5),
        'think_p50':  _p(think, 0.5),
        'think_p90':  _p(think, 0.9),
        'deep_count': len(deep),
        'stuck_count': len(stuck),
    }


def compute_velocity(conn: sqlite3.Connection, session_ids: list[int] | None = None) -> dict[str, Any]:
    sf = _session_filter(session_ids)
    rows = conn.execute(
        f"SELECT wpm, error_count, char_count FROM bursts WHERE 1=1 {sf}"
    ).fetchall()

    if not rows:
        return {'wpm_mean': 0, 'wpm_p90': 0, 'error_rate': 0.0}

    wpms = [r['wpm'] for r in rows]
    total_chars = sum(r['char_count'] for r in rows)
    total_errors = sum(r['error_count'] for r in rows)

    return {
        'wpm_mean': round(float(np.mean(wpms))),
        'wpm_p90':  round(float(np.percentile(wpms, 90))),
        'error_rate': round(total_errors / total_chars, 4) if total_chars else 0.0,
    }


def _session_filter(session_ids: list[int] | None) -> str:
    if session_ids:
        ids = ','.join(str(i) for i in session_ids)
        return f"AND session_id IN ({ids})"
    return ''
