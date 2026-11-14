"""Text utilities shared by ingest, the automatic writer and the AI verifier.

Everything that comes from a feed or web page is untrusted: `plain()` strips markup and `esc()`
escapes text before it goes into the paper's HTML, so a feed can never inject markup or scripts.
"""
import hashlib
import html
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# ------------------------------------------------------------------ cleaning
_WS = re.compile(r'\s+')
_TAG = re.compile(r'<[^>]+>')


def plain(s):
    """Markup -> plain text: tags dropped, entities decoded, whitespace collapsed."""
    if not s:
        return ''
    s = re.sub(r'(?i)<br\s*/?>|</p>|</div>|</li>', ' ', s)
    s = _TAG.sub('', s)
    s = html.unescape(s)
    s = unicodedata.normalize('NFC', s).replace('\u00a0', ' ').replace('\u200b', '')
    return _WS.sub(' ', s).strip()


def esc(s):
    """Plain text -> safe HTML text (quotes kept as typographic characters)."""
    return html.escape(s or '', quote=False)


def smart_quotes(s):
    """Straight quotes to typographic ones (plain text in, plain text out)."""
    s = re.sub(r'(^|[\s(\[{\u2014-])"', '\\1\u201c', s)
    s = s.replace('"', '\u201d')
    s = re.sub(r"(^|[\s(\[{\u2014-])'", '\\1\u2018', s)
    return s.replace("'", '\u2019')


def words(s):
    return re.findall(r"[A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F'\u2019-]*", s or '')


def word_count(s):
    return len(words(s))


BOILERPLATE = re.compile(
    r'(?i)^(advertisement|sponsored|related:|read more|read next|see also|credit:|image credit|photo credit|caption:|'
    r'this article (is|was) (republished|originally published)|sign up|subscribe|newsletter|share this|follow us|'
    r'click here|support our|donate|editor\'?s note|copyright|all rights reserved|the post .* appeared first on|'
    r'listen to this article|continue reading|recommended|more from|you may also like|top image|header image|to learn more|'
    r'learn more about|find out more|for more information|visit .{0,40}for more|watch the|view the)')


_PREAMBLE = [
    re.compile(r'(?i)^by:?\s+[^.]{0,80}?(email|e-mail):\s*\S+@\S+\s*'),                    # By: Office Email: x@y
    re.compile(r'^\((?:\s*[A-Z][\w.\' -]+,){1,3}\s*[A-Z][a-z]+\.? \d{1,2},? \d{4}\)\s*[\u2013\u2014-]+\s*'),  # (City, State, Oct. 27, 2026) -
    re.compile(r'^[A-Z][A-Z .,\'-]{2,40}(?:\([A-Za-z .]+\))?\s*[\u2013\u2014-]{1,2}\s+(?=[A-Z])'),   # WASHINGTON - / LAWRENCE, Kan. --
]
_JUNK = [
    re.compile(r'(?i)\((image|photo|video|graphic)( credit)?:[^)]*\)'),
    re.compile(r'(?i)\b(download (the )?(image|photo|video|pdf)|view (the )?(image|gallery|video))\b'),
    re.compile(r'(?i)\b\d+\s+off\s*$'),
]
_TRAILERS = [
    re.compile(r'(?i)\s*the post .{3,300}? (first )?appeared (first )?on .{2,120}?\.?\s*$'),
    re.compile(r'(?i)\s*(continue reading|read more|read the full story|read full article)\b.*$'),
    re.compile(r'\s*\[(\u2026|\.\.\.)\]\s*'),
]


def clean_lead(t):
    """Strip press-release preambles (bylines, contact emails, datelines) and feed trailers from text."""
    t = (t or '').strip()
    for _ in range(3):
        before = t
        for rx in _PREAMBLE:
            t = rx.sub('', t, count=1).strip()
        if t == before:
            break
    for rx in _JUNK + _TRAILERS:
        t = rx.sub(' ', t).strip()
    return re.sub(r'\s{2,}', ' ', t)


def is_boilerplate(p):
    p = p.strip()
    return (not p) or bool(BOILERPLATE.match(p)) or (len(p) < 40 and not re.search(r'[.!?\u201d]$', p) and not p.isupper())


# ------------------------------------------------------------------ sentences
_ABBR = {'mr', 'mrs', 'ms', 'dr', 'prof', 'sr', 'jr', 'st', 'mt', 'ft', 'vs', 'etc', 'inc', 'ltd', 'co', 'corp', 'dept',
         'univ', 'fig', 'figs', 'no', 'nos', 'vol', 'approx', 'est', 'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug',
         'sep', 'sept', 'oct', 'nov', 'dec', 'gen', 'gov', 'sen', 'rep', 'lt', 'col', 'capt', 'sgt', 'e.g', 'i.e',
         'al', 'ca', 'u.s', 'u.k', 'u.n', 'a.m', 'p.m', 'ph.d', 'b.c', 'a.d'}


