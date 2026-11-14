"""Reusable page parts: QR/source boxes, heads, story blocks, briefs, fact boxes and data-driven charts.

Charts are described by data in the edition (never hand-placed SVG), so every edition gets the same
look. Kinds: bars, timeline, flow, checklist, svg (escape hatch for a one-off explainer diagram).
"""
import re
import qrcode, qrcode.image.svg
from . import rules as R

F = 'font-family="Franklin"'

# ------------------------------------------------------------------ QR and sources
def qr(url, size=None):
    size = size or R.QR_SIZE
    long = len(url) > 120   # very long URLs: low error correction keeps modules big enough to scan
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1,
                      error_correction=qrcode.constants.ERROR_CORRECT_L if long else qrcode.constants.ERROR_CORRECT_M)
    s = re.sub(r'<\?xml[^>]*\?>', '', img.to_string(encoding='unicode'))
    size = '0.74in' if long and size == R.QR_SIZE else size
    s = re.sub(r'width="[^"]*"', f'width="{size}"', s, count=1)
    return re.sub(r'height="[^"]*"', f'height="{size}"', s, count=1)

def qr_inline(url):
    return qr(url, R.QR_INLINE_LONG if len(url) > R.QR_LONG_URL else R.QR_INLINE)

def dom(url):
    return re.sub(r'^https?://(www\.)?', '', url).split('/')[0]

def srcbox(url, label='Read the source', note=''):
    return (f'<div class="src">{qr(url)}<div><b>{label}</b><br>{note}{"<br>" if note else ""}'
            f'<span class="dom">{dom(url)}</span></div></div>')

def story_src(st):
    url, label, note = (list(st['src']) + ['Read the source', ''])[:3]
    if st.get('license_note'):
        note = f'{note}<br><i>{st["license_note"]}</i>' if note else f'<i>{st["license_note"]}</i>'
    return srcbox(url, label or 'Read the source', note)

# ------------------------------------------------------------------ moon drawings
def moon_svg(illum, waning, size=12):
    """Lit fraction `illum` (0 new .. 1 full). Lit limb right when waxing, left when waning; the terminator
    (x-radius |2k-1|r) bulges toward the dark limb for a gibbous moon and toward the lit limb for a crescent."""
    r = size / 2 - 1; c = size / 2
    k = min(max(illum, 0.0), 1.0); rx = abs(2 * k - 1) * r
    s = 1 if waning else 0
    t = (1 - s) if k >= 0.5 else s
    d = f'M{c},{c-r} A{r},{r} 0 0,{s} {c},{c+r} A{rx:.2f},{r} 0 0,{t} {c},{c-r} Z'
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}"><circle cx="{c}" cy="{c}" r="{r}" fill="#fff" '
            f'stroke="#111" stroke-width="1"/><path d="{d}" fill="#111"/></svg>')

# ------------------------------------------------------------------ heads
def kicker(text):
    return f'<div class="kicker"><span>{text}</span></div>'

def headblock(st, level='h2'):
    d = f'<div class="deck">{st["deck"]}</div>' if st.get('deck') else ''
    return f'<div class="headblock">{kicker(st["kicker"])}<{level}>{st["headline"]}</{level}>{d}</div>'

def shead(st):
    d = f'<div class="deck">{st["deck"]}</div>' if st.get('deck') else ''
    return f'<div class="shead">{kicker(st["kicker"])}<h3>{st["headline"]}</h3>{d}</div>'

