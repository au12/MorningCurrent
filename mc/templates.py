"""Page templates. Each returns the inner HTML of one page from edition data plus the current fit state.

Design rules built in (spec §3): ear-less masthead with a computed sky strip; head blocks hold only
kicker, headline and deck; every story's source box comes at its end; two-story pages give each story
its own column; briefs, fact boxes and charts close any gap; puzzles and answers are generated.
"""
from . import rules as R, almanac as A, puzzles as PZ
from .components import (qr_inline, srcbox, story_src, moon_svg, kicker, headblock, shead, blocks, plain,
                         also, factbox, chart, dom)


def _live(bl):
    return [b for b in bl if b is not None]


def _split(bl, idx, nsent=0):
    """Blocks before and after a page break. With nsent > 0 the paragraph at idx splits after that many
    sentences (the rest continues, unindented, after the jump). A subhead is never left at the bottom."""
    if nsent and idx < len(bl) and bl[idx] is not None and len(bl[idx]) > 2 and isinstance(bl[idx][2], dict):
        ss = bl[idx][2].get('s') or []
        if 0 < nsent < len(ss):
            head = [bl[idx][0], ' '.join(ss[:nsent]), {'s': ss[:nsent], 'jump': True}]
            tail = ['p', ' '.join(ss[nsent:]), {'s': ss[nsent:], 'cont': True}]
            return _live(bl[:idx]) + [head], [tail] + _live(bl[idx + 1:])
    left, right = _live(bl[:idx]), _live(bl[idx:])
    while left and left[-1][0] == 'h4':
        right.insert(0, left.pop())
    return left, right


def page(n, inner, section='', front=False):
    side = 'recto' if n % 2 else 'verso'
    rh = fo = ''
    if not front:
        l, r = (R.TITLE, None) if side == 'verso' else (None, R.TITLE)
        l = l or '{date}'
        r = r or '{date}'
        rh = f'<div class="rhead"><span>{l}</span><span class="sec">{section}</span><span>{r}</span></div>'
        fo = f'<div class="folio">{n}</div>'
    return f'<section class="page {side}{" front" if front else ""}" data-n="{n}">{rh}<div class="inner">{inner}</div>{fo}</section>'


def cols(slot, html, one=False, space=0):
    sp = f' data-space="{space}"' if space else ''
    return f'<div class="cols{" one" if one else ""}" data-slot="{slot}"{sp}>{html}</div>'


def extras(ed, st):
    """The story's own briefs plus any reserve briefs the fitter placed under it."""
    own = st.get('briefs', [])
    added = ed.fit['extra'].get(st['id'], [])
    out = also(st.get('also', f'Also in {st["category"]}'), own + added)
    for k, spec in ed.fit['graphics'].get(st['id'], []):
        out += factbox(*spec) if k == 'facts' else chart(spec)
    return out


def _space(ed, sid):
    return ed.fit['space'].get(sid, 0)


# ------------------------------------------------------------------ front and continuation
def front(ed):
    t0 = ed.sky_today
    sep = '<span class="sep">&middot;</span>'
    strip = ''
    if R.SKY_STRIP:
        rise = t0['mr'] if t0['mr'] != '&mdash;' else f'{t0["mr_next"]} {t0["mr_next_day"]}'
        strip = (f'<div class="skystrip" data-shrink><span>Sunrise {t0["sr"]}</span>{sep}<span>Sunset {t0["ss"]}</span>'
                 f'<span class="sep">&mdash;</span>{moon_svg(t0["lit"] / 100, t0["waning"])}'
                 f'<span>{A.phase_name(t0["lit"], t0["waning"])}, {t0["lit"]}% lit</span>{sep}'
                 f'<span>Moonrise {rise}</span>{sep}<span>Moonset {t0["ms"]}</span></div>')
    index = ''
    if R.INDEX_ON_FRONT:
        cells = ''.join(f'<div><span class="pg">{pg}</span><span class="t">{t}</span>{h}</div>' for pg, t, h in ed.index())
        index = f'<div class="inside">{cells}</div>' if cells else ''
    lead = ed.lead
    a, _ = _split(ed.blocks_of(lead), ed.fit['jump'], ed.fit.get('jump_s', 0))
    return (f'<div class="mast"><div class="title" data-shrink>{R.TITLE}</div><div class="dateline"><span>Vol. {R.VOLUME} &middot; No. {ed.number}</span>'
            f'<span>{ed.pretty}</span><span>{R.TAGLINE}</span></div>{strip}</div>'
            f'{headblock(lead, "h1")}'
            + cols('front', blocks(a) + '<p class="cont">Continued on page 2 &rarr;</p>', space=_space(ed, 'front'))
            + index)


