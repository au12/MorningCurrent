"""Build pipeline: puzzles -> render -> automatic fit -> reading PDF -> booklet -> QR check -> contact sheets -> QA.

The fitter adjusts only what the rules allow it to: where the lead jumps from page 1 to 2, where the
Deep Dive turns from the left page to the right, how many reserve briefs close short columns, how much
of an automatically written story is trimmed (whole paragraphs or single sentences, least important
first; never rewording, and only from the end for no-derivatives sources), a little extra space between
paragraphs, and how many sky-calendar rows and note lines the almanac and back page carry. Overflow it
cannot fix is reported for the writer to trim.
"""
import glob
import json
import math
import os
import re
import shutil
import subprocess

from . import paths, rules as R, templates as T
from .edition import Edition, ledger

MAX_SPACE = 6
NO_FILL = ('xword',)          # measured for overflow only


def _slots(rep):
    """{slot: (page, hidden lines, column fills, inner overflow px)} for every measured column region."""
    out = {}
    for p in rep:
        for k, v in p.items():
            if k.startswith('cols'):
                out[v['slot']] = (int(p['n']), v['hiddenLines'], v['colFills'], p['innerOver'])
    return out


def _target(slot):
    return R.FILL_OTHER if slot in ('almanac', 'back') else R.FILL_STORY


def _chars_per_line(one_column=True):
    inner = R.PAGE_W - R.MARGIN['inner'] - R.MARGIN['outer']
    w = (inner - R.COL_GAP) / 2
    return max(20, w * 72 / (R.BODY_PT * 0.468))


# ------------------------------------------------------------------ trimming helpers
def _trim_owner(ed, slot):
    """Which story (or list) a slot's overflow may be trimmed from, most expendable first."""
    if slot == 'front':
        return [ed.lead]
    if slot == 'cont':
        return ([ed.sidebar] if ed.sidebar else []) + [ed.lead]
    if slot == 'wonders':
        return [{'id': 'wonders', 'items': ed.wonders, '_min': R.WONDERS_COUNT[0]}]
    sid = slot[:-2] if slot.endswith(('_l', '_r')) else slot
    for s in ed.stories():
        if s['id'] == sid:
            return [s]
    for r in ed.roundups():
        if r['id'] == sid:
            return [r]
    return []


def _capacity(ed, st):
    if 'items' in st:     # roundup / Small Wonders: may drop items from the end, keeping a minimum
        return max(0, len(st['items']) - st.get('_min', 3))
    return len(st.get('trim') or [])


def _step_lines(st, i):
    step = st['trim'][i]
    if isinstance(step, int):
        b = st['blocks'][step]
        text = b[1] if len(b) > 1 and isinstance(b[1], str) else ''
    else:
        text = st.get('sents', {}).get(str(step[0]), [''] * (step[1] + 1))[step[1]]
    return max(1, len(re.sub(r'<[^>]+>', '', text)) / _chars_per_line())


def _trim_more(ed, st, hidden):
    """Increase a story's trim by enough steps to recover about `hidden` lines. Returns True if changed."""
    cap = _capacity(ed, st)
    cur = ed.fit['trim'].get(st['id'], 0)
    if cur >= cap:
        return False
    if 'items' in st:
        ed.fit['trim'][st['id']] = cur + 1
        return True
    got, k = 0.0, cur
    while k < cap and got < hidden:
        got += _step_lines(st, k)
        k += 1
    ed.fit['trim'][st['id']] = max(k, cur + 1)
    return True


# ------------------------------------------------------------------ the fit loop
def _sent_count(ed, st, idx):
    """Sentences in block idx of a story (after trimming), or 0 if it can't be split."""
    bl = ed.blocks_of(st)
    if idx < len(bl) and bl[idx] is not None and len(bl[idx]) > 2 and isinstance(bl[idx][2], dict):
        return len(bl[idx][2].get('s') or [])
    return 0


