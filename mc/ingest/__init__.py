"""Fetch every enabled feed, keep what fits the paper, and prepare it for tonight's planner.

run() is safe to call often (the scheduler runs it every few hours): feeds are fetched with conditional
GETs, articles already in the database are skipped, and only promising candidates get their full text
extracted.
"""
import calendar
import datetime
import json
import re
import time

from .. import config
from ..edition import ledger
from . import classify, extract, fetch, score as scoring, store, tone
from .text import canonical_url, clean_lead, plain, same_story, shorten, simhash, word_count


def _published(e):
    for k in ('published_parsed', 'updated_parsed', 'created_parsed'):
        t = e.get(k)
        if t:
            try:
                return datetime.datetime.fromtimestamp(calendar.timegm(t), datetime.timezone.utc).isoformat(timespec='seconds')
            except (OverflowError, ValueError):
                pass
    return fetch.now_iso()


def _feed_image(e):
    for key in ('media_content', 'media_thumbnail'):
        for m in e.get(key) or []:
            if m.get('url') and (m.get('medium') in (None, 'image') or 'image' in (m.get('type') or '')):
                return m['url'], plain(e.get('media_credit', [{}])[0].get('content', '') if e.get('media_credit') else '')
    for l in e.get('links') or []:
        if l.get('rel') == 'enclosure' and 'image' in (l.get('type') or ''):
            return l.get('href'), ''
    return None, ''


def _ledger_sets():
    L = ledger()['editions']
    urls = {canonical_url(u) for e in L for u in e.get('urls', [])}
    titles = [t for e in L[-120:] for t in e.get('titles', [])]
    return urls, titles


def add_entries(src, entries, log=print):
    """Insert new feed entries for one source. Returns the number added."""
    con = store.connect()
    added = 0
    for e in entries[:60]:
        link = (e.get('link') or '').strip()
        if not link.startswith('http'):
            continue
        url = canonical_url(link)
        if con.execute('SELECT 1 FROM items WHERE url=?', (url,)).fetchone():
            continue
        title = plain(e.get('title', ''))
        if not title:
            continue
        summary = clean_lead(plain(e.get('summary', '') or e.get('description', '')))
        if summary.lower().startswith(title.lower()):
            summary = summary[len(title):].lstrip(' .:\u2013\u2014-')
        content = ''
        if e.get('content'):
            content = max((c.get('value', '') for c in e['content']), key=len)
        if plain(summary) == plain(content):
            summary = ''
        if not summary and content:
            summary = shorten(plain(content), 60)
        img, credit = _feed_image(e) if src.images else (None, '')
        meta = dict(feed_content=content[:200000] if len(plain(content)) > 600 else '', rights=plain(e.get('rights', '')),
                    tags=[t.get('term') for t in e.get('tags', []) if t.get('term')][:12])
        con.execute('INSERT OR IGNORE INTO items(url, link, feed_url, source, title, summary, author, published, seen, image, '
                    'image_credit, license, tier, trust, meta, simhash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (url, link, src.url, src.name, title, summary[:2000], plain(e.get('author', ''))[:300], _published(e),
                     fetch.now_iso(), img, credit, src.license, src.use, src.trust, json.dumps(meta),
                     str(simhash(title + ' ' + summary))))
        added += 1
    con.commit()
    return added


def screen(log=print):
    """Filter new items: age, tone, already printed, duplicates; classify the survivors."""
    cfg = config.load()
    ed = cfg.editorial
    con = store.connect()
    used, used_titles = _ledger_sets()
    sources = {s.name: s for s in cfg.sources.feeds}
    recent = [store.item(r) for r in con.execute(
        "SELECT * FROM items WHERE status IN ('candidate','pinned','used','backlog') AND seen > ?",
        ((datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=45)).isoformat(),)).fetchall()]
    n_ok = n_rej = 0
    for r in con.execute("SELECT * FROM items WHERE status='new'").fetchall():
        it = store.item(r)
        reason = ''
        age = scoring._age_days(it['published'])
        if age > ed.recency_exception_days:
            reason = f'too old ({int(age)} days)'
        elif it['url'] in used:
            reason = 'already printed'
        elif any(same_story(it['title'], t) for t in used_titles):
            reason = 'same story as an earlier edition'
        ok, tval, why = tone.check(it['title'], it['summary'], ed)
        if not reason and not ok:
            reason = why
        if not reason:
            for other in recent:
                if other['id'] != it['id'] and same_story(it['title'], other['title'], it['summary'], other['summary']):
                    mine = (scoring.TIER.get(it['tier'], 1) * (it['trust'] or 1))
                    theirs = (scoring.TIER.get(other['tier'], 1) * (other['trust'] or 1))
                    if theirs >= mine:
                        reason = f'duplicate of #{other["id"]} ({other["source"]})'
                    elif other['status'] == 'candidate':
                        store.update(other['id'], status='rejected', reason=f'duplicate of #{it["id"]} ({it["source"]})')
                    break
        src = sources.get(it['source'])
        cat, conf, method = classify.classify(it['title'], it['summary'], '', default=src.category if src else None)
        fields = dict(tone=tval, category=cat, cat_score=conf, cat_method=method)
        if reason:
            fields.update(status='rejected', reason=reason)
            n_rej += 1
        elif not cat:
            fields.update(status='rejected', reason='no matching category')
            n_rej += 1
        else:
            fields.update(status='candidate', reason='')
            recent.append(dict(it, **fields))
            n_ok += 1
        store.update(it['id'], **fields)
    log(f'screened: {n_ok} candidates, {n_rej} rejected')
    return n_ok, n_rej


