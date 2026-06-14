import pytest
from soul_analyzer.signals import compute_signals

BASE = 3_000_000

def seed(conn, keys=None, bursts=None, pauses=None):
    keys = keys or [{'ts': BASE, 'char': 'a', 'is_delete': 0, 'context': 'identifier'}]
    start = keys[0]['ts']
    end = keys[-1]['ts'] + 100
    sid = conn.execute(
        "INSERT INTO sessions (started_at, ended_at, file, language) VALUES (?,?,?,?)",
        (start, end, 'f.ts', 'typescript')
    ).lastrowid
    for k in keys:
        conn.execute(
            "INSERT INTO keystrokes (session_id,ts,event_type,char,is_delete,context,line,col) VALUES (?,?,?,?,?,?,?,?)",
            (sid, k['ts'], 'key', k.get('char','a'), k.get('is_delete',0), k.get('context','identifier'), 1, 0)
        )
    if bursts:
        for b in bursts:
            conn.execute(
                "INSERT INTO bursts (session_id,ts,char_count,duration_ms,wpm,error_count,context) VALUES (?,?,?,?,?,?,?)",
                (sid, b['ts'], b['char_count'], b['duration_ms'], b['wpm'], b.get('error_count', 0), b.get('context', 'identifier'))
            )
    if pauses:
        for p in pauses:
            conn.execute(
                "INSERT INTO pauses (session_id,ts,duration_ms) VALUES (?,?,?)",
                (sid, p['ts'], p['duration_ms'])
            )
    conn.commit()
    return sid

def test_anxiety_bursts_counts_rapid_reversals(db_conn):
    keys = [
        {'ts': BASE,       'char': 'a', 'is_delete': 0, 'context': 'identifier'},
        {'ts': BASE + 100, 'char': '',  'is_delete': 1, 'context': 'identifier'},  # delete < 300ms → anxiety
        {'ts': BASE + 200, 'char': 'b', 'is_delete': 0, 'context': 'identifier'},
        {'ts': BASE + 1700,'char': '',  'is_delete': 1, 'context': 'identifier'},  # delete after 1500ms → NOT anxiety
    ]
    seed(db_conn, keys=keys)
    sig = compute_signals(db_conn)
    assert sig['anxiety_bursts'] == 1

def test_anxiety_zero_when_no_rapid_reversals(db_conn):
    keys = [
        {'ts': BASE,       'char': 'a', 'is_delete': 0, 'context': 'identifier'},
        {'ts': BASE + 1000,'char': '',  'is_delete': 1, 'context': 'identifier'},  # slow delete
    ]
    seed(db_conn, keys=keys)
    sig = compute_signals(db_conn)
    assert sig['anxiety_bursts'] == 0

def test_exploration_sequences_detected(db_conn):
    keys = []
    t = BASE
    for _ in range(6):   # type 6
        keys.append({'ts': t, 'char': 'x', 'is_delete': 0, 'context': 'identifier'})
        t += 50
    for _ in range(4):   # delete 4 (≥ floor(6/2)=3, so ≥50%)
        keys.append({'ts': t, 'char': '', 'is_delete': 1, 'context': 'identifier'})
        t += 50
    for _ in range(4):   # retype
        keys.append({'ts': t, 'char': 'y', 'is_delete': 0, 'context': 'identifier'})
        t += 50
    seed(db_conn, keys=keys)
    sig = compute_signals(db_conn)
    assert sig['exploration_sequences'] >= 1

def test_exploration_not_triggered_below_threshold(db_conn):
    keys = []
    t = BASE
    for _ in range(6):
        keys.append({'ts': t, 'char': 'x', 'is_delete': 0, 'context': 'identifier'})
        t += 50
    for _ in range(2):   # only 2 deletes (< floor(6/2)=3)
        keys.append({'ts': t, 'char': '', 'is_delete': 1, 'context': 'identifier'})
        t += 50
    seed(db_conn, keys=keys)
    sig = compute_signals(db_conn)
    assert sig['exploration_sequences'] == 0

def test_stuck_moments_counts_long_pauses(db_conn):
    seed(db_conn, pauses=[
        {'ts': BASE, 'duration_ms': 500},         # not stuck
        {'ts': BASE + 1000, 'duration_ms': 20000},# stuck
        {'ts': BASE + 3000, 'duration_ms': 25000},# stuck
    ])
    sig = compute_signals(db_conn)
    assert sig['stuck_moments'] == 2

def test_difficulty_triggers_contexts_below_70pct_mean(db_conn):
    bursts = [
        {'ts': BASE + 100, 'wpm': 200, 'char_count': 10, 'duration_ms': 300, 'context': 'identifier'},
        {'ts': BASE + 200, 'wpm': 200, 'char_count': 10, 'duration_ms': 300, 'context': 'identifier'},
        {'ts': BASE + 300, 'wpm': 60,  'char_count': 3,  'duration_ms': 300, 'context': 'operator'},
    ]
    seed(db_conn, bursts=bursts)
    sig = compute_signals(db_conn)
    assert 'operator' in sig['difficulty_triggers']
    assert 'identifier' not in sig['difficulty_triggers']

def test_fatigue_curve_buckets(db_conn):
    start = BASE
    bursts = [
        {'ts': start + 60_000,   'wpm': 200, 'char_count': 10, 'duration_ms': 300, 'context': 'identifier'},
        {'ts': start + 1_200_000,'wpm': 150, 'char_count': 8,  'duration_ms': 300, 'context': 'identifier'},
    ]
    sid = db_conn.execute(
        "INSERT INTO sessions (started_at, ended_at, file, language) VALUES (?,?,?,?)",
        (start, start + 2_000_000, 'f.ts', 'typescript')
    ).lastrowid
    for b in bursts:
        db_conn.execute(
            "INSERT INTO bursts (session_id,ts,char_count,duration_ms,wpm,error_count,context) VALUES (?,?,?,?,?,?,?)",
            (sid, b['ts'], b['char_count'], b['duration_ms'], b['wpm'], 0, b['context'])
        )
    db_conn.commit()
    sig = compute_signals(db_conn)
    assert sig['fatigue_curve']['wpm_at_0min'] == 200
    assert sig['fatigue_curve']['wpm_at_15min'] == 150

def test_compute_signals_returns_all_fields(db_conn):
    sig = compute_signals(db_conn)
    for key in ['anxiety_bursts', 'exploration_sequences', 'stuck_moments',
                'difficulty_triggers', 'wpm_by_context', 'fatigue_curve']:
        assert key in sig
    fc = sig['fatigue_curve']
    for k in ['wpm_at_0min', 'wpm_at_15min', 'wpm_at_30min', 'wpm_at_60min', 'decay_rate']:
        assert k in fc