def cont(ed):
    lead = ed.lead
    b = plain(_split(ed.blocks_of(lead), ed.fit['jump'], ed.fit.get('jump_s', 0))[1])
    h = f'<div class="headblock">{kicker(lead["kicker"] + " &middot; Continued from page 1")}<h3>{lead["cont_head"]}</h3></div>'
    body = blocks(b) + story_src(lead) + extras(ed, lead)
    if ed.sidebar:
        s = ed.sidebar
        body += (f'<div class="side"><div class="bhead"><div class="rule thick" style="margin:0 0 5pt"></div>{kicker(s["kicker"])}'
                 f'<h3>{s["headline"]}</h3></div>{blocks(plain(_live(ed.blocks_of(s))))}{story_src(s)}{extras(ed, s)}</div>')
    return h + cols('cont', body, space=_space(ed, 'cont'))


# ------------------------------------------------------------------ story pages
def feature(ed, st):
    return headblock(st) + cols(st['id'], blocks(_live(ed.blocks_of(st)), first_dropcap=True) + story_src(st) + extras(ed, st),
                                space=_space(ed, st['id']))


def split(ed, a, b):
    col = lambda st, first: cols(st['id'], shead(st) + blocks(_live(ed.blocks_of(st)) if first else plain(_live(ed.blocks_of(st))),
                                                              first_dropcap=first)
                                 + story_src(st) + extras(ed, st), one=True, space=_space(ed, st['id']))
    return f'<div class="split">{col(a, True)}{col(b, False)}</div>'


def spread_left(ed, st):
    bl = _split(ed.blocks_of(st), ed.fit['turn'], ed.fit.get('turn_s', 0))[0]
    return '<div class="spreadrule"></div>' + headblock(st, 'h1') + cols(st['id'] + '_l', blocks(bl, first_dropcap=True),
                                                                       space=_space(ed, st['id'] + '_l'))


def spread_right(ed, st):
    bl = plain(_split(ed.blocks_of(st), ed.fit['turn'], ed.fit.get('turn_s', 0))[1])
    h = '<div class="spreadrule"></div>' + cols(st['id'] + '_r', blocks(bl) + story_src(st) + extras(ed, st),
                                                 space=_space(ed, st['id'] + '_r'))
    if st.get('facts'):
        fh = ''.join(f'<div><b>{a}</b>{b}</div>' for a, b in st['facts'][1])
        h += (f'<div class="box shade" style="flex:0 0 auto;margin-top:7pt;padding:5pt 7pt"><div class="boxhead" style="margin-bottom:3pt">'
              f'{st["facts"][0]}</div><div class="facts">{fh}</div></div>')
    if st.get('timeline'):
        h += f'<div style="flex:0 0 auto">{chart(dict(st["timeline"], kind="timeline"), wide=True)}</div>'
    return h


def _odd_items(items):
    return ''.join(f'<div class="odd"><div class="qhead"><h5>{w["head"]}</h5>{qr_inline(w["src"])}</div><p>{w["text"]}</p>'
                   f'{"<p class=srcl>" + w["credit"] + "</p>" if w.get("credit") else ""}</div>' for w in items)