# ------------------------------------------------------------------ story blocks
def blocks(bl, wide=False, first_dropcap=False):
    """Render a block list. ('p'|'dropcap'|'h4', html) ('quote', text, who) ('chart', spec) ('facts', title, items[, cols]) ('jump',)"""
    h = ''
    for i, b in enumerate(bl):
        t = b[0]
        opt = b[2] if len(b) > 2 and isinstance(b[2], dict) else {}
        if opt.get('cont'): h += f'<p class="noind">{b[1]}</p>'
        elif t == 'dropcap' or (t == 'p' and i == 0 and first_dropcap): h += f'<p class="dropcap">{b[1]}</p>'
        elif t == 'p': h += f'<p>{b[1]}</p>'
        elif t == 'h4': h += f'<h4>{b[1]}</h4>'
        elif t == 'quote': h += f'<div class="pull">&ldquo;{b[1]}&rdquo;<span class="who">{b[2]}</span></div>'
        elif t == 'chart': h += chart(b[1], wide)
        elif t == 'facts': h += factbox(b[1], b[2], b[3] if len(b) > 3 else (2 if len(b[2]) <= 2 else 4))
        elif t == 'image': h += photo(*b[1:])
        elif t == 'note': h += f'<p class="enote">{b[1]}</p>'
        elif t == 'list': h += '<ul class="blist">' + ''.join(f'<li>{x}</li>' for x in b[1]) + '</ul>'
        elif t in ('jump', 'turn'): pass
        else: raise ValueError(f'unknown block {t}')
    return h

def photo(src, caption='', credit='', height=None):
    """A grayscale photo (public-domain or openly licensed only). src is a local file path or file:// URL."""
    url = src if src.startswith(('file:', 'data:', 'http')) else 'file://' + src
    cap = f'<figcaption>{caption}{" <span>" + credit + "</span>" if credit else ""}</figcaption>' if (caption or credit) else ''
    style = f' style="max-height:{height}in"' if height else ''
    return f'<figure class="photo"><img src="{url}" alt=""{style}>{cap}</figure>'


def plain(bl):
    """Same blocks, with any drop cap demoted (for stories that don't lead their page)."""
    return [('p',) + tuple(b[1:]) if b and b[0] == 'dropcap' else b for b in bl]

def brief(b):
    """A brief: dict(head, text, src=url optional). With src it gets its own inline QR."""
    cr = f'<p class="srcl">{b["credit"]}</p>' if b.get('credit') else ''
    if b.get('src'):
        return (f'<div class="mini"><div class="qhead"><h5>{b["head"]}</h5>{qr_inline(b["src"])}</div><p>{b["text"]}</p>{cr}</div>')
    return f'<div class="mini"><h5>{b["head"]}</h5><p>{b["text"]}</p>{cr}</div>'

def also(kick, briefs, note=''):
    if not briefs: return ''
    h = f'<div class="bhead"><div class="rule thick" style="margin:9pt 0 4pt"></div>{kicker(kick)}</div>'
    h += ''.join(brief(b) for b in briefs)
    return h + (f'<p class="note">{note}</p>' if note else '')

def factbox(title, items, cols=4):
    fh = ''.join(f'<div><b>{a}</b>{b}</div>' for a, b in items)
    return (f'<div class="box shade fill" style="padding:5pt 7pt"><div class="boxhead" style="margin-bottom:3pt">{title}</div>'
            f'<div class="facts{" two" if cols == 2 else ""}">{fh}</div></div>')

# ------------------------------------------------------------------ charts
def _wrap(spec, svg, W, H, flex=False):
    note = f'<div class="cs">{spec["note"]}</div>' if spec.get('note') else ''
    return (f'<div class="chart">'
            f'<div class="ct">{spec["title"]}</div><svg viewBox="0 0 {W} {H:.0f}" width="100%">{svg}</svg>{note}</div>')

def chart(spec, wide=False):
    return {'bars': bars, 'timeline': timeline, 'flow': flow, 'checklist': checklist, 'svg': raw_svg}[spec['kind']](spec, wide)