def _break_step(ed, f, st, key, skey, short, overflow, n_blocks, tag):
    """Move a page break (lead jump or spread turn). Whole blocks move forward; when the first page overflows,
    an automatically written story gives back one sentence at a time (a paragraph may continue after the jump);
    hand-written stories move whole blocks. Returns a change label or None."""
    j, js = f[key], f.get(skey, 0)
    if overflow:
        if js > 1:
            f[skey] = js - 1
            return f'{tag}s-'
        if js == 1:
            f[skey] = 0
            return f'{tag}s-'
        n_prev = _sent_count(ed, st, j - 1) if j >= 1 else 0
        if n_prev > 1 and j >= 1:
            f[key], f[skey] = j - 1, n_prev - 1
            return f'{tag}-s'
        if j > 2:
            f[key] = j - 1
            f[skey] = 0
            return f'{tag}-'
        return None
    if short:
        if js == 0 and j < n_blocks - 2 and (key + '+', j) not in f['tried']:
            f['tried'].add((key + '+', j))
            f[key] = j + 1
            return f'{tag}+'
        n = _sent_count(ed, st, j)
        if n > 1 and js + 1 < n and (skey + '+', j, js) not in f['tried']:
            f['tried'].add((skey + '+', j, js))
            f[skey] = js + 1
            return f'{tag}s+'
    return None


def _snapshot(ed):
    f = ed.fit
    return json.dumps(dict(xw_pt=f.get('xw_pt', 8.1), logic_zoom=f.get('logic_zoom', 1.0),
                           jump=f['jump'], jump_s=f.get('jump_s', 0), turn=f['turn'], turn_s=f.get('turn_s', 0),
                           cal_rows=f['cal_rows'], lookup=f['lookup'], note_lines=f['note_lines'], trim=f['trim'],
                           space=f['space'], extra={k: [b['head'] for b in v] for k, v in f['extra'].items()}))


def _restore(ed, snap, all_briefs):
    d = json.loads(snap)
    f = ed.fit
    for k in ('xw_pt', 'logic_zoom', 'jump', 'jump_s', 'turn', 'turn_s', 'cal_rows', 'lookup', 'note_lines', 'trim', 'space'):
        f[k] = d[k]
    by_head = {b['head']: b for b in all_briefs}
    f['extra'] = {k: [by_head[h] for h in v if h in by_head] for k, v in d['extra'].items()}
    used = {h for v in d['extra'].values() for h in v}
    ed.reserve = [b for b in all_briefs if b['head'] not in used]


def _badness(S):
    """Hidden lines first (they must never ship), then how far columns fall short of their fill targets."""
    hid = sum(h + (1 if inner else 0) for _, h, _, inner in S.values())
    short = sum(max(0, _target(slot) - min(fl)) for slot, (_, _, fl, _) in S.items() if fl)
    return hid * 1000 + short


def _search(f, sid):
    return f['search'].setdefault(sid, dict(lo=-1, hi=None, brief_trim=0))


def _trim_to(ed, st, t):
    t = max(0, min(t, _capacity(ed, st)))
    if t == ed.fit['trim'].get(st['id'], 0):
        return False
    ed.fit['trim'][st['id']] = t
    return True