def extract_text(limit=40, log=print):
    """Fetch and extract full text for the most promising candidates that may need it."""
    cfg = config.load()
    ai = cfg.ai.provider != 'none' and cfg.ai.write_stories
    sources = {s.name: s for s in cfg.sources.feeds}
    tiers = ('full', 'verbatim', 'excerpt') if ai else ('full', 'verbatim')
    q = ','.join('?' * len(tiers))
    rows = store.items(f"status IN ('candidate','pinned') AND extracted=0 AND tier IN ({q})", tiers, order='seen DESC', limit=300)
    fb, recent = scoring.feedback_multipliers(), scoring.recent_categories()
    rows.sort(key=lambda it: -scoring.score(it, cfg, fb, recent))
    done = 0
    for it in rows[:limit]:
        src = sources.get(it['source'])
        meta = it.get('meta') or {}
        res = None
        if meta.get('feed_content'):
            res = extract.from_html(meta['feed_content'], it['link'], fragment=True)
        if (not res or res['words'] < 250) and (src is None or src.fetch_full_text):
            page = fetch.fetch_page(it['link'])
            if page:
                res2 = extract.from_html(page, it['link'])
                if res2['words'] > (res['words'] if res else 0):
                    res = res2
        fields = dict(extracted=1)
        if res and res['words']:
            fields.update(text=res['text'], blocks=res['blocks'], words=res['words'])
            imgs = [i for i in res['images'] if extract.credit_ok(i.get('caption', '') + ' ' + i.get('credit', ''))]
            if src and src.images and not it.get('image') and imgs:
                fields.update(image=imgs[0]['src'], image_credit=imgs[0].get('caption', ''))
            cat, conf, method = classify.classify(it['title'], it['summary'], res['text'], default=src.category if src else None)
            if cat:
                fields.update(category=cat, cat_score=conf, cat_method=method)
            ok, tval, why = tone.check(it['title'], (it['summary'] or '') + ' ' + res['text'][:600], cfg.editorial)
            if not ok:
                fields.update(status='rejected', reason=why)
        store.update(it['id'], **fields)
        done += 1
    log(f'extracted text for {done} articles')
    return done


def prune():
    cfg = config.load()
    cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=cfg.sources.keep_days)).isoformat()
    con = store.connect()
    n = con.execute("DELETE FROM items WHERE seen < ? AND status NOT IN ('used','pinned','backlog')", (cutoff,)).rowcount
    con.commit()
    return n


def run(log=print, extract_limit=40):
    """Fetch all enabled feeds, screen, extract, score. Returns stats."""
    cfg = config.activate()
    con = store.connect()
    t0 = time.time()
    stats = dict(feeds=0, ok=0, errors=0, added=0)
    for src in [s for s in cfg.sources.feeds if s.enabled]:
        stats['feeds'] += 1
        row = con.execute('SELECT * FROM feeds WHERE url=?', (src.url,)).fetchone()
        etag, lm = (row['etag'], row['last_modified']) if row else (None, None)
        r = fetch.fetch_feed(src.url, etag, lm)
        now = fetch.now_iso()
        if r.get('error'):
            stats['errors'] += 1
            con.execute('INSERT INTO feeds(url, name, last_fetch, last_error, fail_count) VALUES(?,?,?,?,1) '
                        'ON CONFLICT(url) DO UPDATE SET name=excluded.name, last_fetch=excluded.last_fetch, '
                        'last_error=excluded.last_error, fail_count=fail_count+1', (src.url, src.name, now, r['error']))
            log(f'  ! {src.name}: {r["error"]}')
        else:
            n = add_entries(src, r['entries'], log)
            stats['ok'] += 1
            stats['added'] += n
            con.execute('INSERT INTO feeds(url, name, etag, last_modified, last_fetch, last_ok, last_error, items_seen, new_items, fail_count) '
                        'VALUES(?,?,?,?,?,?,NULL,?,?,0) ON CONFLICT(url) DO UPDATE SET name=excluded.name, etag=excluded.etag, '
                        'last_modified=excluded.last_modified, last_fetch=excluded.last_fetch, last_ok=excluded.last_ok, '
                        'last_error=NULL, items_seen=excluded.items_seen, new_items=excluded.new_items, fail_count=0',
                        (src.url, src.name, r.get('etag'), r.get('last_modified'), now, now, len(r['entries']), n))
            log(f'  {src.name}: {len(r["entries"])} items, {n} new' + (' (not modified)' if r['status'] == 304 else ''))
        con.commit()
    stats['candidates'], stats['rejected'] = screen(log)
    stats['extracted'] = extract_text(extract_limit, log)
    try:
        classify.train()
    except Exception as e:  # noqa: BLE001
        log(f'classifier training skipped: {e}')
    scoring.rescore_all(log)
    stats['pruned'] = prune()
    stats['seconds'] = round(time.time() - t0, 1)
    store.kv_set('last_ingest', dict(stats, at=fetch.now_iso()))
    return stats