def sentences(text):
    """Split prose into sentences (handles common abbreviations, initials, decimals and quotes)."""
    text = _WS.sub(' ', text or '').strip()
    if not text:
        return []
    out, start = [], 0
    for m in re.finditer(r'[.!?]+[\u201d\u2019"\')\]]*\s+(?=[\u201c\u2018"\'(\[]?[A-Z0-9\u00C0-\u00DE])', text):
        end = m.end()
        chunk = text[start:m.start() + 1]
        last = re.findall(r'([A-Za-z.]+)[.!?]+[\u201d\u2019"\')\]]*$', text[start:m.end()].strip())
        token = last[0].lower().rstrip('.') if last else ''
        if token in _ABBR or (len(token) == 1 and token.isalpha()):
            continue      # "Dr. Smith", "J. R. R."
        if re.search(r'\d\.$', text[start:m.start() + 1]) and re.match(r'\d', text[m.end():m.end() + 1]):
            continue      # 3. 5 (unlikely after the regex, kept for safety)
        out.append(text[start:end].strip())
        start = end
    out.append(text[start:].strip())
    return [s for s in out if s]


# ------------------------------------------------------------------ URLs
_DROP_PARAMS = re.compile(r'^(utm_|fbclid|gclid|mc_cid|mc_eid|ref$|ref_src|cmpid|ncid|sr_share|smid|soc_src|_hs|mkt_tok|'
                          r'guccounter|guce_|amp$|output$|rss$|src$|cid$)')


def canonical_url(url):
    """Normalize a URL so the same article from different links compares equal."""
    try:
        u = urlsplit(url.strip())
    except ValueError:
        return url.strip()
    scheme = 'https' if u.scheme in ('http', 'https') else u.scheme
    host = u.netloc.lower()
    if host.startswith('www.'):
        host = host[4:]
    path = re.sub(r'/(amp|amp\.html)/?$', '/', u.path) or '/'
    if path != '/' and path.endswith('/'):
        path = path[:-1]
    q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=False) if not _DROP_PARAMS.match(k.lower())]
    return urlunsplit((scheme, host, path, urlencode(q), ''))


def domain(url):
    return re.sub(r'^https?://(www\.)?', '', url).split('/')[0].lower()


# ------------------------------------------------------------------ near-duplicates
_STOP = set('a an the and or but of in on at to for from by with as is are was were be been it its this that these those '
            'new how why what when who which into over about after before more than says said can could will would may '
            'might has have had not no yes up out off'.split())


def shingles(text, k=3):
    w = [x.lower() for x in words(text) if x.lower() not in _STOP]
    if len(w) < k:
        return set(w)
    return {' '.join(w[i:i + k]) for i in range(len(w) - k + 1)}


def simhash(text, bits=64):
    v = [0] * bits
    toks = [x.lower() for x in words(text) if x.lower() not in _STOP]
    toks += [a + ' ' + b for a, b in zip(toks, toks[1:])]
    for t in toks:
        h = int.from_bytes(hashlib.blake2b(t.encode(), digest_size=8).digest(), 'big')
        for i in range(bits):
            v[i] += 1 if h >> i & 1 else -1
    return sum(1 << i for i in range(bits) if v[i] > 0)


def hamming(a, b):
    return bin(int(a) ^ int(b)).count('1')


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def same_story(t1, t2, s1=None, s2=None):
    """Two headlines (plus optional summaries) about the same story?"""
    k1, k2 = {x.lower() for x in words(t1) if x.lower() not in _STOP and len(x) > 2}, {x.lower() for x in words(t2) if x.lower() not in _STOP and len(x) > 2}
    if k1 and k2 and len(k1 & k2) / min(len(k1), len(k2)) >= 0.7 and len(k1 & k2) >= 3:
        return True
    if s1 and s2:
        return jaccard(shingles(s1), shingles(s2)) > 0.35
    return False


# ------------------------------------------------------------------ headlines
_SMALL = set('a an and as at but by en for if in nor of on or per the to v vs via with from into onto upon off up out over'.split())


def title_case(s):
    """AP-style title case for a plain-text headline. Words already capitalized mid-word (iPhone, NASA, eBay)
    keep their casing; small words stay lowercase except first and last."""
    parts = re.split(r'(\s+)', s.strip())
    toks = [p for p in parts if p and not p.isspace()]
    out, ti = [], 0
    for p in parts:
        if not p or p.isspace():
            out.append(p)
            continue
        first, last = ti == 0, ti == len(toks) - 1
        ti += 1

        def cap(w, force=False):
            core = re.sub(r'^[^\w]+|[^\w]+$', '', w)
            if not core:
                return w
            if any(c.isupper() for c in core[1:]) or any(c.isdigit() for c in core):
                return w          # NASA, iPhone, 3D, CO2
            if not force and core.lower() in _SMALL:
                return w.lower()
            i = w.find(core[0])
            return w[:i] + core[0].upper() + w[i + 1:]
        after_colon = out and re.search(r'[:\u2014\u2013-]\s*$', ''.join(out))
        force = first or last or bool(after_colon)
        out.append('-'.join(cap(x, force or j > 0) for j, x in enumerate(p.split('-'))))
    return ''.join(out)


def shorten(text, max_words, end='\u2026'):
    """Cut text to at most max_words words, at a sentence end when one is close, else at a word."""
    w = text.split()
    if len(w) <= max_words:
        return text
    cut = ' '.join(w[:max_words])
    m = list(re.finditer(r'[.!?][\u201d\u2019"\')]?(?=\s|$)', cut))
    if m and m[-1].end() > len(cut) * 0.6:
        return cut[:m[-1].end()]
    return cut.rstrip(',;:') + end


def numbers_in(text):
    """Numbers mentioned in text, normalized ('1,588' -> '1588', '3.5' -> '3.5', 'nine' left alone)."""
    return [n.replace(',', '') for n in re.findall(r'(?<![\w.])\d[\d,]*(?:\.\d+)?', text or '')]
