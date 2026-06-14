import json
import sys
from pathlib import Path

SOUL_DIR = Path.home() / '.soul'
PROFILE_PATH = SOUL_DIR / 'profile.json'

C = {
    'reset': '\x1b[0m', 'bold': '\x1b[1m', 'dim': '\x1b[2m',
    'cyan': '\x1b[36m', 'green': '\x1b[32m', 'yellow': '\x1b[33m',
    'red': '\x1b[31m', 'blue': '\x1b[34m', 'magenta': '\x1b[35m',
}


def bar(value: float, max_val: float, width: int = 20) -> str:
    if max_val == 0:
        return C['dim'] + '░' * width + C['reset']
    filled = round((value / max_val) * width)
    return C['cyan'] + '█' * filled + C['dim'] + '░' * (width - filled) + C['reset']


def pct(n: float) -> str:
    return f"{n * 100:.1f}%"


def cmd_extract() -> None:
    from .db import connect
    from .profile import build_profile

    conn = connect()
    profile = build_profile(conn)
    conn.close()

    SOUL_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2))

    print(f"Profile written -> {PROFILE_PATH}")
    print(f"Sessions: {profile['sessions_analyzed']} | Keystrokes: {profile['total_keystrokes']}")
    print(f"WPM avg: {profile['velocity']['wpm_mean']} | Error rate: {profile['velocity']['error_rate'] * 100:.1f}%")
    cs = profile['cognitive_states']
    print(f"Flow: {pct(cs['flow_pct'])} | Anxious: {pct(cs['anxious_pct'])}")


def cmd_view() -> None:
    if not PROFILE_PATH.exists():
        print(f"No profile at {PROFILE_PATH}. Run: python -m soul_analyzer extract", file=sys.stderr)
        sys.exit(1)

    p = json.loads(PROFILE_PATH.read_text())

    print()
    print(C['bold'] + C['magenta'] + '╔══════════════════════════════════════╗' + C['reset'])
    print(C['bold'] + C['magenta'] + '║        SOUL -- BRAIN PROFILE          ║' + C['reset'])
    print(C['bold'] + C['magenta'] + '╚══════════════════════════════════════╝' + C['reset'])
    print()

    print(C['bold'] + '── Velocity ──────────────────────────────' + C['reset'])
    v = p['velocity']
    print(f"  WPM mean   {C['green']}{v['wpm_mean']}{C['reset']}")
    print(f"  WPM p90    {C['green']}{v['wpm_p90']}{C['reset']}")
    print(f"  Error rate {C['yellow']}{v['error_rate'] * 100:.1f}%{C['reset']}")
    print()

    print(C['bold'] + '── Cognitive States (HMM) ────────────────' + C['reset'])
    cs = p['cognitive_states']
    max_pct = max(cs.values()) or 0.01
    print(f"  FLOW       {bar(cs['flow_pct'], max_pct)} {pct(cs['flow_pct'])}")
    print(f"  THINKING   {bar(cs['stuck_pct'], max_pct)} {pct(cs['stuck_pct'])}")
    print(f"  ANXIOUS    {bar(cs['anxious_pct'], max_pct)} {pct(cs['anxious_pct'])}")
    print(f"  EXPLORING  {bar(cs['exploring_pct'], max_pct)} {pct(cs['exploring_pct'])}")
    print()

    sig = p.get('cognitive_signals', {})
    print(C['bold'] + '── Cognitive Signals ─────────────────────' + C['reset'])
    print(f"  Anxiety bursts       {C['red']}{sig.get('anxiety_bursts', 0)}{C['reset']}")
    print(f"  Exploration seqs     {C['blue']}{sig.get('exploration_sequences', 0)}{C['reset']}")
    print(f"  Stuck moments        {C['yellow']}{sig.get('stuck_moments', 0)}{C['reset']}")
    print()

    wbc = p.get('wpm_by_context', {})
    if wbc:
        print(C['bold'] + '── WPM by Context ────────────────────────' + C['reset'])
        max_wpm = max(wbc.values()) or 1
        for ctx, wpm in sorted(wbc.items(), key=lambda x: -x[1]):
            print(f"  {ctx:<12} {bar(wpm, max_wpm)} {wpm} wpm")
        print()

    fc = p.get('fatigue_curve', {})
    if fc.get('wpm_at_0min') or fc.get('wpm_at_15min'):
        print(C['bold'] + '── Fatigue Curve ─────────────────────────' + C['reset'])
        print(f"  0-15min   {C['green']}{fc.get('wpm_at_0min', 0)}{C['reset']} wpm")
        print(f"  15-30min  {fc.get('wpm_at_15min', 0)} wpm")
        print(f"  30-60min  {fc.get('wpm_at_30min', 0)} wpm")
        print(f"  60min+    {C['dim']}{fc.get('wpm_at_60min', 0)}{C['reset']} wpm")
        dr = fc.get('decay_rate', 0)
        color = C['red'] if dr > 0 else C['green']
        sign = '-' if dr > 0 else '+'
        print(f"  Decay     {color}{sign}{abs(dr)}{C['reset']} wpm/hr")
        print()

    dt = p.get('difficulty_triggers', [])
    if dt:
        print(C['bold'] + '── Difficulty Triggers ───────────────────' + C['reset'])
        print(f"  {C['red']}{', '.join(dt)}{C['reset']}")
        print()

    iki = p.get('iki', {}).get('overall', {})
    if any(iki.values()):
        print(C['bold'] + '── IKI Distribution ──────────────────────' + C['reset'])
        print(f"  p25={iki.get('p25',0)}ms  p50={iki.get('p50',0)}ms  p75={iki.get('p75',0)}ms  p90={iki.get('p90',0)}ms")
        print()

    trans = p.get('hmm_transitions', {})
    if trans:
        print(C['bold'] + '── Top HMM Transitions ───────────────────' + C['reset'])
        for pair, prob in sorted(trans.items(), key=lambda x: -x[1])[:5]:
            print(f"  {pair:<22} {pct(prob)}")
        print()

    digraphs = p.get('digraph_latencies', [])
    if digraphs:
        print(C['bold'] + '── Top Digraph Latencies ─────────────────' + C['reset'])
        for dg in digraphs[:10]:
            print(f"  {dg['pair']:<5} p50={dg['p50']}ms  p90={dg['p90']}ms  n={dg['count']}")
        print()

    print(C['dim'] + f"Sessions: {p['sessions_analyzed']} | Keystrokes: {p['total_keystrokes']} | Generated: {p['generated_at']}" + C['reset'])
    print()


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'extract':
        cmd_extract()
    elif cmd == 'view':
        cmd_view()
    else:
        print('soul_analyzer -- Eduardo brain profiler')
        print('Commands:')
        print('  python -m soul_analyzer extract  -- analyze DB -> ~/.soul/profile.json')
        print('  python -m soul_analyzer view     -- pretty-print profile.json')


if __name__ == '__main__':
    main()