def _story_slot(ed, f, slot, h, fl, changed):
    """One measured column region of a story page: trim auto copy to the least cut that fits (binary search),
    then fill a short column with a reserve brief (trimming a little more to make room) or extra spacing."""
    owners = _trim_owner(ed, slot)
    primary = owners[-1] if owners else None
    ex_id = primary['id'] if primary else slot
    ex = f['extra'].setdefault(ex_id, []) if primary else []
    trimmable = [o for o in owners if _capacity(ed, o) > 0]
    owner = None
    for o in trimmable:          # trim the most expendable story that still has room to give
        if f['trim'].get(o['id'], 0) < _capacity(ed, o):
            owner = o
            break
    owner = owner or (trimmable[-1] if trimmable else None)
    if h:
        if f['space'].get(slot, 0):
            f['space'][slot] -= 1
            changed.append(f'-space {slot}')
            return
        if ex:
            stt = _search(f, ex_id)
            if owner is not None and stt['brief_trim'] < 3 and _trim_to(ed, owner, f['trim'].get(owner['id'], 0) + 1):
                stt['brief_trim'] += 1
                changed.append(f'trim {owner["id"]} (for brief)')
                return
            b = ex.pop()
            f['tried'].add((ex_id, b['head']))
            ed.reserve.append(b)
            if owner is not None and stt['brief_trim']:
                _trim_to(ed, owner, f['trim'].get(owner['id'], 0) - stt['brief_trim'])
            stt['brief_trim'] = 0
            changed.append(f'-brief {ex_id}')
            return
        if owner is not None:
            stt = _search(f, owner['id'])
            cur = f['trim'].get(owner['id'], 0)
            stt['lo'] = max(stt['lo'], cur)
            if stt['hi'] is not None and stt['hi'] > cur:
                nxt = (cur + stt['hi'] + 1) // 2
            else:
                got, nxt = 0.0, cur
                if 'items' in owner:
                    nxt = cur + 1
                else:
                    while nxt < _capacity(ed, owner) and got < h:
                        got += _step_lines(owner, nxt)
                        nxt += 1
            if _trim_to(ed, owner, max(nxt, cur + 1)):
                changed.append(f'trim {owner["id"]}')
        return
    # the column fits
    if owner is not None and not ex:
        stt = _search(f, owner['id'])
        cur = f['trim'].get(owner['id'], 0)
        stt['hi'] = cur if stt['hi'] is None else min(stt['hi'], cur)
        if cur - 1 > stt['lo']:
            mid = (stt['lo'] + cur) // 2
            if mid <= stt['lo']:
                mid = stt['lo'] + 1
            if mid < cur and _trim_to(ed, owner, mid):
                changed.append(f'untrim {owner["id"]}')
                return
    if min(fl) >= _target(slot):
        return
    if primary is not None and ed.reserve:
        cat = primary.get('category')
        pool = sorted([b for b in ed.reserve if (ex_id, b['head']) not in f['tried']],
                      key=lambda b: (b.get('category') != cat, len(b['text'])))
        if pool:
            b = pool[0]
            ed.reserve.remove(b)
            ex.append(b)
            _search(f, ex_id)['brief_trim'] = 0
            changed.append(f'+brief {ex_id}')
            return
    lvl = f['space'].get(slot, 0)
    if lvl < MAX_SPACE and ('space+', slot, lvl) not in f['tried']:
        f['tried'].add(('space+', slot, lvl))
        f['space'][slot] = lvl + 1
        changed.append(f'+space {slot}')


