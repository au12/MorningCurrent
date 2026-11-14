"""Turn fetched articles into the paper's story and brief formats, without AI.

The rules follow the license tier (see config.tier_for):
  full      public domain / CC BY: the article's own paragraphs in order, boilerplate removed, a verified
            pull quote, a public-domain photo when the source allows it; the fitter may trim whole
            paragraphs from the end and then closing sentences ("Excerpted" in the source box).
  verbatim  CC BY-ND: paragraphs exactly as published, headline untouched, no pull quote; the fitter may
            only cut whole paragraphs from the end, and a note says the excerpt continues at the source.
  excerpt   copyrighted: headline, the feed's own summary (shortened) and a QR code, as a brief.
Every piece of text from a feed is escaped before it becomes HTML.
"""
import datetime
import re

from .. import config
from ..ingest import fetch
from ..ingest.extract import credit_ok
from ..ingest.text import esc, plain, sentences, shorten, smart_quotes, title_case, word_count

QUOTE_RE = [
    # “Quote,” said Name / “Quote,” Name said / “Quote,” says Name, title.
    re.compile(r'“([^“”]{40,220}?)[,.!?]?”\s*(?:said|says|explained|explains|added|adds|noted|notes)\s+'
               r'((?:[A-Z][\w.\'’-]+\s?){1,4})'),
    re.compile(r'“([^“”]{40,220}?)[,.!?]?”\s*((?:[A-Z][\w.\'’-]+\s?){1,4})\s+(?:said|says|explained|added|noted)'),
]


def _clean_par(t):
    t = plain(t)
    if '"' in t or "'" in t:
        t = smart_quotes(t)
    return t


def _date_label(iso):
    try:
        d = datetime.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return ''
    mon = d.strftime('%b')
    mon = {'May': 'May', 'Jun': 'June', 'Jul': 'July', 'Sep': 'Sept.'}.get(mon, mon + '.')
    return f'{mon} {d.day}'


def short_category(cat):
    return esc(cat or '').replace('&amp;', '&amp;')


def source_name(it):
    """'The Conversation (Technology)' -> 'The Conversation'."""
    return re.sub(r'\s*\([^)]*\)\s*$', '', it.get('source') or '')


def kicker(it):
    return f'{esc(it.get("category") or "")} &middot; {esc(source_name(it))}'


def headline(it):
    t = _clean_par(it['title'])
    return esc(t if it.get('tier') == 'verbatim' else title_case(t))


def short_title(h):
    """A short index title from a headline (cut at a colon or dash, else after ~30 characters)."""
    t = plain(h)
    m = re.split(r'[:—–]| - ', t, maxsplit=1)
    t = m[0] if len(m[0]) <= 36 else t
    if len(t) > 36:
        w, out = t.split(), ''
        for x in w:
            if len(out) + len(x) > 30:
                break
            out = (out + ' ' + x).strip()
        t = out.rstrip(',;') + '…'
    t = t[:1].upper() + t[1:]
    return esc(t)


def find_quote(paragraphs):
    """A verbatim quote with a named speaker, as (quote, speaker) from the article text, or None."""
    for p in paragraphs:
        for rx in QUOTE_RE:
            m = rx.search(p)
            if m:
                q, who = m.group(1).strip(), m.group(2).strip().rstrip(',.')
                if len(who.split()) >= 2 and not re.search(r'\b(The|This|That|It|He|She|They|We|I)\b$', who):
                    return q.rstrip(',') + ('.' if not q.endswith(('.', '!', '?')) else ''), who
    return None


def _image(it, src_cfg):
    if not (config.load().format.photos and src_cfg and src_cfg.images and it.get('image')):
        return None
    if not credit_ok((it.get('image_credit') or '')):
        return None
    path = fetch.download_image(it['image'])
    if not path:
        return None
    cap = _clean_par(it.get('image_credit') or '')
    cap = shorten(cap, 28) if cap else ''
    return ['image', path, esc(cap), esc(f'{it["source"]}')]


