import { _resetForTest } from '../../src/db';
import Database from 'better-sqlite3';

export function freshDb(): Database.Database {
  return _resetForTest();
}