def wonders(ed):
    return (f'<div class="headblock">{kicker("Odds &amp; Ends")}<h2>Small Wonders</h2><div class="deck">{ed.wonders_deck}</div></div>'
            + cols('wonders', _odd_items(ed.printed_wonders()) + also('More Small Wonders', ed.fit['extra'].get('wonders', [])),
                   space=_space(ed, 'wonders')))


def roundup(ed, r):
    """A page of short items (headline, summary, QR) under one theme, for sources that allow only excerpts."""
    deck = f'<div class="deck">{r["deck"]}</div>' if r.get('deck') else ''
    return (f'<div class="headblock">{kicker(r.get("kicker", "In Brief"))}<h2>{r["headline"]}</h2>{deck}</div>'
            + cols(r['id'], _odd_items(ed.items_of(r)) + also('More to read', ed.fit['extra'].get(r['id'], [])),
                   space=_space(ed, r['id'])))


# ------------------------------------------------------------------ almanac
def almanac(ed):
    a, b = ed.sky_today, ed.sky_tomorrow
    lit = lambda d: f'<span class="phi">{moon_svg(d["lit"] / 100, d["waning"], 10)}</span>{d["lit"]}%'

    def picon(name):
        k, w = (0, False) if name.startswith('New') else (.5, False) if name.startswith('First') else (.5, True) if name.startswith('Last') else (1, False)
        return f'<span class="phi">{moon_svg(k, w, 11)}</span>'
    rows = A.sky_rows(ed.date, ed.alm.get('extra', []), ed.fit['cal_rows'])
    cal = ''.join(f'<tr><td class="d">{"&#9733; " if r.get("star") else ""}{r["label"]}</td><td>{r["text"]}</td></tr>' for r in rows)
    ph = ''.join(f'<tr><td>{picon(n)}{n}</td><td class="v">{v}</td></tr>' for n, v, _, _ in A.phases(ed.date))
    tbl = (f'<tr><td></td><td class="v">{a["day"]}</td><td class="v">{b["day"]}</td></tr>'
           + ''.join(f'<tr><td>{lab}</td><td class="v">{a[k]}</td><td class="v">{b[k]}</td></tr>'
                     for lab, k in (('Sunrise', 'sr'), ('Sunset', 'ss'), ('Daylight', 'dl'), ('Moonrise', 'mr'), ('Moonset', 'ms')))
           + f'<tr><td>Moon lit ({A.clock(21, 0)})</td><td class="v">{lit(a)}</td><td class="v">{lit(b)}</td></tr>')
    word = ed.alm.get('word')
    wd = (f'<div class="box shade" style="margin-top:8pt"><div class="boxhead">Word of the Day</div><p class="noind">'
          f'<b style="font-family:Playfair;font-size:12pt">{word[0]}</b> <i>({word[1]}), {word[2]}.</i> {word[3]}</p></div>') if word else ''
    look = ''
    lk = ed.alm.get('lookup') or A.lookup(ed.date)
    if ed.fit['lookup'] and lk:
        t, txt = lk
        look = f'<div class="box fill"><div class="boxhead">{t}</div><p class="noind" style="font-size:8.4pt;line-height:1.3">{txt}</p></div>'
    src = ed.alm.get('src')
    place = R.LOCATION['name']
    note = f'Times are for {place}' + (f'; {R.LOCATION["note"]}' if R.LOCATION.get('note') else ('' if place.endswith('.') else '.'))
    return (f'<div class="headblock">{kicker("The Almanac")}<h2>Sun, Moon &amp; the {ed.date:%B} Sky</h2>'
            f'<div class="deck">{note}</div></div>'
            f'<div class="alm-grid"><div class="box"><div class="boxhead">Today &amp; Tomorrow</div><table class="sun" style="width:100%">{tbl}</table></div>'
            f'<div class="box"><div class="boxhead">Moon Phases Ahead</div><table class="sun" style="width:100%">{ph}</table>'
            f'<p class="noind" style="font-size:7.8pt;margin-top:4pt;line-height:1.25">{A.dst_note(ed.date)}</p></div></div>'
            + cols('almanac', f'<div class="boxhead" style="margin-top:9pt">Sky Calendar</div><table class="cal">{cal}</table>{wd}{look}'
                   + (srcbox(src[0], src[1], src[2]) if src else '')))


