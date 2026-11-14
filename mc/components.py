"""Reusable page parts as Typst code: QR/source boxes, heads, story blocks, briefs, fact boxes and data-driven charts.

Every function returns a Typst *code* expression (no leading '#') built from the functions in mc/paper.typ.
Charts are described by data in the edition (never hand-placed graphics), drawn here as SVG so every
edition gets the same look. Kinds: bars, timeline, flow, checklist, svg (escape hatch for an explainer).
"""
import os
import re

import qrcode
import qrcode.image.svg

from . import rules as R
from .ty import array, length, q, rich, words

F = 'font-family="MC Franklin"'


class Region:
    """A measured column region: its slot name, spacing level and a running block index for the markers."""

    def __init__(self, slot, space=0):
        self.slot, self.space, self.i = slot, space, 0

    def nxt(self):
        self.i += 1
        return self.i - 1

    def args(self):
        return f'{q(self.slot)}, {self.nxt()}'


def code_block(parts):
    """Typst code statements -> one `{ ... }` block."""
    return '{\n' + '\n'.join(p for p in parts if p) + '\n}'


# ------------------------------------------------------------------ QR and sources
def qr_svg(url):
    long = len(url) > 120   # very long URLs: low error correction keeps modules big enough to scan
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1,
                      error_correction=qrcode.constants.ERROR_CORRECT_L if long else qrcode.constants.ERROR_CORRECT_M)
    return re.sub(r'<\?xml[^>]*\?>', '', img.to_string(encoding='unicode'))


def qr(url, size=None):
    size = size or R.QR_SIZE
    if len(url) > 120 and size == R.QR_SIZE:
        size = '0.74in'
    return f'svg({q(qr_svg(url))}, width: {length(size)})'


def qr_inline(url):
    return qr(url, R.QR_INLINE_LONG if len(url) > R.QR_LONG_URL else R.QR_INLINE)


def dom(url):
    return re.sub(r'^https?://(www\.)?', '', url).split('/')[0]


def srcbox(rg, url, label='Read the source', note=''):
    return f'srcbox({rg.args()}, {qr(url)}, {rich(label)}, {rich(note) if note else "none"}, {q(dom(url))})'


def story_src(rg, st):
    url, label, note = (list(st['src']) + ['Read the source', ''])[:3]
    if st.get('license_note'):
        note = f'{note}<br><i>{st["license_note"]}</i>' if note else f'<i>{st["license_note"]}</i>'
    return srcbox(rg, url, label or 'Read the source', note)


# ------------------------------------------------------------------ moon drawings
def moon_svg(illum, waning, size=12):
    """Lit fraction `illum` (0 new .. 1 full). Lit limb right when waxing, left when waning; the terminator
    (x-radius |2k-1|r) bulges toward the dark limb for a gibbous moon and toward the lit limb for a crescent."""
    r = size / 2 - 1
    c = size / 2
    k = min(max(illum, 0.0), 1.0)
    rx = abs(2 * k - 1) * r
    s = 1 if waning else 0
    t = (1 - s) if k >= 0.5 else s
    d = f'M{c},{c-r} A{r},{r} 0 0,{s} {c},{c+r} A{rx:.2f},{r} 0 0,{t} {c},{c-r} Z'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
            f'<circle cx="{c}" cy="{c}" r="{r}" fill="#fff" stroke="#111" stroke-width="1"/><path d="{d}" fill="#111"/></svg>')


def moon(illum, waning, size=12):
    """An inline moon icon (size in CSS px)."""
    return f'box(baseline: 15%, svg({q(moon_svg(illum, waning, size))}, width: {size * 0.75:.2f}pt))'


# ------------------------------------------------------------------ heads
def kicker(text):
    return f'kicker({rich(text)})'


def headblock(st, level='h2'):
    return f'headblock({rich(st["kicker"])}, {q(level)}, {rich(st["headline"])}, {rich(st["deck"]) if st.get("deck") else "none"})'


def shead(st):
    return f'shead({rich(st["kicker"])}, {rich(st["headline"])}, {rich(st["deck"]) if st.get("deck") else "none"})'


# ------------------------------------------------------------------ story blocks
def _dropcap(rg, html):
    m = re.match(r'^(\s*(?:<[^>]+>)*\s*)([“‘"\']?)(&[a-z]+;|.)', html)
    if not m:
        return f'para({rg.args()}, indent: false, {rich(html)})'
    from .ty import plain
    letter = plain(m.group(2) + m.group(3))
    rest = html[m.end():]
    if m.group(1):
        rest = m.group(1) + rest           # keep an opening tag (e.g. <i>) for the rest of the word
    ws = words(rest)
    return f'dropcap({rg.args()}, {q(letter)}, {ws})'


