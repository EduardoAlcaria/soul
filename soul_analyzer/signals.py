import sqlite3
from typing import Any
import numpy as np


def compute_signals(conn: sqlite3.Connection, session_ids: list[int] | None = None) -> dict[str, Any]:
    sf = _sf(session_ids)
    idf = _idf(session_ids)

    # Load all keystrokes ordered by session + time
    rows = conn.execute(
        f"SELECT ts, is_delete, context FROM keystrokes WHERE 1=1 {sf} ORDER BY session_id, ts"
    ).fetchall()

    # Anxiety: delete within 300ms of a non-delete
    anxiety = 0
    for i in range(1, len(rows)):
        if rows[i]['is_delete'] == 1 and rows[i - 1]['is_delete'] == 0:
            if rows[i]['ts'] - rows[i - 1]['ts'] < 300:
                anxiety += 1

    # Exploration: type ≥5 chars → delete ≥ floor(typed/2) of them
    exploration = 0
    i = 0
    while i < len(rows):
        if rows[i]['is_delete'] == 0:
            typed = 0
            while i < len(rows) and rows[i]['is_delete'] == 0:
                typed += 1
                i += 1
            deleted = 0
            while i < len(rows) and rows[i]['is_delete'] == 1:
                deleted += 1
                i += 1
            if typed >= 5 and deleted >= typed // 2:
                exploration += 1
        else:
            i += 1

    # Stuck moments: pauses ≥ 15000ms
    stuck = conn.execute(
        f"SELECT COUNT(*) FROM pauses WHERE duration_ms >= 15000 {sf}"
    ).fetchone()[0]

    # Bursts for WPM by context and fatigue
    burst_rows = conn.execute(
        f"SELECT ts, wpm, char_count, session_id, context FROM bursts WHERE 1=1 {sf}"
    ).fetchall()

    ctx_wpm: dict[str, list[float]] = {}
    for b in burst_rows:
        ctx = b['context'] or 'other'
        ctx_wpm.setdefault(ctx, []).append(b['wpm'])

    wpm_by_ctx = {ctx: round(float(np.mean(v))) for ctx, v in ctx_wpm.items()}
    overall_mean = float(np.mean([b['wpm'] for b in burst_rows])) if burst_rows else 0.0
    difficulty = [ctx for ctx, wpm in wpm_by_ctx.items() if overall_mean > 0 and wpm < overall_mean * 0.7]

    # Fatigue curve: WPM in 15-min time buckets from session start
    session_rows = conn.execute(
        f"SELECT id, started_at FROM sessions WHERE ended_at IS NOT NULL {idf}"
    ).fetchall()
    start_map = {r['id']: r['started_at'] for r in session_rows}

    buckets: dict[int, list[float]] = {0: [], 15: [], 30: [], 60: []}
    for b in burst_rows:
        s = start_map.get(b['session_id'])
        if s is None:
            continue
        mins = (b['ts'] - s) / 60_000
        if mins < 15:
            buckets[0].append(b['wpm'])
        elif mins < 30:
            buckets[15].append(b['wpm'])
        elif mins < 60:
            buckets[30].append(b['wpm'])
        else:
            buckets[60].append(b['wpm'])

    def mean_wpm(arr: list[float]) -> int:
        return round(float(np.mean(arr))) if arr else 0

    w0 = mean_wpm(buckets[0])
    w60 = mean_wpm(buckets[60])

    return {
        'anxiety_bursts': anxiety,
        'exploration_sequences': exploration,
        'stuck_moments': stuck,
        'difficulty_triggers': difficulty,
        'wpm_by_context': wpm_by_ctx,
        'fatigue_curve': {
            'wpm_at_0min':  w0,
            'wpm_at_15min': mean_wpm(buckets[15]),
            'wpm_at_30min': mean_wpm(buckets[30]),
            'wpm_at_60min': w60,
            'decay_rate': w0 - w60,
        },
    }


def _sf(ids: list[int] | None) -> str:
    return f"AND session_id IN ({','.join(str(i) for i in ids)})" if ids else ''

def _idf(ids: list[int] | None) -> str:
    return f"AND id IN ({','.join(str(i) for i in ids)})" if ids else ''