# ------------------------------------------------------------------ games
def word(ed):
    pz, P = ed.pz, ed.puzzles
    parts = []
    if pz.get('crypt'):
        C = P['cryptogram']
        crypt = ' '.join(f'<span class="w">{w}</span>' for w in pz['crypt'].split(' '))
        parts.append(f'<div style="flex:0 0 auto"><div class="ptitle">Cryptogram</div><p class="pinstr">Each letter stands for another. {C.get("intro", "")} '
                     f'Hint: <b>{pz["hint"][0]} = {pz["hint"][1]}</b>.</p><div class="crypt">{crypt}</div>'
                     f'<p class="noind" style="text-align:right;font:600 8pt Franklin;margin-top:2pt">&mdash; {pz["crypt_who"]}</p></div>'
                     f'<div class="rule thick" style="margin:9pt 0 7pt"></div>')
    lower = ''
    if pz.get('garage'):
        S = P['scramble']
        scr = ''.join(f'{i}. {s} <span class="blank"></span><br>' for i, (s, _) in enumerate(pz['garage'], 1))
        lower += f'<div><div class="ptitle">{S["title"]}</div><p class="pinstr">{S["intro"]}</p><div class="scramble">{scr}</div></div>'
    if pz.get('ladder'):
        lad, L = pz['ladder'], P['ladder']
        rows = ''.join('<tr>' + ''.join(f'<td>{ch if k in (0, len(lad) - 1) else ""}</td>' for ch in w) + '</tr>' for k, w in enumerate(lad))
        lower += (f'<div><div class="ptitle">Word Ladder</div><p class="pinstr">Turn {lad[0]} into {lad[-1]}, changing one letter per step. '
                  f'Every rung must be a real word.</p><table class="ladder">{rows}</table>'
                  f'<p class="pinstr" style="margin-top:5pt">Par: {len(lad) - 2} steps in between. {L.get("note", "")}</p></div>')
    if lower:
        parts.append(f'<div style="display:grid;grid-template-columns:1.25fr 1fr;gap:16pt;flex:0 0 auto">{lower}</div>')
    return (f'<div class="headblock">{kicker("Games")}<h2>Word Play</h2></div>' + ''.join(parts)
            + f'<div class="rule thick" style="margin:10pt 0 4pt"></div><div class="boxhead" style="border:0;margin:0">Morning Notes</div>'
              f'<div class="notes" style="flex:1 1 auto;overflow:hidden">{"<div></div>" * 14}</div>')


def sudoku(ed):
    pz = ed.pz
    sd = pz['sudoku']
    lv = R.SUDOKU_LEVELS[pz['sudoku_level']]['label']
    rows = ''.join('<tr>' + ''.join(f'<td>{sd[r * 9 + c] or ""}</td>' for c in range(9)) + '</tr>' for r in range(9))
    extra = ''
    if pz.get('teasers') and R.SUDOKU_EXTRA == 'teasers':
        tz = ''.join(f'<div><b>{i}. {t}.</b> {q}</div>' for i, (t, q, a) in enumerate(pz['teasers'], 1))
        src = ed.meta.get('teaser_source', 'stories')
        sub = 'FROM TODAY&rsquo;S STORIES' if src == 'stories' else 'FOR THE COFFEE BREAK'
        extra = (f'<div class="rule thick" style="margin:12pt 0 6pt"></div>'
                 f'<div class="ptitle" style="font-size:13pt">Two-Minute Teasers <span style="font:700 7pt Franklin;letter-spacing:.12em">{sub}</span></div>'
                 f'<div class="teasers">{tz}</div>')
    elif R.SUDOKU_EXTRA in ('kenken', 'futoshiki') and pz.get(R.SUDOKU_EXTRA + '_mini'):
        from .puzzles import extra as PX
        extra = (f'<div class="rule thick" style="margin:12pt 0 6pt"></div>'
                 + PX.render(R.SUDOKU_EXTRA + '_mini', pz[R.SUDOKU_EXTRA + '_mini'], small=True))
    return (f'<div class="headblock">{kicker("Games")}<h2>Sudoku <span style="font:700 9pt Franklin;letter-spacing:.14em;vertical-align:middle">'
            f'&middot; {lv.upper()}</span></h2><p class="pinstr" style="margin-top:3pt">Fill the grid so every row, column and 3&times;3 box '
            f'contains the digits 1 through 9. Sudoku gets a little harder each day from Monday to Sunday.</p></div>'
            f'<table class="sdk" style="flex:0 0 auto">{rows}</table>{extra}')