def blocks(rg, bl, wide=False, first_dropcap=False):
    """Render a block list. ('p'|'dropcap'|'h4', html) ('quote', text, who) ('chart', spec) ('facts', title, items[, cols])
    ('image', src, caption, credit) ('note', html) ('list', items) ('jump',)"""
    out = []
    prev = None
    for i, b in enumerate(bl):
        t = b[0]
        opt = b[2] if len(b) > 2 and isinstance(b[2], dict) else {}
        if opt.get('cont'):
            out.append(f'para({rg.args()}, indent: false, {rich(b[1])})')
        elif t == 'dropcap' or (t == 'p' and i == 0 and first_dropcap):
            out.append(_dropcap(rg, b[1]))
        elif t == 'p':
            indent = prev not in (None, 'h4')
            out.append(f'para({rg.args()}, indent: {"true" if indent else "false"}, {rich(b[1])})')
        elif t == 'h4':
            out.append(f'h4({rg.args()}, space: {rg.space}, {rich(b[1])})')
        elif t == 'quote':
            out.append(f'pull({rg.args()}, [“] + {rich(b[1])} + [”], {rich(b[2])})')
        elif t == 'chart':
            out.append(chart(rg, b[1], wide))
        elif t == 'facts':
            out.append(factbox(rg, b[1], b[2], b[3] if len(b) > 3 else (2 if len(b[2]) <= 2 else 4)))
        elif t == 'image':
            out.append(photo(rg, *b[1:]))
        elif t == 'note':
            out.append(f'note({rg.args()}, {rich(b[1])})')
        elif t == 'list':
            out.append(f'blist({rg.args()}, {array(rich(x) for x in b[1])})')
        elif t in ('jump', 'turn'):
            continue
        else:
            raise ValueError(f'unknown block {t}')
        prev = 'p' if t in ('p', 'dropcap') else t
    return out


def photo(rg, src, caption='', credit='', height=None):
    """A photo (public-domain or openly licensed only), printed in grayscale."""
    path = src[7:] if src.startswith('file://') else src
    path, ratio = _gray(path)
    if not path:
        return ''
    return (f'photo({rg.args()}, {q(path)}, {rich(caption) if caption else "none"}, '
            f'{rich(credit) if credit else "none"}, {ratio:.4f})')


def _gray(path):
    """A grayscale copy of an image next to the original (Typst prints images as they are), and its aspect ratio."""
    try:
        from PIL import Image, ImageOps
        if not os.path.exists(path):
            return None, 1
        root, _ = os.path.splitext(path)
        out = root + '.gray.jpg'
        if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(path):
            im = Image.open(path)
            im = ImageOps.exif_transpose(im).convert('L')
            im = ImageOps.autocontrast(im, cutoff=0.5)
            im.save(out, quality=88)
        w, h = Image.open(out).size
        return os.path.abspath(out), w / max(h, 1)
    except Exception:  # noqa: BLE001
        return None, 1


def plain(bl):
    """Same blocks, with any drop cap demoted (for stories that don't lead their page)."""
    return [('p',) + tuple(b[1:]) if b and b[0] == 'dropcap' else b for b in bl]


def brief(rg, b):
    """A brief: dict(head, text, src=url optional). With src it gets its own inline QR."""
    qr_ = qr_inline(b['src']) if b.get('src') else 'none'
    cr = rich(b['credit']) if b.get('credit') else 'none'
    return f'mini({rg.args()}, space: {rg.space}, {rich(b["head"])}, {rich(b["text"])}, qr: {qr_}, credit: {cr})'


def also(rg, kick, briefs, note=''):
    if not briefs:
        return []
    out = [f'also-head({rg.args()}, {rich(kick)})'] + [brief(rg, b) for b in briefs]
    if note:
        out.append(f'note({rg.args()}, {rich(note)})')
    return out


def fact_items(items):
    return array(f'({rich(a)}, {rich(b)})' for a, b in items)


def factbox(rg, title, items, cols=4):
    return f'facts({rg.args()}, {rich(title)}, {fact_items(items)}, {cols})'


# ------------------------------------------------------------------ charts
def _wrap(rg, spec, svg, W, H):
    note = rich(spec['note']) if spec.get('note') else 'none'
    src = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H:.0f}" width="{W}" height="{H:.0f}">{svg}</svg>'
    return f'chart({rg.args()}, {rich(spec["title"])}, {q(src)}, {note})'