def autofit(ed, work, renderer, max_iter=60, log=print):
    path = os.path.join(work, 'edition.html')
    seen = set()
    f = ed.fit
    all_briefs = list(ed.reserve) + [b for v in f['extra'].values() for b in v]
    best = None
    for it in range(max_iter):
        with open(path, 'w') as fh:
            fh.write(ed.html())
        rep_pages = renderer.measure(path)
        S = _slots(rep_pages)
        bad = _badness(S) + sum(1000 for p in rep_pages if p.get('innerOver', 0) > 2 and int(p['n']) not in {v[0] for v in S.values()})
        if best is None or bad < best[0]:
            best = (bad, _snapshot(ed))
        changed = []
        key = json.dumps([f.get('xw_pt'), f.get('logic_zoom'), f['jump'], f.get('jump_s', 0), f['turn'], f.get('turn_s', 0), f['cal_rows'], f['lookup'],
                          f['note_lines'], {k: [b['head'] for b in v] for k, v in f['extra'].items()}, f['trim'], f['space']],
                         sort_keys=True)
        if key in seen:
            log('fit: state repeated, stopping')
            break
        seen.add(key)
        # 1. the lead's jump from page 1 to page 2 (page 1 first: it is the paper's face)
        _, hid, fills, _ = S['front']
        _, chid, cfills, _ = S['cont']
        c = _break_step(ed, f, ed.lead, 'jump', 'jump_s', min(fills) < R.FILL_STORY, bool(hid), len(ed.lead['blocks']), 'jump')
        if c:
            changed.append(c)
        elif min(fills) < R.FILL_STORY and not hid:
            lvl = f['space'].get('front', 0)
            if lvl < MAX_SPACE and ('space+', 'front', lvl) not in f['tried']:
                f['tried'].add(('space+', 'front', lvl))
                f['space']['front'] = lvl + 1
                changed.append('+space front')
        elif hid and f['space'].get('front', 0):
            f['space']['front'] -= 1
            changed.append('-space front')
        # 2. the spread's turn from the left page to the right
        if ed.spread:
            sid = ed.spread['id']
            _, lh, lf, _ = S[sid + '_l']
            _, rh, rf, _ = S[sid + '_r']
            c = _break_step(ed, f, ed.spread, 'turn', 'turn_s', min(lf) < R.FILL_STORY and not rh, bool(lh),
                            len(ed.spread['blocks']), 'turn')
            if c:
                changed.append(c)
        # 3. every other story column
        for slot in ['cont'] + [x for x in S if x not in ('front', 'cont', 'almanac', 'back', 'xword')]:
            if slot not in S or (ed.spread and slot == ed.spread['id'] + '_l'):
                continue
            if 'jump' in ' '.join(changed) and slot == 'cont':
                continue          # let the jump settle before trimming page 2
            _, h, fl, _ = S[slot]
            _story_slot(ed, f, slot, h, fl, changed)
        # 4. almanac rows / look-up box
        if 'almanac' in S:
            _, h, fl, _ = S['almanac']
            if h:
                if f['lookup']:
                    f['lookup'] = False
                    f['tried'].add('lookup')
                else:
                    f['cal_rows'] -= 1
                changed.append('alm-')
            elif min(fl) < R.FILL_OTHER:
                if not f['lookup'] and 'lookup' not in f['tried']:
                    f['lookup'] = True
                    changed.append('alm+')
                elif f['cal_rows'] < 14 and ('cal+', f['cal_rows']) not in f['tried']:
                    f['tried'].add(('cal+', f['cal_rows']))
                    f['cal_rows'] += 1
                    changed.append('alm+')
        # 5. puzzle pages that overflow: smaller crossword clues, a slightly smaller logic page
        xw_over = 'xword' in S and S['xword'][1] > 0
        logic_over = False
        for p in rep_pages:
            if p.get('innerOver', 0) <= 2:
                continue
            pid = ed.pages[int(p['n']) - 1][0]
            if pid == 'logic' or (pid == 'xword' and 'crossword' not in ed.pz):
                logic_over = True
            elif pid == 'xword':
                xw_over = True
        if xw_over and f.get('xw_pt', 8.1) > 6.4:
            f['xw_pt'] = round(f.get('xw_pt', 8.1) - 0.3, 2)
            changed.append('xword clues smaller')
        if logic_over and f.get('logic_zoom', 1.0) > 0.7:
            f['logic_zoom'] = round(f.get('logic_zoom', 1.0) - 0.05, 2)
            changed.append('logic page smaller')
        # 6. back page note lines
        if 'back' in S:
            _, h, fl, _ = S['back']
            if h and f['note_lines'] > 2:
                f['note_lines'] -= 1
                f['tried'].add(('notes+', f['note_lines']))
                changed.append('notes-')
            elif min(fl) < R.FILL_OTHER and f['note_lines'] < 30 and ('notes+', f['note_lines']) not in f['tried']:
                f['tried'].add(('notes+', f['note_lines']))
                f['note_lines'] += 1
                changed.append('notes+')
        log(f'fit {it}: {", ".join(changed) or "stable"}')
        if not changed:
            break
    if best and best[1] != _snapshot(ed):
        _restore(ed, best[1], all_briefs)
        log(f'fit: keeping the best state seen (score {best[0]})')
    with open(path, 'w') as fh:
        fh.write(ed.html())
    return path


# ------------------------------------------------------------------ PDF helpers
def _render_pages(pdf, dpi):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf)
    try:
        for i in range(len(doc)):
            page = doc[i]
            img = page.render(scale=dpi / 72).to_pil()
            yield i + 1, img
            page.close()
    finally:
        doc.close()


def _decode(img):
    """All QR payloads found in a PIL image."""
    got = set()
    try:
        import zxingcpp
        for res in zxingcpp.read_barcodes(img, formats=zxingcpp.BarcodeFormat.QRCode):
            if res.text:
                got.add(res.text)
    except ImportError:
        pass
    if not got:
        try:
            import cv2
            import numpy as np
            arr = cv2.cvtColor(np.array(img.convert('RGB')), cv2.COLOR_RGB2BGR)
            ok, data, _, _ = cv2.QRCodeDetectorAruco().detectAndDecodeMulti(arr)
            if ok:
                got |= {t for t in data if t}
        except Exception:
            pass
    return got