def bars(spec, wide=False):
    """Horizontal bars. rows: [(label, value)]; the largest (or `highlight` index) is drawn black.
    fmt: python format for the value label; unit appended."""
    rows = spec['rows']; W = 590 if wide else 280
    lw = max(len(re.sub(r'&[a-z]+;', 'x', str(l))) for l, _ in rows) * 3.55 + 6
    vmax = spec.get('max') or max(v for _, v in rows); bw = W - lw - 52
    hi = spec.get('highlight', max(range(len(rows)), key=lambda i: rows[i][1]))
    s = ''; y = 2
    for i, (l, v) in enumerate(rows):
        w = max(v / vmax * bw, 1.2); f = '#111' if i == hi else ('#777' if i % 2 else '#999')
        lab = format(v, spec.get('fmt', ',g')) + spec.get('unit', '')
        s += (f'<text x="0" y="{y+8.5}" {F} font-size="7">{l}</text><rect x="{lw:.0f}" y="{y}" width="{w:.1f}" height="11" fill="{f}"/>'
              f'<text x="{lw+w+4:.1f}" y="{y+8.5}" {F} font-weight="700" font-size="7">{lab}</text>')
        y += 16
    return _wrap(spec, s, W, y)

def _textw(t, size):
    return len(re.sub(r'&[a-z#0-9]+;', 'x', re.sub(r'<[^>]+>', '', str(t)))) * size * 0.53

def timeline(spec, wide=True):
    """events: [(t, label, sublabel, key)] with t a decimal year (or any number); start/end set the axis.
    Labels are placed automatically on four tiers (two above, two below) so none overlap."""
    W = 590 if wide else 280; x0, x1 = 24, W - 24
    t0, t1 = spec['start'], spec['end']; X = lambda t: x0 + (t - t0) / (t1 - t0) * (x1 - x0)
    step = spec.get('tick', max(1, round((t1 - t0) / 12)))
    s = f'<line x1="{x0}" y1="40" x2="{x1}" y2="40" stroke="#111" stroke-width="1.2"/>'
    k = int(t0) + (0 if t0 == int(t0) else 1)
    while k <= t1:
        if (k - int(spec['start'])) % step == 0:
            s += (f'<line x1="{X(k):.1f}" y1="37" x2="{X(k):.1f}" y2="43" stroke="#111" stroke-width=".6"/>'
                  f'<text x="{X(k):.1f}" y="53" text-anchor="middle" {F} font-size="7" fill="#333">{spec.get("tickfmt", "{}").format(k)}</text>')
        k += 1
    tiers = {'up': [], 'down': [], 'up2': [], 'down2': []}
    for t, a, b, key in sorted(spec['events'], key=lambda e: e[0]):
        x = X(t); w = max(_textw(a, 6.6), _textw(b, 6.0)) + 4
        opts = []   # (tier, anchor) in order of preference; a label may hang left or right of its dot to find room
        for n in ('up', 'down', 'up2', 'down2'):
            for anc in ('middle', 'start', 'end'):
                lo = x if anc == 'start' else x - w if anc == 'end' else x - w / 2
                if lo < 2 or lo + w > W - 2: continue
                if all(lo > r + 3 or lo + w < l - 3 for l, r in tiers[n]): opts.append((n, anc, lo))
        tier, anc, lo = opts[0] if opts else ('down2', 'middle', x - w / 2)
        tiers[tier].append((lo, lo + w)); xt = x + 3 if anc == 'start' else x - 3 if anc == 'end' else x
        s += f'<circle cx="{x:.1f}" cy="40" r="{4 if key else 2.6}" fill="{"#111" if key else "#fff"}" stroke="#111" stroke-width="1"/>'
        if tier.startswith('up'):
            yy = 26 if tier == 'up' else 12
            s += f'<line x1="{x:.1f}" y1="{yy+3}" x2="{x:.1f}" y2="37" stroke="#999" stroke-width=".5"/>'
            s += f'<text x="{xt:.1f}" y="{yy-6}" text-anchor="{anc}" {F} font-weight="800" font-size="6.6">{a}</text><text x="{xt:.1f}" y="{yy+1}" text-anchor="{anc}" {F} font-size="6">{b}</text>'
        else:
            yy = 68 if tier == 'down' else 84
            s += f'<line x1="{x:.1f}" y1="43" x2="{x:.1f}" y2="{yy-8}" stroke="#999" stroke-width=".5"/>'
            s += f'<text x="{xt:.1f}" y="{yy}" text-anchor="{anc}" {F} font-weight="800" font-size="6.6">{a}</text><text x="{xt:.1f}" y="{yy+7}" text-anchor="{anc}" {F} font-size="6">{b}</text>'
    H = 94 if tiers['down2'] else 78 if tiers['down'] else 58
    return _wrap(spec, s, W, H, flex=True)