def _svgtext(t):
    """Chart labels: inline HTML -> SVG text (entities decoded, tags dropped, XML-escaped)."""
    from xml.sax.saxutils import escape
    from .ty import plain as _p
    return escape(_p(str(t)))


def chart(rg, spec, wide=False):
    return {'bars': bars, 'timeline': timeline, 'flow': flow, 'checklist': checklist, 'svg': raw_svg}[spec['kind']](rg, spec, wide)


def bars(rg, spec, wide=False):
    """Horizontal bars. rows: [(label, value)]; the largest (or `highlight` index) is drawn black.
    fmt: python format for the value label; unit appended."""
    rows = spec['rows']
    W = 590 if wide else 280
    lw = max(len(_svgtext(l)) for l, _ in rows) * 3.55 + 6
    vmax = spec.get('max') or max(v for _, v in rows)
    bw = W - lw - 52
    hi = spec.get('highlight', max(range(len(rows)), key=lambda i: rows[i][1]))
    s = ''
    y = 2
    for i, (l, v) in enumerate(rows):
        w = max(v / vmax * bw, 1.2)
        f = '#111' if i == hi else ('#777' if i % 2 else '#999')
        lab = _svgtext(format(v, spec.get('fmt', ',g')) + spec.get('unit', ''))
        s += (f'<text x="0" y="{y+8.5}" {F} font-size="7">{_svgtext(l)}</text><rect x="{lw:.0f}" y="{y}" width="{w:.1f}" height="11" fill="{f}"/>'
              f'<text x="{lw+w+4:.1f}" y="{y+8.5}" {F} font-weight="700" font-size="7">{lab}</text>')
        y += 16
    return _wrap(rg, spec, s, W, y)


def _textw(t, size):
    return len(_svgtext(t)) * size * 0.53


def timeline(rg, spec, wide=True):
    """events: [(t, label, sublabel, key)] with t a decimal year (or any number); start/end set the axis.
    Labels are placed automatically on four tiers (two above, two below) so none overlap."""
    W = 590 if wide else 280
    x0, x1 = 24, W - 24
    t0, t1 = spec['start'], spec['end']
    X = lambda t: x0 + (t - t0) / (t1 - t0) * (x1 - x0)
    step = spec.get('tick', max(1, round((t1 - t0) / 12)))
    s = f'<line x1="{x0}" y1="40" x2="{x1}" y2="40" stroke="#111" stroke-width="1.2"/>'
    k = int(t0) + (0 if t0 == int(t0) else 1)
    while k <= t1:
        if (k - int(spec['start'])) % step == 0:
            s += (f'<line x1="{X(k):.1f}" y1="37" x2="{X(k):.1f}" y2="43" stroke="#111" stroke-width=".6"/>'
                  f'<text x="{X(k):.1f}" y="53" text-anchor="middle" {F} font-size="7" fill="#333">'
                  f'{_svgtext(spec.get("tickfmt", "{}").format(k))}</text>')
        k += 1
    tiers = {'up': [], 'down': [], 'up2': [], 'down2': []}
    for t, a, b, key in sorted(spec['events'], key=lambda e: e[0]):
        x = X(t)
        w = max(_textw(a, 6.6), _textw(b, 6.0)) + 4
        opts = []
        for n in ('up', 'down', 'up2', 'down2'):
            for anc in ('middle', 'start', 'end'):
                lo = x if anc == 'start' else x - w if anc == 'end' else x - w / 2
                if lo < 2 or lo + w > W - 2:
                    continue
                if all(lo > r + 3 or lo + w < l - 3 for l, r in tiers[n]):
                    opts.append((n, anc, lo))
        tier, anc, lo = opts[0] if opts else ('down2', 'middle', x - w / 2)
        tiers[tier].append((lo, lo + w))
        xt = x + 3 if anc == 'start' else x - 3 if anc == 'end' else x
        s += f'<circle cx="{x:.1f}" cy="40" r="{4 if key else 2.6}" fill="{"#111" if key else "#fff"}" stroke="#111" stroke-width="1"/>'
        a, b = _svgtext(a), _svgtext(b)
        if tier.startswith('up'):
            yy = 26 if tier == 'up' else 12
            s += f'<line x1="{x:.1f}" y1="{yy+3}" x2="{x:.1f}" y2="37" stroke="#999" stroke-width=".5"/>'
            s += (f'<text x="{xt:.1f}" y="{yy-6}" text-anchor="{anc}" {F} font-weight="800" font-size="6.6">{a}</text>'
                  f'<text x="{xt:.1f}" y="{yy+1}" text-anchor="{anc}" {F} font-size="6">{b}</text>')
        else:
            yy = 68 if tier == 'down' else 84
            s += f'<line x1="{x:.1f}" y1="43" x2="{x:.1f}" y2="{yy-8}" stroke="#999" stroke-width=".5"/>'
            s += (f'<text x="{xt:.1f}" y="{yy}" text-anchor="{anc}" {F} font-weight="800" font-size="6.6">{a}</text>'
                  f'<text x="{xt:.1f}" y="{yy+7}" text-anchor="{anc}" {F} font-size="6">{b}</text>')
    H = 94 if tiers['down2'] else 78 if tiers['down'] else 58
    return _wrap(rg, spec, s, W, H)


