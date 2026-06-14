import pytest
from soul_analyzer.stats import compute_iki_stats, compute_digraph_latencies, compute_wpm_by_context, compute_pause_stats, compute_velocity

def seed_session(conn, keystrokes, bursts=None, pauses=None):
    start = keystrokes[0]['ts']
    end = keystrokes[-1]['ts'] + 100
    sid = conn.execute(
        "INSERT INTO sessions (started_at, ended_at, file, language) VALUES (?,?,?,?)",
        (start, end, 'f.ts', 'typescript')
    ).lastrowid
    for k in keystrokes:
        conn.execute(
            "INSERT INTO keystrokes (session_id,ts,event_type,char,is_delete,context,line,col) VALUES (?,?,?,?,?,?,?,?)",
            (sid, k['ts'], 'key', k['char'], k.get('is_delete', 0), k.get('context', 'identifier'), 1, 0)
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

BASE = 2_000_000

def test_iki_overall_p50_is_median(db_conn):
    keys = [
        {'ts': BASE,       'char': 'a'},
        {'ts': BASE + 100, 'char': 'b'},  # gap 100
        {'ts': BASE + 300, 'char': 'c'},  # gap 200
        {'ts': BASE + 600, 'char': 'd'},  # gap 300
    ]
    seed_session(db_conn, keys)
    stats = compute_iki_stats(db_conn)
    # gaps: [100, 200, 300] → median = 200
    assert stats['overall']['p50'] == 200

def test_iki_by_context_groups(db_conn):
    keys = [
        {'ts': BASE,       'char': 'a', 'context': 'comment'},
        {'ts': BASE + 200, 'char': 'b', 'context': 'comment'},    # gap 200
        {'ts': BASE + 250, 'char': 'c', 'context': 'identifier'},
        {'ts': BASE + 350, 'char': 'd', 'context': 'identifier'},  # gap 100
    ]
    seed_session(db_conn, keys)
    stats = compute_iki_stats(db_conn)
    assert 'comment' in stats['by_context']
    assert 'identifier' in stats['by_context']
    assert stats['by_context']['comment']['p50'] > stats['by_context']['identifier']['p50']

def test_digraph_latencies_min_count(db_conn):
    # Need at least 5 occurrences of a pair to appear
    keys = [{'ts': BASE + i * 100, 'char': 'a' if i % 2 == 0 else 'b'} for i in range(12)]
    seed_session(db_conn, keys)
    digraphs = compute_digraph_latencies(db_conn)
    # 'ab' and 'ba' should appear (6 occurrences each)
    pairs = {d['pair'] for d in digraphs}
    assert 'ab' in pairs or 'ba' in pairs

def test_digraph_below_min_count_excluded(db_conn):
    # Only 3 occurrences of 'xy' — should be excluded
    keys = [
        {'ts': BASE, 'char': 'x'}, {'ts': BASE + 100, 'char': 'y'},
        {'ts': BASE + 300, 'char': 'x'}, {'ts': BASE + 400, 'char': 'y'},
        {'ts': BASE + 600, 'char': 'x'}, {'ts': BASE + 700, 'char': 'y'},
    ]
    seed_session(db_conn, keys)
    digraphs = compute_digraph_latencies(db_conn)
    pairs = {d['pair'] for d in digraphs}
    assert 'xy' not in pairs  # only 3 occurrences < 5

def test_wpm_by_context(db_conn):
    keys = [{'ts': BASE, 'char': 'a'}]
    bursts = [
        {'ts': BASE + 100, 'wpm': 200, 'char_count': 10, 'duration_ms': 300, 'context': 'identifier'},
        {'ts': BASE + 500, 'wpm': 80,  'char_count': 4,  'duration_ms': 300, 'context': 'operator'},
    ]
    seed_session(db_conn, keys, bursts=bursts)
    wpm = compute_wpm_by_context(db_conn)
    assert wpm['identifier'] == 200
    assert wpm['operator'] == 80

def test_pause_stats_categories(db_conn):
    keys = [{'ts': BASE, 'char': 'a'}]
    pauses = [
        {'ts': BASE + 100, 'duration_ms': 500},    # micro
        {'ts': BASE + 700, 'duration_ms': 2000},   # think
        {'ts': BASE + 3000, 'duration_ms': 8000},  # deep
        {'ts': BASE + 12000, 'duration_ms': 20000},# stuck
    ]
    seed_session(db_conn, keys, pauses=pauses)
    stats = compute_pause_stats(db_conn)
    assert stats['micro_p50'] == 500
    assert stats['think_p50'] == 2000
    assert stats['deep_count'] == 1
    assert stats['stuck_count'] == 1

def test_velocity_empty_db(db_conn):
    v = compute_velocity(db_conn)
    assert v['wpm_mean'] == 0
    assert v['wpm_p90'] == 0
    assert v['error_rate'] == 0.0
