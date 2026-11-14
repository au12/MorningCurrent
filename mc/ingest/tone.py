"""Keep the paper good-natured: a blocklist (crime, disaster, politics, war, sensational and business gloom)
plus a lexicon sentiment score (VADER). Every rejection carries a reason the editor's desk can show."""
import re
from functools import lru_cache

from .. import config


def _pattern(terms):
    parts = []
    for t in terms:
        t = t.strip().lower()
        if not t:
            continue
        if t.endswith('*'):
            parts.append(r'\b' + re.escape(t[:-1]) + r'\w*')
        else:
            parts.append(r'\b' + re.escape(t) + r'\b')
    return re.compile('|'.join(parts), re.I) if parts else None


@lru_cache(maxsize=4)
def _compiled(block, allow):
    return _pattern(block), _pattern(allow)


_vader = None


def sentiment(text):
    """VADER compound score in [-1, 1] (0 when the analyzer isn't installed)."""
    global _vader
    if _vader is None:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            _vader = SentimentIntensityAnalyzer()
        except ImportError:
            _vader = False
    if not _vader:
        return 0.0
    return _vader.polarity_scores(text or '')['compound']


def lean(title, summary='', ed=None):
    """A multiplier around 1.0 from the editorial up/down word lists (headline counts double)."""
    ed = ed or config.load().editorial
    down, up = _compiled(tuple(ed.downweight), tuple(ed.upweight))
    t, s = title or '', (summary or '')[:600]
    d = (2 * len(down.findall(t)) + len(down.findall(s))) if down else 0
    u = (2 * len(up.findall(t)) + len(up.findall(s))) if up else 0
    return max(0.55, min(1.3, (0.9 ** min(d, 6)) * (1.04 ** min(u, 6))))


def check(title, summary='', ed=None):
    """Returns (ok, tone, reason). Headline hits on the blocklist reject; summary hits only lower the tone."""
    ed = ed or config.load().editorial
    block, allow = _compiled(tuple(ed.blocklist), tuple(ed.allowlist))
    t = title or ''
    clean_t = allow.sub(' ', t) if allow else t
    clean_s = allow.sub(' ', summary or '') if allow else (summary or '')
    if block:
        m = block.search(clean_t)
        if m:
            return False, -1.0, f'headline mentions "{m.group(0)}"'
    tone = sentiment(t)
    first = re.split(r'(?<=[.!?])\s', clean_s.strip(), maxsplit=1)[0] if clean_s else ''
    hits = len(block.findall(clean_s)) if block else 0
    if block and first and block.search(first):
        hits += 1
    if tone < ed.tone_threshold:
        return False, tone, f'negative headline (tone {tone:+.2f})'
    if hits >= 3:
        return False, tone, f'summary dwells on blocked topics ({hits} mentions)'
    return True, round(tone - 0.15 * hits, 3), ''
