import { freshDb } from './helpers/memdb';
import { Recorder } from '../src/recorder';

const BASE_TS = 1_000_000;

function makeRecorder(): Recorder {
  freshDb();
  return new Recorder();
}

test('burst flushed with correct context', () => {
  const rec = makeRecorder();
  const d = require('../src/db').db();
  rec.start('test.ts', 'typescript');
  for (let i = 0; i < 10; i++) {
    rec.record({ ts: BASE_TS + i * 50, char: 'a', isDelete: false, context: 'identifier', line: 1, col: i });
  }
  rec.stop();
  const burst = d.prepare('SELECT context, wpm FROM bursts LIMIT 1').get() as { context: string; wpm: number };
  expect(burst).toBeDefined();
  expect(burst.context).toBe('identifier');
  expect(burst.wpm).toBeGreaterThan(0);
});

test('pause recorded when gap >= 1000ms', () => {
  freshDb();
  const d = require('../src/db').db();
  const rec = new Recorder();
  rec.start('test.ts', 'typescript');
  rec.record({ ts: BASE_TS, char: 'a', isDelete: false, context: 'other', line: 1, col: 0 });
  rec.record({ ts: BASE_TS + 1500, char: 'b', isDelete: false, context: 'other', line: 1, col: 1 });
  rec.stop();
  const pause = d.prepare('SELECT duration_ms FROM pauses LIMIT 1').get() as { duration_ms: number };
  expect(pause).toBeDefined();
  expect(pause.duration_ms).toBe(1500);
});

test('delete increments error count', () => {
  freshDb();
  const d = require('../src/db').db();
  const rec = new Recorder();
  rec.start('test.ts', 'typescript');
  for (let i = 0; i < 5; i++) {
    rec.record({ ts: BASE_TS + i * 50, char: 'a', isDelete: false, context: 'identifier', line: 1, col: i });
  }
  rec.record({ ts: BASE_TS + 250, char: '', isDelete: true, context: 'identifier', line: 1, col: 4 });
  rec.stop();
  const burst = d.prepare('SELECT error_count FROM bursts LIMIT 1').get() as { error_count: number };
  expect(burst.error_count).toBe(1);
});

test('stop returns session id', () => {
  freshDb();
  const rec = new Recorder();
  rec.start('test.ts', 'typescript');
  const id = rec.stop();
  expect(typeof id).toBe('number');
  expect(id).toBeGreaterThan(0);
});