def flow(rg, spec, wide=False):
    """Process diagram. lanes: [(lane label, [(step, substep), ...])]; each lane is a row of boxes joined by arrows.
    shade: lane indexes drawn shaded."""
    W = 590 if wide else 280
    s = ''
    y = 0
    for li, (lab, steps) in enumerate(spec['lanes']):
        if lab:
            s += f'<text x="0" y="{y+8}" {F} font-weight="800" font-size="6.6" letter-spacing=".08em">{_svgtext(lab).upper()}</text>'
            y += 12
        n = len(steps)
        gap = 18
        bw = (W - gap * (n - 1)) / n
        for i, st in enumerate(steps):
            a, b = (list(st) + [''])[:2] if isinstance(st, (list, tuple)) else (st, '')
            x = i * (bw + gap)
            dark = li in spec.get('shade', [])
            s += (f'<rect x="{x:.1f}" y="{y}" width="{bw:.1f}" height="24" rx="3" fill="{"#e4e4e4" if dark else "#fff"}" stroke="#111" stroke-width=".8"/>'
                  f'<text x="{x+bw/2:.1f}" y="{y+10}" text-anchor="middle" {F} font-weight="800" font-size="6.6">{_svgtext(a)}</text>'
                  f'<text x="{x+bw/2:.1f}" y="{y+19}" text-anchor="middle" {F} font-size="6">{_svgtext(b)}</text>')
            if i < n - 1:
                ax = x + bw + 2
                bx = x + bw + gap - 1
                s += (f'<line x1="{ax:.1f}" y1="{y+12}" x2="{bx-3:.1f}" y2="{y+12}" stroke="#111" stroke-width=".9"/>'
                      f'<path d="M{bx-4:.1f} {y+9.4} L{bx:.1f} {y+12} L{bx-4:.1f} {y+14.6} Z" fill="#111"/>')
        y += 34
    return _wrap(rg, spec, s, W, y - 6)


def checklist(rg, spec, wide=False):
    """rows: [(mark, title, detail)] with mark 'x' (ruled out), 'o' (open) or 'v' (confirmed)."""
    W = 590 if wide else 280
    s = ''
    y = 2
    for mark, a, b in spec['rows']:
        if mark == 'x':
            s += (f'<line x1="2" y1="{y+4}" x2="9" y2="{y+11}" stroke="#111" stroke-width="1.4"/>'
                  f'<line x1="9" y1="{y+4}" x2="2" y2="{y+11}" stroke="#111" stroke-width="1.4"/>')
        elif mark == 'v':
            s += f'<path d="M1 {y+8} L4.5 {y+11.5} L10 {y+3.5}" fill="none" stroke="#111" stroke-width="1.5"/>'
        else:
            s += f'<circle cx="5.5" cy="{y+7.5}" r="3.6" fill="none" stroke="#111" stroke-width="1.2"/>'
        s += (f'<text x="15" y="{y+7}" {F} font-weight="800" font-size="6.9">{_svgtext(a)}</text>'
              f'<text x="15" y="{y+14.5}" {F} font-size="6.4" fill="#333">{_svgtext(b)}</text>')
        y += 20
    return _wrap(rg, spec, s, W, y)


def raw_svg(rg, spec, wide=False):
    """Escape hatch for an explainer diagram: spec['svg'] is SVG markup for a viewBox of width 280 (590 if wide) x spec['height']."""
    import html as _h
    svg = re.sub(r'font-family="[^"]*"', F, spec['svg'])
    svg = re.sub(r'&([a-zA-Z]+);', lambda m: m.group(0) if m.group(1) in ('amp', 'lt', 'gt', 'quot', 'apos') else _h.unescape(m.group(0)), svg)
    return _wrap(rg, spec, svg, 590 if wide else 280, spec['height'])
