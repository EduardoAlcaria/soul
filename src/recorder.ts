import { db } from './db';

export interface KeyEvent {
  ts: number;
  char: string;
  isDelete: boolean;
  context: 'comment' | 'identifier' | 'operator' | 'string' | 'keyword' | 'other';
  line: number;
  col: number;
}

const PAUSE_THRESHOLD_MS = 1000;
const MICRO_PAUSE_MS = 300;

export class Recorder {
  private sessionId: number | null = null;
  private events: KeyEvent[] = [];
  private lastTs = 0;
  private burstStart = 0;
  private burstChars = 0;
  private burstErrors = 0;
  private burstContext: string = 'other';

  start(file: string, language: string): void {
    const now = Date.now();
    const result = db().prepare(
      'INSERT INTO sessions (started_at, file, language) VALUES (?, ?, ?)'
    ).run(now, file, language);
    this.sessionId = Number(result.lastInsertRowid);
    this.lastTs = now;
    this.burstStart = 0;
    this.burstChars = 0;
    this.burstErrors = 0;
    this.events = [];
  }

  record(ev: KeyEvent): void {
    if (!this.sessionId) { return; }

    if (this.burstStart === 0) { this.burstStart = ev.ts; }

    const gap = ev.ts - this.lastTs;

    if (gap >= PAUSE_THRESHOLD_MS && this.lastTs > 0) {
      this.flushBurst(ev.ts - gap);
      db().prepare(
        'INSERT INTO pauses (session_id, ts, duration_ms) VALUES (?, ?, ?)'
      ).run(this.sessionId, this.lastTs, gap);
      this.burstStart = ev.ts;
      this.burstChars = 0;
      this.burstErrors = 0;
    } else if (gap >= MICRO_PAUSE_MS && this.lastTs > 0) {
      this.flushBurst(ev.ts - gap);
      this.burstStart = ev.ts;
      this.burstChars = 0;
      this.burstErrors = 0;
    }

    db().prepare(
      `INSERT INTO keystrokes (session_id, ts, event_type, char, is_delete, context, line, col)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
    ).run(
      this.sessionId, ev.ts, 'key', ev.char,
      ev.isDelete ? 1 : 0, ev.context, ev.line, ev.col
    );

    if (ev.isDelete) { this.burstErrors++; } else { this.burstChars++; }
    this.burstContext = ev.context;
    this.lastTs = ev.ts;
    this.events.push(ev);
  }

  stop(): number | null {
    if (!this.sessionId) { return null; }
    this.flushBurst(this.lastTs);
    this.burstContext = 'other';
    db().prepare('UPDATE sessions SET ended_at = ? WHERE id = ?')
      .run(Date.now(), this.sessionId);
    const id = this.sessionId;
    this.sessionId = null;
    return id;
  }

  private flushBurst(endTs: number): void {
    if (!this.sessionId || this.burstChars === 0) { return; }
    const duration = endTs - this.burstStart;
    if (duration <= 0) { return; }
    const wpm = (this.burstChars / 5) / (duration / 60000);
    db().prepare(
      `INSERT INTO bursts (session_id, ts, char_count, duration_ms, wpm, error_count, context)
       VALUES (?, ?, ?, ?, ?, ?, ?)`
    ).run(this.sessionId, this.burstStart, this.burstChars, duration, wpm, this.burstErrors, this.burstContext);
  }
}

export const recorder = new Recorder();