def story(it, sid, role, budget, src_cfg=None, teaser=False, images=True):
    """An article -> a story dict for the given role (lead, feature, split, spread, sidebar)."""
    verbatim = it.get('tier') == 'verbatim'
    raw = it.get('blocks') or [dict(type='p', text=p) for p in (it.get('text') or '').split('\n\n') if p.strip()]
    blocks, paras = [], []
    total = 0
    limit = int(budget * 1.5) + 40          # take a little more than fits; the fitter trims the rest
    pending_head = None
    for b in raw:
        if total >= limit:
            break
        if b['type'] == 'h':
            pending_head = ['h4', esc(_clean_par(b['text']))]
            continue
        if b['type'] in ('p', 'quote'):
            t = _clean_par(b['text'])
            if not t:
                continue
            if pending_head and blocks:
                blocks.append(pending_head)
            pending_head = None
            html_t = esc(t) if b['type'] == 'p' else f'<i>{esc(t)}</i>'
            blocks.append(['p', html_t])
            paras.append((len(blocks) - 1, t))
            total += word_count(t)
        elif b['type'] == 'list' and blocks:
            items = [esc(_clean_par(x)) for x in b['items'][:8]]
            blocks.append(['list', items])
            total += sum(word_count(x) for x in b['items'][:8])
    if not paras:
        raise ValueError(f'no text for {it["url"]}')
    if role == 'lead':
        blocks[paras[0][0]][0] = 'dropcap'
    # sentence lists: used to split a paragraph across a page break, and (adaptable sources only) to trim
    sents = {}
    for i, t in paras:
        ss = sentences(t)
        if len(ss) > 1:
            sents[str(i)] = [esc(s) for s in ss]
    # extras: verified pull quote and photo (never for no-derivatives sources)
    if not verbatim and role in ('lead', 'feature', 'spread') and len(paras) >= 4:
        q = find_quote([t for _, t in paras])
        if q:
            pos = paras[min(2, len(paras) - 1)][0] + 1
            blocks.insert(pos, ['quote', esc(q[0]), esc(q[1])])
            sents = {str(int(k) + (1 if int(k) >= pos else 0)): v for k, v in sents.items()}
            paras = [(i + (1 if i >= pos else 0), t) for i, t in paras]
    if images and role in ('lead', 'feature', 'spread'):
        img = _image(it, src_cfg)
        if img and img[2]:
            cap = plain(img[2])[:50].lower()
            dup = [i for i, t in paras if t[:50].lower() == cap]
            if dup and len(paras) > 3:
                blocks[dup[0]] = ['p', '']          # keep indexes stable; empty paragraphs are skipped below
                paras = [(i, t) for i, t in paras if i != dup[0]]
                sents.pop(str(dup[0]), None)
        if img:
            pos = paras[0][0] + 1
            blocks.insert(pos, img)
            sents = {str(int(k) + (1 if int(k) >= pos else 0)): v for k, v in sents.items()}
            paras = [(i + (1 if i >= pos else 0), t) for i, t in paras]
    # trim order, least important first: walk back from the end; a paragraph loses its closing sentences
    # one at a time (adaptable sources only) and then goes entirely; lists and the pull quote go whole.
    # The first two paragraphs and photos always stay. Orphaned subheads disappear at render time.
    keep = {paras[0][0]} | ({paras[1][0]} if len(paras) > 1 else set())
    trim = []
    for i in range(len(blocks) - 1, -1, -1):
        kind = blocks[i][0]
        if i in keep or kind in ('image', 'h4') or (kind == 'p' and not blocks[i][1]):
            continue
        if kind == 'p' and not verbatim:
            n = len(sents.get(str(i), []))
            trim += [[i, k] for k in range(n - 1, 0, -1)]
        if kind in ('p', 'list', 'quote'):
            trim.append(i)
    date = _date_label(it.get('published'))
    note = ', '.join(x for x in (esc(source_name(it)), date) if x)
    if it.get('author') and len(it['author']) < 120:
        note += f'; by {esc(it["author"])}'
    attribution = esc(src_cfg.attribution) if src_cfg and src_cfg.attribution else ''
    lic = {'public-domain': 'Public domain', 'cc-by': 'CC BY 4.0', 'cc-by-sa': 'CC BY-SA 4.0', 'cc-by-nd': 'CC BY-ND 4.0',
           'cc-by-nc': 'CC BY-NC 4.0', 'cc-by-nc-sa': 'CC BY-NC-SA 4.0', 'cc-by-nc-nd': 'CC BY-NC-ND 4.0'}.get(it.get('license'), '')
    license_note = attribution or (f'{lic}' if lic else '')
    if not verbatim:
        license_note = ('Excerpted. ' + license_note).strip()
    summary = _clean_par(it.get('summary') or '')
    first = paras[0][1]
    title_p = _clean_par(it['title'])
    if summary.lower().startswith(title_p.lower()[:40]):
        summary = ''
    deck = ''
    if summary and summary[:60] not in first and word_count(summary) >= 6:
        deck = esc(shorten(summary, 34))
    empties = [i for i, b in enumerate(blocks) if b[0] == 'p' and not b[1]]
    if empties:                                    # drop placeholder paragraphs, shifting indexes
        remap = {}
        nb = []
        for i, b in enumerate(blocks):
            if i in empties:
                continue
            remap[i] = len(nb)
            nb.append(b)
        blocks = nb
        sents = {str(remap[int(k)]): v for k, v in sents.items() if int(k) in remap}
        trim = [([remap[x[0]], x[1]] if isinstance(x, list) else remap[x]) for x in trim
                if (x[0] if isinstance(x, list) else x) in remap]
    st = dict(id=sid, category=it['category'], kicker=kicker(it), headline=headline(it), deck=deck,
              src=[it['link'], 'Read the full story', note], blocks=blocks, trim=trim, sents=sents,
              license_note=license_note, item_id=it.get('id'), source=it.get('source'), auto=True)
    if verbatim:
        st['verbatim'] = True
        st['excerpt_note'] = 'This excerpt continues at the source; scan the code to read the rest.'
    if role == 'lead':
        st['cont_head'] = esc(_cont_head(it, paras))
    if teaser:
        hook = shorten(plain(st['deck'] or first), 16)
        st['teaser'] = [short_title(st['headline']), esc(hook)]
    return st


