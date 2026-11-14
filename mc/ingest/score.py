"""Score candidates: how much a story deserves a place in tomorrow's paper.

score = recency x category weight x source trust x license tier x length fit x substance x tone
        x novelty (vs. the last two papers) x reader feedback x classifier confidence
All factors are near 1.0, so the score reads as a relative preference, not a probability.
"""
import datetime
import json
import math
import re

from .. import config
from ..edition import ledger
from . import store

TIER = {'full': 1.15, 'verbatim': 1.1, 'excerpt': 1.0, 'headline': 0.8}


def _age_days(published):
    try:
        t = datetime.datetime.fromisoformat(published)
    except (TypeError, ValueError):
        return 7.0
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    return max(0.0, (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds() / 86400)


def feedback_multipliers():
    """{('source', name): m, ('category', name): m} from the reader's thumbs, recent votes counting more."""
    now = datetime.datetime.now(datetime.timezone.utc)
    acc = {}
    for v in store.votes():
        try:
            age = (now - datetime.datetime.fromisoformat(v['at'])).days
        except (TypeError, ValueError):
            age = 0
        w = 1.0 if age < 90 else 0.5
        for kind in ('source', 'category'):
            if v.get(kind):
                acc[(kind, v[kind])] = acc.get((kind, v[kind]), 0) + w * (1 if v['vote'] > 0 else -1)
    return {k: max(0.6, min(1.4, 1 + 0.08 * s)) for k, s in acc.items()}


def recent_categories(n=2):
    eds = [e for e in ledger()['editions'] if isinstance(e.get('number'), int)][-n:]
    lead = {e.get('lead_category') for e in eds if e.get('lead_category')}
    spread = {e.get('spread_category') for e in eds if e.get('spread_category')}
    allc = {c for e in eds for c in e.get('categories', [])}
    return lead, spread, allc


def score(it, cfg=None, fb=None, recent=None):
    cfg = cfg or config.load()
    ed = cfg.editorial
    fb = fb if fb is not None else feedback_multipliers()
    recent = recent or recent_categories()
    age = _age_days(it.get('published'))
    if age > ed.recency_exception_days:
        return 0.0
    rec = math.exp(-age / (ed.recency_days / 2.2))
    if age > ed.recency_days:
        rec *= 0.35
    cat = ed.category(it.get('category') or '')
    cw = (cat.weight if cat and cat.enabled else 0.5)
    if it.get('category') in ed.favorite_names():
        cw *= 1.25
    tier = it.get('tier') or 'excerpt'
    words = it.get('words') or 0
    if tier in ('full', 'verbatim'):
        length = 1.0 if 350 <= words <= 3500 else (0.75 if words >= 150 else 0.55)
    else:
        sw = len((it.get('summary') or '').split())
        length = 1.0 if sw >= 25 else 0.7
    text = it.get('text') or it.get('summary') or ''
    nums = len(re.findall(r'\d', text[:4000]))
    quote = 1.08 if re.search(r'[“"][^”"]{20,}[”"]', text[:6000]) else 1.0
    substance = (1 + 0.025 * min(nums, 12)) * quote
    from .tone import lean
    tone = (1 + 0.25 * max(-0.7, min(1.0, it.get('tone') or 0))) * lean(it.get('title'), it.get('summary'), ed)
    lead_c, spread_c, all_c = recent
    novelty = 0.92 if it.get('category') in all_c else 1.0
    m = fb.get(('source', it.get('source')), 1.0) * fb.get(('category', it.get('category')), 1.0)
    conf = 0.85 + 0.15 * (it.get('cat_score') or 0)
    origin = 1.2 if it.get('origin') == 'ai' else 1.0       # an AI editor's pick (research mode)
    s = rec * cw * (it.get('trust') or 1.0) * TIER.get(tier, 1.0) * length * substance * tone * novelty * m * conf * origin
    return round(s, 4)


def rescore_all(log=None):
    cfg = config.load()
    fb, recent = feedback_multipliers(), recent_categories()
    con = store.connect()
    n = 0
    for r in con.execute("SELECT * FROM items WHERE status IN ('candidate', 'pinned', 'backlog')").fetchall():
        it = store.item(r)
        s = score(it, cfg, fb, recent)
        con.execute('UPDATE items SET score=? WHERE id=?', (s, it['id']))
        n += 1
    con.commit()
    if log:
        log(f'scored {n} candidates')
    return n
