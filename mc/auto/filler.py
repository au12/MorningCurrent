"""Filler briefs that always exist: Wikipedia's "On this day" events and today's featured article
(CC BY-SA 4.0, credited on each item). The fitter drops them into short columns like reserve briefs."""
import datetime
import json
import re

from .. import config
from ..ingest import fetch, tone
from ..ingest.text import esc, plain, shorten

API = 'https://en.wikipedia.org/api/rest_v1/feed/featured/{y}/{m:02d}/{d:02d}'
CREDIT = 'Wikipedia, CC BY-SA 4.0'
# history is full of wars and coups; only gentle events make the paper
STRICT = re.compile(r'(?i)\b(party|president|presidential|minister|election|elected|government|parliament|king|queen|emperor|'
                    r'empress|pope|army|armies|battle|war|wars|troops|soldier|kill|killed|kills|die|dies|died|death|dead|'
                    r'assassinat\w*|coup|revolution\w*|independence|treaty|protest\w*|riot\w*|massacre|bomb\w*|attack\w*|'
                    r'invad\w*|invasion|communist|secretary|senate|congress|court|sentenced|executed|disaster|earthquake|'
                    r'hurricane|crash\w*|sank|sinks|fire|terror\w*|shot|shooting|nazi\w*|genocide|occupation|surrender\w*|'
                    r'annex\w*|declar\w* war|regime|dictator\w*|prison\w*|slave\w*|flood\w*|plague|epidemic|famine)\b')
GENTLE = re.compile(r'(?i)\b(first|launch\w*|discover\w*|open\w*|publish\w*|premiere\w*|record\w*|invent\w*|patent\w*|'
                    r'found\w*|complet\w*|orbit\w*|lands?|landed|flight|flies|flew|debut\w*|unveil\w*|demonstrat\w*|'
                    r'perform\w*|broadcast\w*|observ\w*|named|establish\w*)\b')


def featured(date):
    try:
        status, body, _, _ = fetch.get(API.format(y=date.year, m=date.month, d=date.day), accept='application/json')
        if status >= 400:
            return {}
        return json.loads(body)
    except Exception:  # noqa: BLE001 - filler is optional
        return {}


def wikipedia_briefs(date, n_days=3):
    """Up to `n_days` gentle "On this day" items plus the featured article, as brief dicts."""
    cfg = config.load()
    if not cfg.editorial.filler_wikipedia:
        return []
    data = featured(date)
    out = []
    events = sorted(data.get('onthisday', []), key=lambda e: -len(e.get('pages', [])))
    for e in events:
        text = plain(e.get('text', ''))
        ok, _, _ = tone.check(text, '', cfg.editorial)
        if not ok or not e.get('pages') or STRICT.search(text) or not GENTLE.search(text):
            continue
        page = e['pages'][0]
        url = page.get('content_urls', {}).get('desktop', {}).get('page')
        if not url:
            continue
        out.append(dict(head=esc(f'On This Day, {e.get("year")}'), text=esc(shorten(text[:1].upper() + text[1:], 55)), src=url,
                        category='History & Everyday Things', credit=CREDIT, filler=True))
        if len(out) >= n_days:
            break
    tfa = data.get('tfa')
    if tfa and tfa.get('extract'):
        url = tfa.get('content_urls', {}).get('desktop', {}).get('page')
        title = plain(tfa.get('normalizedtitle') or tfa.get('title', '')).replace('_', ' ')
        ok, _, _ = tone.check(title, tfa.get('extract', ''), cfg.editorial)
        if ok and url:
            out.append(dict(head=esc(f'From the Encyclopedia: {title}'), text=esc(shorten(plain(tfa['extract']), 60)), src=url,
                            category=None, credit=CREDIT, filler=True))
    return out