def add_trim(st, verbatim=False):
    """(Re)compute a story's sentence lists and trim order from its blocks (used for AI-written stories,
    whose own sentences may be cut like any adaptable source)."""
    blocks = st['blocks']
    paras = [(i, plain(b[1])) for i, b in enumerate(blocks) if b[0] in ('p', 'dropcap') and isinstance(b[1], str) and b[1]]
    sents = {}
    for i, t in paras:
        ss = sentences(t)
        if len(ss) > 1:
            sents[str(i)] = [esc(x) for x in ss]
    keep = {paras[0][0]} | ({paras[1][0]} if len(paras) > 1 else set()) if paras else set()
    trim = []
    for i in range(len(blocks) - 1, -1, -1):
        kind = blocks[i][0]
        if i in keep or kind in ('image', 'h4', 'jump', 'turn'):
            continue
        if kind in ('p', 'dropcap') and not verbatim:
            n = len(sents.get(str(i), []))
            trim += [[i, k] for k in range(n - 1, 0, -1)]
        if kind in ('p', 'dropcap', 'list', 'quote', 'facts', 'chart'):
            trim.append(i)
    st['sents'], st['trim'] = sents, trim
    return st


def _cont_head(it, paras):
    heads = [b['text'] for b in (it.get('blocks') or []) if b['type'] == 'h']
    if heads:
        h = _clean_par(heads[0])
        return h[:1].upper() + h[1:]
    t = plain(it['title'])
    return 'More on ' + (t[:1].lower() + t[1:] if not t[:2].isupper() else t)


def brief(it, max_words=62, credit=True):
    """An article -> a short item (Small Wonders, roundups, reserve briefs)."""
    from ..ingest.text import clean_lead
    text = clean_lead(_clean_par(it.get('summary') or ''))
    if word_count(text) < 12 and it.get('text'):
        text = clean_lead(_clean_par(it['text'].split('\n\n')[0]))
    text = shorten(text, max_words)
    b = dict(head=esc(title_case(_clean_par(it['title'])) if it.get('tier') != 'verbatim' else _clean_par(it['title'])),
             text=esc(text), src=it['link'], category=it.get('category'), item_id=it.get('id'), source=it.get('source'))
    if credit:
        d = _date_label(it.get('published'))
        b['credit'] = esc(', '.join(x for x in (source_name(it), d) if x))
    return b


def roundup(rid, title, items, category, deck='', kicker_text='In Brief'):
    return dict(id=rid, category=category, kicker=esc(kicker_text), headline=esc(title), deck=esc(deck), items=items,
                section=esc(title))