def flow(spec, wide=False):
    """Process diagram. lanes: [(lane label, [(step, substep), ...])]; each lane is a row of boxes joined by arrows.
    shade: lane indexes drawn shaded."""
    W = 590 if wide else 280; s = ''; y = 0
    for li, (lab, steps) in enumerate(spec['lanes']):
        if lab: s += f'<text x="0" y="{y+8}" {F} font-weight="800" font-size="6.6" letter-spacing=".08em">{lab.upper()}</text>'; y += 12
        n = len(steps); gap = 18; bw = (W - gap * (n - 1)) / n
        for i, st in enumerate(steps):
            a, b = (list(st) + [''])[:2] if isinstance(st, (list, tuple)) else (st, '')
            x = i * (bw + gap); dark = li in spec.get('shade', [])
            s += (f'<rect x="{x:.1f}" y="{y}" width="{bw:.1f}" height="24" rx="3" fill="{"#e4e4e4" if dark else "#fff"}" stroke="#111" stroke-width=".8"/>'
                  f'<text x="{x+bw/2:.1f}" y="{y+10}" text-anchor="middle" {F} font-weight="800" font-size="6.6">{a}</text>'
                  f'<text x="{x+bw/2:.1f}" y="{y+19}" text-anchor="middle" {F} font-size="6">{b}</text>')
            if i < n - 1:
                ax = x + bw + 2; bx = x + bw + gap - 1
                s += f'<line x1="{ax:.1f}" y1="{y+12}" x2="{bx-3:.1f}" y2="{y+12}" stroke="#111" stroke-width=".9"/><path d="M{bx-4:.1f} {y+9.4} L{bx:.1f} {y+12} L{bx-4:.1f} {y+14.6} Z" fill="#111"/>'
        y += 34
    return _wrap(spec, s, W, y - 6)

def checklist(spec, wide=False):
    """rows: [(mark, title, detail)] with mark 'x' (ruled out), 'o' (open) or 'v' (confirmed)."""
    W = 590 if wide else 280; s = ''; y = 2
    for mark, a, b in spec['rows']:
        if mark == 'x':
            s += f'<line x1="2" y1="{y+4}" x2="9" y2="{y+11}" stroke="#111" stroke-width="1.4"/><line x1="9" y1="{y+4}" x2="2" y2="{y+11}" stroke="#111" stroke-width="1.4"/>'
        elif mark == 'v':
            s += f'<path d="M1 {y+8} L4.5 {y+11.5} L10 {y+3.5}" fill="none" stroke="#111" stroke-width="1.5"/>'
        else:
            s += f'<circle cx="5.5" cy="{y+7.5}" r="3.6" fill="none" stroke="#111" stroke-width="1.2"/>'
        s += f'<text x="15" y="{y+7}" {F} font-weight="800" font-size="6.9">{a}</text><text x="15" y="{y+14.5}" {F} font-size="6.4" fill="#333">{b}</text>'
        y += 20
    return _wrap(spec, s, W, y)

def raw_svg(spec, wide=False):
    """Escape hatch for an explainer diagram: spec['svg'] is SVG markup for a viewBox of width 280 (590 if wide) x spec['height']."""
    return _wrap(spec, spec['svg'], 590 if wide else 280, spec['height'])