def xw_table(grid, fill=False):
    nums, _, _ = PZ.entries(grid)
    H, W = len(grid), len(grid[0])
    h = '<table class="xw">'
    for r in range(H):
        h += '<tr>' + ''.join('<td class="b"></td>' if grid[r][c] == '#' else
                              '<td>' + (f'<span class="num">{nums[(r, c)]}</span>' if (r, c) in nums and not fill else '')
                              + (f'<span class="let">{grid[r][c]}</span>' if fill else '') + '</td>' for c in range(W)) + '</tr>'
    return h + '</table>'


def xword(ed):
    if 'crossword' not in ed.pz:          # no crossword today: the page carries logic puzzles instead
        return logic(ed, ('kenken', 'futoshiki', 'wordsearch'))
    xw = ed.pz['crossword']
    H, W = len(xw['grid']), len(xw['grid'][0])
    cl = '<h6>Across</h6>' + ''.join(f'<div><b>{n}</b>{t}</div>' for n, t in xw['across'])
    cl += '<h6 style="margin-top:6pt">Down</h6>' + ''.join(f'<div><b>{n}</b>{t}</div>' for n, t in xw['down'])
    shape = f'A {H}-by-{W} grid today.'
    side = W * R.CROSSWORD['cell_in'] <= (R.PAGE_W - R.MARGIN['inner'] - R.MARGIN['outer']) * 0.47
    pt = ed.fit.get('xw_pt', 8.1)
    st = f'font-size:{pt}pt'
    body = (f'<div style="display:flex;gap:14pt;flex:1 1 auto;min-height:0"><div style="flex:0 0 auto">{xw_table(xw["grid"])}</div>'
            f'<div class="clues cols" data-slot="xword" style="flex:1 1 auto;{st}">{cl}</div></div>') if side else \
           (f'<div style="flex:0 0 auto;margin:0 auto">{xw_table(xw["grid"])}</div>'
            f'<div class="clues cols" data-slot="xword" style="margin-top:10pt;flex:1 1 auto;{st}">{cl}</div>')
    return (f'<div class="headblock">{kicker("Games")}<h2>The Morning Crossword</h2>'
            f'<p class="pinstr" style="margin:2pt 0 6pt">{shape} Answers in tomorrow&rsquo;s paper.</p></div>{body}')


def logic(ed, names=None):
    from .puzzles import extra as PX
    items = [(n, ed.pz[n]) for n in (names or R.LOGIC_PUZZLES) if ed.pz.get(n)][:3]
    body = ''.join(f'<div class="lp{" wide" if n in ("wordsearch", "nonogram") else ""}">{PX.render(n, p)}</div>' for n, p in items)
    z = ed.fit.get('logic_zoom', 1.0)
    return (f'<div class="headblock">{kicker("Games")}<h2>Logic Corner</h2>'
            f'<p class="pinstr" style="margin:2pt 0 6pt">Pure reasoning, no guessing needed: every puzzle has exactly one solution. '
            f'Answers in tomorrow&rsquo;s paper.</p></div><div class="logic" style="zoom:{z}">{body}</div>')


