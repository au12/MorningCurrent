"""Assign each article one category.

1. keywords: each category's keyword list (Settings > Content) scored over headline (x3), summary (x1.5)
   and the first part of the text (x0.4); multi-word phrases and stems ("archaeolog*") supported.
2. learned: a small naive Bayes model trained on articles whose category is known (printed in an edition
   or corrected on the editor's desk). It improves the keyword guess as the household's paper grows.
3. embeddings (optional): if the `fastembed` package is installed, articles are compared with each
   category's keywords in a small local embedding model (no API, no network after the first download).
The feed's own default category breaks ties and is used when nothing matches.
"""
import math
import re
from collections import Counter
from functools import lru_cache

from .. import config
from . import store
from .text import words

MIN_TRAIN = 40


def _kw_patterns(cats):
    out = {}
    for c in cats:
        singles, phrases, stems = set(), [], []
        for k in c.keywords:
            k = k.lower().strip()
            if not k:
                continue
            if k.endswith('*'):
                stems.append(k[:-1])
            elif ' ' in k or '-' in k:
                phrases.append(re.compile(r'\b' + re.escape(k) + r'\b'))
            else:
                singles.add(k)
        out[c.name] = (singles, phrases, tuple(stems))
    return out


@lru_cache(maxsize=2)
def _patterns_for(key):
    cfg = config.load()
    return _kw_patterns([c for c in cfg.editorial.categories if c.enabled])


def keyword_scores(title, summary='', text=''):
    cfg = config.load()
    key = tuple((c.name, tuple(c.keywords)) for c in cfg.editorial.categories if c.enabled)
    pats = _patterns_for(key)
    parts = ((title or '', 3.0), (summary or '', 1.5), ((text or '')[:4000], 0.4))
    scores = Counter()
    for name, (singles, phrases, stems) in pats.items():
        s = 0.0
        for txt, w in parts:
            low = txt.lower()
            toks = [t.lower() for t in words(txt)]
            hit = sum(1 for t in toks if t in singles or (stems and t.startswith(stems)))
            hit += sum(len(p.findall(low)) for p in phrases)
            s += w * min(hit, 6)
        if s:
            scores[name] = s
    return scores


# ------------------------------------------------------------------ naive Bayes
def _tokens(title, summary, text):
    toks = [t.lower() for t in words(f'{title} {title} {summary} {(text or "")[:2500]}') if len(t) > 2]
    return toks


def train():
    """Fit the classifier on labeled articles (printed or desk-corrected). Stored in the kv table."""
    con = store.connect()
    rows = con.execute("SELECT title, summary, text, category FROM items WHERE category IS NOT NULL AND "
                       "(status='used' OR cat_method='desk')").fetchall()
    if len(rows) < MIN_TRAIN:
        return None
    docs = Counter()
    counts = {}
    vocab = set()
    for r in rows:
        docs[r['category']] += 1
        c = counts.setdefault(r['category'], Counter())
        for t in set(_tokens(r['title'], r['summary'], r['text'])):
            c[t] += 1
            vocab.add(t)
    model = dict(docs=dict(docs), counts={k: dict(v.most_common(4000)) for k, v in counts.items()}, n=len(rows), v=len(vocab))
    store.kv_set('bayes', model)
    return model


def bayes_scores(title, summary, text, model):
    toks = set(_tokens(title, summary, text))
    out = {}
    V = model['v'] or 1
    for cat, nd in model['docs'].items():
        cnt = model['counts'].get(cat, {})
        lp = math.log(nd / model['n'])
        for t in toks:
            lp += math.log((cnt.get(t, 0) + 1) / (nd + 2))
        out[cat] = lp
    if not out:
        return {}
    m = max(out.values())
    z = sum(math.exp(v - m) for v in out.values())
    return {k: math.exp(v - m) / z for k, v in out.items()}


# ------------------------------------------------------------------ embeddings (optional)
_embed = None


def _embedder():
    global _embed
    if _embed is None:
        try:
            from fastembed import TextEmbedding
            _embed = TextEmbedding('BAAI/bge-small-en-v1.5')
        except Exception:  # noqa: BLE001
            _embed = False
    return _embed


def embedding_scores(title, summary):
    emb = _embedder()
    if not emb:
        return {}
    cfg = config.load()
    cats = [c for c in cfg.editorial.categories if c.enabled]
    key = 'cat_vectors:' + str(hash(tuple((c.name, tuple(c.keywords)) for c in cats)))
    vecs = store.kv_get(key)
    if not vecs:
        texts = [f'{c.name}: ' + ', '.join(k.rstrip('*') for k in c.keywords[:40]) for c in cats]
        vecs = {c.name: list(map(float, v)) for c, v in zip(cats, emb.embed(texts))}
        store.kv_set(key, vecs)
    q = list(emb.embed([f'{title}. {summary}'[:1000]]))[0]
    def cos(a, b):
        na = math.sqrt(sum(x * x for x in a)) or 1
        nb = math.sqrt(sum(x * x for x in b)) or 1
        return sum(x * y for x, y in zip(a, b)) / (na * nb)
    return {k: cos(q, v) for k, v in vecs.items()}


# ------------------------------------------------------------------ combined
def classify(title, summary='', text='', default=None):
    """Returns (category, confidence 0..1, method)."""
    cfg = config.load()
    names = cfg.editorial.category_names()
    kw = keyword_scores(title, summary, text)
    if default in names:
        kw[default] += 2.0
    method = 'keywords'
    total = sum(kw.values())
    probs = {k: v / total for k, v in kw.items()} if total else {}
    if cfg.editorial.classifier in ('learned', 'embeddings'):
        model = store.kv_get('bayes')
        if model and model.get('n', 0) >= MIN_TRAIN:
            b = bayes_scores(title, summary, text, model)
            if b:
                probs = {k: 0.6 * probs.get(k, 0) + 0.4 * b.get(k, 0) for k in set(probs) | set(b) if k in names}
                method = 'learned'
    if cfg.editorial.classifier == 'embeddings':
        e = embedding_scores(title, summary)
        if e:
            lo, hi = min(e.values()), max(e.values())
            span = (hi - lo) or 1
            probs = {k: 0.5 * probs.get(k, 0) + 0.5 * (e.get(k, lo) - lo) / span / len(e) * 3 for k in set(probs) | set(e) if k in names}
            method = 'embeddings'
    if not probs:
        return (default if default in names else None), 0.0, 'default'
    best = max(probs, key=probs.get)
    return best, round(probs[best], 3), method
