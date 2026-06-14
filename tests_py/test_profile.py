import time
import pytest
from soul_analyzer.profile import build_profile

BASE = 4_000_000

def seed_minimal(conn):
    sid = conn.execute(
        "INSERT INTO sessions (started_at, ended_at, file, language) VALUES (?,?,?,?)",
        (BASE, BASE + 300_000, 'f.ts', 'typescript')
    ).lastrowid
    for i in range(10):
        conn.execute(
            "INSERT INTO keystrokes (session_id,ts,event_type,char,is_delete,context,line,col) VALUES (?,?,?,?,?,?,?,?)",
            (sid, BASE + i * 100, 'key', 'a', 0, 'identifier', 1, i)
        )
    conn.execute(
        "INSERT INTO bursts (session_id,ts,char_count,duration_ms,wpm,error_count,context) VALUES (?,?,?,?,?,?,?)",
        (sid, BASE + 200, 10, 450, 180.0, 0, 'identifier')
    )
    conn.commit()

def test_build_profile_has_all_keys(db_conn):
    seed_minimal(db_conn)
    p = build_profile(db_conn)
    required = [
        'sessions_analyzed', 'total_keystrokes', 'velocity', 'pauses',
        'digraph_latencies', 'iki', 'wpm_by_context', 'fatigue_curve',
        'cognitive_signals', 'cognitive_states', 'hmm_transitions',
        'difficulty_triggers', 'generated_at',
    ]
    for key in required:
        assert key in p, f"Missing key: {key}"

def test_build_profile_velocity_populated(db_conn):
    seed_minimal(db_conn)
    p = build_profile(db_conn)
    assert p['velocity']['wpm_mean'] > 0

def test_build_profile_sessions_analyzed(db_conn):
    seed_minimal(db_conn)
    p = build_profile(db_conn)
    assert p['sessions_analyzed'] == 1

def test_build_profile_cognitive_states_sum_to_one(db_conn):
    seed_minimal(db_conn)
    p = build_profile(db_conn)
    cs = p['cognitive_states']
    total = cs['flow_pct'] + cs['anxious_pct'] + cs['exploring_pct'] + cs['stuck_pct']
    assert abs(total - 1.0) < 0.01

def test_build_profile_generated_at_recent(db_conn):
    seed_minimal(db_conn)
    before = int(time.time() * 1000)
    p = build_profile(db_conn)
    after = int(time.time() * 1000)
    assert before <= p['generated_at'] <= after

def test_build_profile_empty_db(db_conn):
    p = build_profile(db_conn)
    assert p['sessions_analyzed'] == 0
    assert p['total_keystrokes'] == 0
    assert p['velocity']['wpm_mean'] == 0