# ------------------------------------------------------------------ back page
def about_text(ed):
    if R.ABOUT:
        return R.ABOUT
    who = f' for {R.HOUSEHOLD}' if R.HOUSEHOLD else ''
    gen = ed.meta.get('generator', 'manual')
    if gen == 'auto':
        how = ('assembled automatically from public-domain and openly licensed sources, with headlines and summaries '
               'from other outlets')
    elif gen == 'ai':
        how = 'researched and written with Claude from the sources listed below'
    else:
        how = 'researched and written by Claude'
    return (f'<i>{R.TITLE}</i> is a printed morning paper of recent discoveries and good news, {how}{who}. '
            f'Every story links to its source; scan the codes to read further.')


def answers(prev):
    """The previous edition's answers (whatever puzzles it had), as an HTML block."""
    from .puzzles import extra as PX
    sol, giv = prev['sudoku_sol'], prev['sudoku']
    srows = ''.join('<tr>' + ''.join(f'<td class="{"g" if giv[r * 9 + c] else ""}">{sol[r * 9 + c]}</td>' for c in range(9)) + '</tr>' for r in range(9))
    xw = f'<div><h5>Crossword</h5>{xw_table(prev["crossword"]["grid"], True)}</div>' if prev.get('crossword') else ''
    words = ''
    if prev.get('crypt_plain'):
        plainq = prev['crypt_plain'].strip().lower()
        plainq = plainq[:1].upper() + plainq[1:]
        words += f'<h5>Cryptogram</h5><p>&ldquo;{plainq}&rdquo; &mdash; {prev["crypt_who"].title()}</p>'
    if prev.get('garage'):
        scr = ' '.join(f'{i}. {w.title()}' for i, (_, w) in enumerate(prev['garage'], 1))
        words += f'<h5 style="margin-top:5pt">{prev.get("scramble_title", "Scramble")}</h5><p>{scr}</p>'
    if prev.get('ladder'):
        words += f'<h5 style="margin-top:5pt">Word Ladder</h5><p>{" &rarr; ".join(prev["ladder"])}</p>'
    if prev.get('teasers'):
        tz = ' '.join(f'{i}. {a}.' for i, (_, _, a) in enumerate(prev['teasers'], 1))
        words += f'<h5 style="margin-top:5pt">Teasers</h5><p>{tz}</p>'
    for name in PX.NAMES:
        if prev.get(name):
            words += PX.answer(name, prev[name])
    return f'<div class="ans">{xw}<div><h5>Sudoku</h5><table class="sdk">{srows}</table></div><div>{words}</div></div>'


def back(ed):
    prev, label = ed.prev_puzzles()
    if prev:
        box = (f'<div class="box" style="flex:0 0 auto"><div class="boxhead" style="display:flex;justify-content:space-between">'
               f'<span>Answers to {label}</span><span style="font-weight:600;letter-spacing:.06em">Printed upside down</span></div>'
               f'<div class="upside">{answers(prev)}</div><p class="noind" style="font-size:7.4pt;font-style:italic;margin-top:5pt;text-align:left">'
               f'Today&rsquo;s answers appear in tomorrow&rsquo;s paper.</p></div>')
    else:
        box = '<div class="box" style="flex:0 0 auto"><p class="noind">No previous edition&rsquo;s answers today. Today&rsquo;s appear tomorrow.</p></div>'
    sl = ''.join(f'<div><b>{t}</b> &middot; {o}</div>' for t, o in ed.source_rows())
    return (f'<div class="headblock">{kicker("The Back Page")}<h2>Answers &amp; Sources</h2></div>{box}'
            + cols('back', f'<div class="box shade" style="margin:9pt 0 8pt;font-size:8pt;line-height:1.3"><div class="boxhead">About this paper</div>'
                   f'<p class="noind" style="text-align:left">{about_text(ed)}</p></div>'
                   f'<div class="boxhead">Sources</div><div class="srclist">{sl}</div>'
                   f'<div class="notesbox"><div class="boxhead" style="border:0;margin:9pt 0 0">Notes</div><div class="notes">{"<div></div>" * ed.fit["note_lines"]}</div></div>'))
