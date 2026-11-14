"""The article database (<data>/mc.db, SQLite).

feeds     one row per feed URL: conditional-GET validators, last result, error count
items     every article seen: metadata, extracted text, category, tone, score, status
feedback  thumbs up/down from the reader, per story
kv        small blobs (the learned classifier, last ingest time, ...)

Item status: new -> candidate (passed filters) | rejected (with a reason) -> used (printed) ;
pinned / killed are editor's-desk overrides; backlog marks good evergreen items saved for thin days.
"""
import json
import sqlite3
import threading

from .. import paths

SCHEMA = """
CREATE TABLE IF NOT EXISTS feeds (
  url TEXT PRIMARY KEY, name TEXT, etag TEXT, last_modified TEXT, last_fetch TEXT, last_ok TEXT,
  last_error TEXT, items_seen INTEGER DEFAULT 0, new_items INTEGER DEFAULT 0, fail_count INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY,
  url TEXT UNIQUE,
  link TEXT,
  feed_url TEXT, source TEXT,
  title TEXT, summary TEXT, author TEXT,
  published TEXT, seen TEXT,
  text TEXT, blocks TEXT, words INTEGER DEFAULT 0, extracted INTEGER DEFAULT 0,
  image TEXT, image_credit TEXT,
  category TEXT, cat_score REAL, cat_method TEXT,
  tone REAL, reason TEXT,
  simhash TEXT, cluster INTEGER,
  score REAL DEFAULT 0, status TEXT DEFAULT 'new', used_in TEXT,
  license TEXT, tier TEXT, trust REAL DEFAULT 1,
  origin TEXT DEFAULT 'feed',
  meta TEXT
);
CREATE INDEX IF NOT EXISTS items_status ON items(status);
CREATE INDEX IF NOT EXISTS items_published ON items(published);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY, at TEXT, edition TEXT, story_id TEXT, url TEXT, source TEXT, category TEXT, vote INTEGER,
  UNIQUE(edition, story_id)
);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
"""

_local = threading.local()


def connect(path=None):
    path = path or paths.db_file()
    key = f'db_{path}'
    con = getattr(_local, key, None)
    if con is None:
        con = sqlite3.connect(path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA journal_mode=WAL')
        con.execute('PRAGMA busy_timeout=30000')
        con.executescript(SCHEMA)
        setattr(_local, key, con)
    return con


def kv_get(k, default=None):
    r = connect().execute('SELECT v FROM kv WHERE k=?', (k,)).fetchone()
    return json.loads(r['v']) if r else default


def kv_set(k, v):
    con = connect()
    con.execute('INSERT INTO kv(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v', (k, json.dumps(v)))
    con.commit()


def item(row):
    """sqlite Row -> dict with JSON columns decoded."""
    d = dict(row)
    for k in ('blocks', 'meta'):
        if d.get(k):
            try:
                d[k] = json.loads(d[k])
            except (TypeError, json.JSONDecodeError):
                d[k] = None
    d['meta'] = d.get('meta') or {}
    return d


def items(where='1=1', args=(), order='score DESC', limit=None):
    sql = f'SELECT * FROM items WHERE {where} ORDER BY {order}' + (f' LIMIT {int(limit)}' if limit else '')
    return [item(r) for r in connect().execute(sql, args).fetchall()]


def update(item_id, **fields):
    if not fields:
        return
    for k in ('blocks', 'meta'):
        if k in fields and not isinstance(fields[k], (str, type(None))):
            fields[k] = json.dumps(fields[k])
    cols = ', '.join(f'{k}=?' for k in fields)
    con = connect()
    con.execute(f'UPDATE items SET {cols} WHERE id=?', (*fields.values(), item_id))
    con.commit()


def set_status(urls, status, edition=None):
    con = connect()
    for u in urls:
        con.execute('UPDATE items SET status=?, used_in=COALESCE(?, used_in) WHERE url=? OR link=?', (status, edition, u, u))
    con.commit()


def vote(edition, story_id, url, source, category, value, at):
    con = connect()
    con.execute('INSERT INTO feedback(at, edition, story_id, url, source, category, vote) VALUES(?,?,?,?,?,?,?) '
                'ON CONFLICT(edition, story_id) DO UPDATE SET vote=excluded.vote, at=excluded.at',
                (at, edition, story_id, url, source, category, value))
    con.commit()


def votes():
    return [dict(r) for r in connect().execute('SELECT * FROM feedback ORDER BY at').fetchall()]