def qrcheck(pdf, expected, work):
    """Rasterize at 300 dpi and decode every QR code. Tiles catch codes a whole-page pass misses."""
    found = {}
    for pg, img in _render_pages(pdf, 300):
        got = _decode(img)
        W, H = img.size
        step, tile = 600, 900
        for y in range(0, max(1, H - tile // 2), step):
            for x in range(0, max(1, W - tile // 2), step):
                got |= _decode(img.crop((x, y, min(W, x + tile), min(H, y + tile))))
        for t in got:
            found.setdefault(t, []).append(pg)
    return dict(decoded=sorted(found), missing=sorted(expected - set(found)), unexpected=sorted(set(found) - expected))


def impose(src, dst):
    """Booklet imposition: sheet s carries pages (N-2s, 1+2s) on the front and (2+2s, N-1-2s) on the back."""
    from pypdf import PdfReader, PdfWriter, Transformation, PageObject
    P = PdfReader(src).pages
    n = len(P)
    assert n % 4 == 0
    W, H = float(P[0].mediabox.width), float(P[0].mediabox.height)
    w = PdfWriter()
    for s in range(n // 4):
        for L, Rr in ((n - 2 * s, 1 + 2 * s), (2 + 2 * s, n - 1 - 2 * s)):   # front side, back side of sheet s
            sh = PageObject.create_blank_page(width=2 * W, height=H)
            sh.merge_transformed_page(P[L - 1], Transformation())
            sh.merge_transformed_page(P[Rr - 1], Transformation().translate(W, 0))
            w.add_page(sh)
    w.write(dst)


def contact(pdf, prefix, per=4, dpi=80):
    from PIL import Image
    for x in glob.glob(prefix + '-*.png'):
        os.remove(x)
    ims = [img for _, img in _render_pages(pdf, dpi)]
    w, h = ims[0].size
    rows = []
    for k in range(0, len(ims), per):
        sh = Image.new('RGB', (w * per, h), 'white')
        for i, im in enumerate(ims[k:k + per]):
            sh.paste(im, (i * w, 0))
        rows.append(f'{prefix}-row{k // per}.png')
        sh.save(rows[-1])
    for i, im in enumerate(ims, 1):
        im.save(f'{prefix}-pg-{i:02d}.png')
    return rows


# ------------------------------------------------------------------ QA
def qa(ed, rep, html, qr):
    """Every rule QA can check in code. Returns (errors, cosmetic, warnings): errors must never ship;
    cosmetic problems (a column short of its fill target) are judgment calls; warnings are advisory."""
    err, cos, warn = [], [], []
    if len(rep) != ed.pages_n:
        err.append(f'{len(rep)} pages rendered, plan has {ed.pages_n}')
    for slot, (pg, hid, fills, inner) in _slots(rep).items():
        if hid or inner:
            err.append(f'p{pg} {slot}: {hid} hidden lines, {inner}px stack overflow')
        if fills and slot not in NO_FILL and min(fills) < _target(slot):
            cos.append(f'p{pg} {slot}: column fill {fills} below {_target(slot)}%')
    slotted = {pg for pg, *_ in _slots(rep).values()}
    for p in rep:
        if int(p['n']) not in slotted and p.get('innerOver', 0) > 2:
            err.append(f'p{p["n"]}: content runs {p["innerOver"]}px past the bottom margin')
    if R.CLOCK == '24h' and re.search(r'\d\s?(a\.m\.|p\.m\.)', html):
        err.append('12-hour time found (use 24-hour HH:MM)')
    if '{p:' in html:
        err.append('unresolved {p:} reference')
    if qr['missing'] or qr['unexpected']:
        err.append(f'QR: missing {qr["missing"]}, unexpected {qr["unexpected"]}')
    used = {u for e in ledger()['editions'] if e['date'] != ed.date.isoformat() for u in e.get('urls', [])}
    standing = {ed.alm['src'][0]} if ed.alm.get('src') else set()     # a standing sky guide may repeat
    rep_urls = [u for u in ed.urls() if u in used and u not in standing]
    if rep_urls:
        err.append(f'URLs already used in earlier editions: {rep_urls}')
    cats = [s['category'] for s in ed.stories()] + [w.get('category') for w in ed.wonders if w.get('category')]
    cats += [r.get('category') for r in ed.roundups() if r.get('category')]
    bad = [c for c in cats if c not in R.ALL_CATEGORIES]
    if bad:
        err.append(f'unknown categories {bad} (see Settings > Content)')
    if len(set(cats)) < R.MIN_CATEGORIES:
        warn.append(f'only {len(set(cats))} categories; aim for {R.MIN_CATEGORIES}+')
    per_page = {}
    for pid, fn, args, sec in ed.pages:
        for a in args:
            if 'category' in a:
                per_page.setdefault(a['category'], set()).add(pid if fn is not T.spread_right else args[0]['id'])
    for c, ps in per_page.items():
        cap = R.CATEGORY_CAPS.get(c, R.MAX_SAME_CATEGORY)
        if len(ps) > cap:
            warn.append(f'{c} fills {len(ps)} story pages (max {cap})')
    med = sum(1 for s in ed.stories() if s['category'] in R.HEALTH_CATEGORIES and s is not ed.sidebar)
    if med > R.MEDICINE_MAX_FEATURES:
        warn.append(f'{med} medicine features (max {R.MEDICINE_MAX_FEATURES})')
    for s in ed.stories():
        lim = R.HEADLINE_MAX_CHARS['h1'] if s is ed.lead else R.HEADLINE_MAX_CHARS['h2']
        n = len(re.sub(r'&[a-z]+;', 'x', s['headline']))
        if n > lim:
            warn.append(f'headline over {lim} chars: {s["headline"][:40]}...')
    if ed.has('wonders') and not (R.WONDERS_COUNT[0] <= len(ed.wonders) <= R.WONDERS_COUNT[1]):
        warn.append(f'{len(ed.wonders)} Small Wonders')
    if ed.reserve:
        warn.append(f'{len(ed.reserve)} reserve briefs unused')
    return err, cos, warn


# ------------------------------------------------------------------ build
def build(date, log=print, allow_py=True, content=None, strict=True):
    """Build one edition. Returns a result dict; result['ok'] is True when nothing blocking failed
    (and, when strict, no column missed its fill target)."""
    from .measure import Renderer
    paths.ensure()
    ed = Edition(date, content=content, allow_py=allow_py)
    work = paths.out_dir(date)
    os.makedirs(work, exist_ok=True)
    os.makedirs(ed.dir, exist_ok=True)
    ed.make_puzzles()
    log(f'No. {ed.number}, {ed.pages_n} pp, sudoku {ed.pz["sudoku_level"]} {ed.pz["sudoku_stats"]}')
    reading, booklet = os.path.join(work, 'reading.pdf'), os.path.join(work, 'booklet.pdf')
    with Renderer() as r:
        html_path = autofit(ed, work, r, log=log)
        rep = r.measure(html_path)
        r.pdf(reading)
    if R.BOOKLET:
        impose(reading, booklet)
    else:
        shutil.copy(reading, booklet)
    qr = qrcheck(reading, ed.printed_urls(), work)
    rows = contact(reading, os.path.join(work, 'c'))
    with open(html_path) as fh:
        err, cos, warn = qa(ed, rep, fh.read(), qr)
    ed.save_puzzles()
    ed.save_fit()
    fit = {k: v for k, v in ed.fit.items() if k not in ('tried', 'search')}
    fit['extra'] = {k: [b['head'] for b in v] for k, v in fit['extra'].items() if v}
    result = dict(date=date, number=ed.number, pages=ed.pages_n, errors=err, cosmetic=cos, warnings=warn, fit=fit,
                  qr=len(qr['decoded']), qr_expected=len(ed.printed_urls()), contact=rows,
                  ok=not err and (not strict or not cos), reading=reading, booklet=booklet,
                  title=f'Vol. {R.VOLUME}, No. {ed.number}', lead=re.sub(r'<[^>]+>|&[a-z#0-9]+;', '', ed.lead['headline']))
    with open(os.path.join(work, 'qa.json'), 'w') as fh:
        json.dump(dict(result, measured=rep), fh, indent=1, default=str)
    for p in rep:
        cs = [f"{v['slot']}:{v['colFills']}{' HID ' + str(v['hiddenLines']) if v['hiddenLines'] else ''}" for k, v in p.items() if k.startswith('cols')]
        log(f"p{p['n']:>2} {'  '.join(cs)}")
    log(f'QR codes decoded: {len(qr["decoded"])}/{len(ed.printed_urls())}')
    for w in warn:
        log('WARN ' + w)
    for c in cos:
        log(('FAIL ' if strict else 'COSMETIC ') + c)
    for e in err:
        log('FAIL ' + e)
    log('QA ' + ('PASSED' if result['ok'] else 'FAILED') + f'; outputs in {work}; contact sheets {rows[0]}..')
    return result


def record(date, topics, allow_py=True):
    """Add this edition to the ledger (date, number, pages, every URL used, titles, short topic list)."""
    ed = Edition(date, allow_py=allow_py)
    L = ledger()
    L['editions'] = [e for e in L['editions'] if e['date'] != date]
    cats = sorted({s['category'] for s in ed.stories()})
    entry = dict(date=date, number=ed.number, pages=ed.pages_n, urls=ed.urls(), topics=topics, titles=ed.titles(),
                 categories=cats, lead_category=ed.lead['category'],
                 spread_category=ed.spread['category'] if ed.spread else None,
                 generator=ed.meta.get('generator', 'manual'))
    L['editions'].append(entry)
    L['editions'].sort(key=lambda e: e['date'])
    tmp = paths.ledger_file() + '.tmp'
    with open(tmp, 'w') as fh:
        json.dump(L, fh, indent=1)
    os.replace(tmp, paths.ledger_file())
    return entry


def publish(date, result=None):
    """Store a built edition's PDFs with the edition (where the printer, reader and archive find them)."""
    import datetime
    work = paths.out_dir(date)
    d = paths.edition_dir(date)
    os.makedirs(d, exist_ok=True)
    for name in ('booklet.pdf', 'reading.pdf', 'qa.json'):
        src = os.path.join(work, name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(d, name))
    meta_p = os.path.join(d, 'meta.json')
    meta = json.load(open(meta_p)) if os.path.exists(meta_p) else {}
    from pypdf import PdfReader
    meta.update(title=(result or {}).get('title') or meta.get('title', ''),
                pages=len(PdfReader(os.path.join(d, 'booklet.pdf')).pages),
                reading_pages=len(PdfReader(os.path.join(d, 'reading.pdf')).pages),
                uploaded_at=datetime.datetime.now().astimezone().isoformat(timespec='seconds'), source='build')
    if result:
        meta.update(lead=result.get('lead'), qa=dict(errors=result['errors'], cosmetic=result['cosmetic'],
                                                     warnings=result['warnings']))
    meta.setdefault('prints', [])
    pz = os.path.join(d, 'puzzles.json')
    if os.path.exists(pz):
        meta['data'] = json.load(open(pz))
    with open(meta_p, 'w') as fh:
        json.dump(meta, fh, indent=1)
    return meta


def deliver(date, url=None, token=None):
    """Upload booklet, reading PDF and puzzles to a remote Morning Current / Morning Press server."""
    from . import secrets
    ed = Edition(date)
    work = paths.out_dir(date)
    url = url or os.environ.get('PRESS_URL') or R.PRESS_URL
    token = token or os.environ.get('PRESS_TOKEN') or secrets.get('remote_token')
    if not url or not token:
        raise SystemExit('deliver needs a server URL (delivery.remote.url or $PRESS_URL) and a token ($PRESS_TOKEN)')
    import httpx
    files = {'file': ('booklet.pdf', open(os.path.join(work, 'booklet.pdf'), 'rb'), 'application/pdf'),
             'reading': ('reading.pdf', open(os.path.join(work, 'reading.pdf'), 'rb'), 'application/pdf')}
    pz = os.path.join(ed.dir, 'puzzles.json')
    data = {'date': date, 'title': f'Vol. {R.VOLUME}, No. {ed.number}', 'data': open(pz).read() if os.path.exists(pz) else ''}
    r = httpx.post(url, headers={'Authorization': f'Bearer {token}'}, files=files, data=data, timeout=120)
    print(r.text)
    r.raise_for_status()
    resp = r.json()
    expect = ed.pages_n // 2 if R.BOOKLET else ed.pages_n
    assert resp['date'] == date and resp['pages'] == expect, resp
    return resp
