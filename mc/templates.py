"""Page templates. Each returns the Typst code for one page's body from edition data plus the current fit state.

Design rules built in (spec §3): ear-less masthead with a computed sky strip; head blocks hold only
kicker, headline and deck; every story's source box comes at its end; two-story pages give each story
its own column; briefs, fact boxes and charts close any gap; puzzles and answers are generated.
Each story column region is a `region(...)` in mc/paper.typ; the fitter measures it by slot name.
"""
from . import almanac as A, puzzles as PZ, rules as R
from .components import (Region, also, blocks, chart, code_block, fact_items, factbox, headblock, kicker, moon, plain,
                         qr_inline, shead, srcbox, story_src, dom)
from .ty import array, q, rich


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


def page(n, body, section='', front=False):
    verso = n % 2 == 0
    lh, rh = (R.TITLE, '{date}') if verso else ('{date}', R.TITLE)
    return (f'#page-frame({n}, front: {"true" if front else "false"}, section: {rich(section)}, '
            f'lhead: {rich(lh)}, rhead: {rich(rh)}, {body})\n')


def region(slot, parts, n=2, space=0, height=None):
    h = f', height: {height}' if height else ''
    return f'region({q(slot)}, n: {n}, space: {space}{h}, {code_block(parts)})'


def extras(ed, rg, st):
    """The story's own briefs plus any reserve briefs the fitter placed under it, and fitted graphics."""
    own = st.get('briefs', [])
    added = ed.fit['extra'].get(st['id'], [])
    out = also(rg, st.get('also', f'Also in {st["category"]}'), own + added)
    for k, spec in ed.fit['graphics'].get(st['id'], []):
        out.append(factbox(rg, *spec) if k == 'facts' else chart(rg, spec))
    return out


def _space(ed, sid):
    return ed.fit['space'].get(sid, 0)


def _rg(ed, slot):
    return Region(slot, _space(ed, slot))


# ------------------------------------------------------------------ front and continuation
def front(ed):
    t0 = ed.sky_today
    strip = 'none'
    if R.SKY_STRIP:
        rise = t0['mr'] if t0['mr'] != '&mdash;' else f'{t0["mr_next"]} {t0["mr_next_day"]}'
        strip = ' + '.join([rich(f'Sunrise {t0["sr"]}'), 'sep', rich(f'Sunset {t0["ss"]}'), '[ — ]',
                            moon(t0['lit'] / 100, t0['waning']), '[ ]',
                            rich(f'{A.phase_name(t0["lit"], t0["waning"])}, {t0["lit"]}% lit'), 'sep',
                            rich(f'Moonrise {rise}'), 'sep', rich(f'Moonset {t0["ms"]}')])
        strip = f'({strip})'
    parts = [f'masthead({rich(R.TITLE)}, {rich(f"Vol. {R.VOLUME} &middot; No. {ed.number}")}, {rich(ed.pretty)}, '
             f'{rich(R.TAGLINE)}, {strip})', headblock(ed.lead, 'h1')]
    lead = ed.lead
    a, _ = _split(ed.blocks_of(lead), ed.fit['jump'], ed.fit.get('jump_s', 0))
    rg = _rg(ed, 'front')
    body = blocks(rg, a) + [f'cont-line({rg.args()}, [Continued on page 2 →])']
    parts.append(region('front', body, space=rg.space))
    if R.INDEX_ON_FRONT:
        cells = ed.index()
        if cells:
            parts.append('index-cells(' + array(f'({rich(pg)}, {rich(t)}, {rich(h)})' for pg, t, h in cells) + ')')
    return code_block(parts)


def side_head(rg, s):
    return f'side-head({rg.args()}, {rich(s["kicker"])}, {rich(s["headline"])})'


def cont(ed):
    lead = ed.lead
    b = plain(_split(ed.blocks_of(lead), ed.fit['jump'], ed.fit.get('jump_s', 0))[1])
    head = (f'block(below: 2pt, {{ {kicker(lead["kicker"] + " &middot; Continued from page 1")}; '
            f'hed(T.h3, {rich(lead["cont_head"])}); v(4pt) }})')
    rg = _rg(ed, 'cont')
    body = blocks(rg, b) + [story_src(rg, lead)] + extras(ed, rg, lead)
    if ed.sidebar:
        s = ed.sidebar
        body += [side_head(rg, s)] + blocks(rg, plain(_live(ed.blocks_of(s)))) + [story_src(rg, s)] + extras(ed, rg, s)
    return code_block([head, region('cont', body, space=rg.space)])


# ------------------------------------------------------------------ story pages
def feature(ed, st):
    rg = _rg(ed, st['id'])
    body = blocks(rg, _live(ed.blocks_of(st)), first_dropcap=True) + [story_src(rg, st)] + extras(ed, rg, st)
    return code_block([headblock(st), region(st['id'], body, space=rg.space)])


def split(ed, a, b):
    def col(st, first):
        rg = _rg(ed, st['id'])
        bl = _live(ed.blocks_of(st))
        body = ([f'blk({rg.args()}, {shead(st)})'] + blocks(rg, bl if first else plain(bl), first_dropcap=first)
                + [story_src(rg, st)] + extras(ed, rg, st))
        return region(st['id'], body, n=1, space=rg.space, height='100%')
    return code_block([f'split-pair({col(a, True)}, {col(b, False)})'])


def spread_left(ed, st):
    bl = _split(ed.blocks_of(st), ed.fit['turn'], ed.fit.get('turn_s', 0))[0]
    slot = st['id'] + '_l'
    rg = _rg(ed, slot)
    return code_block(['spread-rule()', headblock(st, 'h1'), region(slot, blocks(rg, bl, first_dropcap=True), space=rg.space)])


def spread_right(ed, st):
    bl = plain(_split(ed.blocks_of(st), ed.fit['turn'], ed.fit.get('turn_s', 0))[1])
    slot = st['id'] + '_r'
    rg = _rg(ed, slot)
    parts = ['spread-rule()', region(slot, blocks(rg, bl) + [story_src(rg, st)] + extras(ed, rg, st), space=rg.space)]
    x = Region('_fixed')
    if st.get('facts'):
        parts.append(f'block(above: 7pt, ibox(shade: true, inset: (x: 7pt, y: 5pt), {{ boxhead({rich(st["facts"][0])}, below: 3pt); '
                     f'factgrid({fact_items(st["facts"][1])}, 4) }}))')
    if st.get('timeline'):
        parts.append(chart(x, dict(st['timeline'], kind='timeline'), wide=True))
    return code_block(parts)


def _odd_items(rg, items):
    out = []
    for w in items:
        cr = rich(w['credit']) if w.get('credit') else 'none'
        out.append(f'odd({rg.args()}, space: {rg.space}, {rich(w["head"])}, {rich(w["text"])}, {qr_inline(w["src"])}, credit: {cr})')
    return out


def wonders(ed):
    rg = _rg(ed, 'wonders')
    head = f'headblock([Odds & Ends], "h2", [Small Wonders], {rich(ed.wonders_deck) if ed.wonders_deck else "none"})'
    body = _odd_items(rg, ed.printed_wonders()) + also(rg, 'More Small Wonders', ed.fit['extra'].get('wonders', []))
    return code_block([head, region('wonders', body, space=rg.space)])


def roundup(ed, r):
    """A page of short items (headline, summary, QR) under one theme, for sources that allow only excerpts."""
    rg = _rg(ed, r['id'])
    head = f'headblock({rich(r.get("kicker", "In Brief"))}, "h2", {rich(r["headline"])}, {rich(r["deck"]) if r.get("deck") else "none"})'
    body = _odd_items(rg, ed.items_of(r)) + also(rg, 'More to read', ed.fit['extra'].get(r['id'], []))
    return code_block([head, region(r['id'], body, space=rg.space)])


# ------------------------------------------------------------------ almanac
def _phase_icon(name):
    k, w = (0, False) if name.startswith('New') else (.5, False) if name.startswith('First') else (.5, True) if name.startswith('Last') else (1, False)
    return moon(k, w, 11)


def almanac(ed):
    a, b = ed.sky_today, ed.sky_tomorrow
    lit = lambda d: f'({moon(d["lit"] / 100, d["waning"], 10)} + [ ] + {rich(str(d["lit"]) + "%")})'
    rows = [('[]', rich(a['day']), rich(b['day']))]
    rows += [(rich(lab), rich(a[k]), rich(b[k])) for lab, k in (('Sunrise', 'sr'), ('Sunset', 'ss'), ('Daylight', 'dl'),
                                                               ('Moonrise', 'mr'), ('Moonset', 'ms'))]
    rows += [(rich(f'Moon lit ({A.clock(21, 0)})'), lit(a), lit(b))]
    sun = 'suntable(' + array('(' + ', '.join(r) + ')' for r in rows) + ')'
    ph = 'phasetable(' + array(f'({_phase_icon(n)} + [ ] + {rich(n)}, {rich(v)})' for n, v, _, _ in A.phases(ed.date)) + ')'
    place = R.LOCATION['name']
    note = f'Times are for {place}' + (f'; {R.LOCATION["note"]}' if R.LOCATION.get('note') else ('' if place.endswith('.') else '.'))
    head = f'headblock([The Almanac], "h2", {rich(f"Sun, Moon &amp; the {ed.date:%B} Sky")}, {rich(note)})'
    boxes = (f'grid(columns: (1fr, 1fr), column-gutter: 9pt, ibox({{ boxhead([Today & Tomorrow]); {sun} }}), '
             f'ibox({{ boxhead([Moon Phases Ahead]); {ph}; small-note({rich(A.dst_note(ed.date))}) }}))')
    rg = Region('almanac')
    cal_rows = A.sky_rows(ed.date, ed.alm.get('extra', []), ed.fit['cal_rows'])
    cal = 'caltable(' + array(f'({rich(("★ " if r.get("star") else "") + r["label"])}, {rich(r["text"])})' for r in cal_rows) + ')'
    parts = [f'blk({rg.args()}, block(above: 9pt, boxhead([Sky Calendar])))', f'blk({rg.args()}, {cal})']
    word = ed.alm.get('word')
    if word:
        parts.append(f'blk({rg.args()}, word-box({rich(word[0])}, {rich(word[1])}, {rich(word[2])}, {rich(word[3])}))')
    lk = ed.alm.get('lookup') or A.lookup(ed.date)
    if ed.fit['lookup'] and lk:
        parts.append(f'blk({rg.args()}, lookup-box({rich(lk[0])}, {rich(lk[1])}))')
    src = ed.alm.get('src')
    if src:
        parts.append(srcbox(rg, src[0], src[1], src[2]))
    return code_block([head, boxes, region('almanac', parts)])


# ------------------------------------------------------------------ games
def word(ed):
    pz, P = ed.pz, ed.puzzles
    parts = ['headblock([Games], "h2", [Word Play], none)']
    if pz.get('crypt'):
        C = P['cryptogram']
        ws = array(q(w) for w in pz['crypt'].split(' ') if w)
        hint = f'Each letter stands for another. {C.get("intro", "")} Hint: <b>{pz["hint"][0]} = {pz["hint"][1]}</b>.'
        parts.append(f'cryptogram({rich(hint)}, {ws}, {rich(pz["crypt_who"])})')
        parts.append('rule(above: 9pt, below: 7pt, weight: 2pt)')
    lower = []
    if pz.get('garage'):
        S = P['scramble']
        items = array(f'({q(s)})' for s, _ in pz['garage'])
        lower.append(f'scramble({rich(S["title"])}, {rich(S["intro"])}, {items})')
    if pz.get('ladder'):
        lad, L = pz['ladder'], P['ladder']
        intro = f'Turn {lad[0]} into {lad[-1]}, changing one letter per step. Every rung must be a real word.'
        note = f'Par: {len(lad) - 2} steps in between. {L.get("note", "")}'
        lower.append(f'ladder({array(q(w) for w in lad)}, {rich(intro)}, {rich(note)})')
    if lower:
        parts.append(f'grid(columns: (1.25fr, 1fr), column-gutter: 16pt, {", ".join(lower)})')
    parts.append('rule(above: 10pt, below: 4pt, weight: 2pt)')
    parts.append('boxhead([Morning Notes], stroke: false, below: 0pt)')
    parts.append('notes-lines(40, height: 1fr)')
    return code_block(parts)


def sudoku_grid(cells, size, givens=None, small=False):
    out = []
    for r in range(9):
        for c in range(9):
            v = cells[r * 9 + c]
            w = 600 if not small else (800 if givens and givens[r * 9 + c] else 500)
            fs = size * 32 if not small else 7.4
            out.append(f'sans({fs:.1f}pt, weight: {w}, [{v or ""}])')
    return f'sudoku-grid({size:.3f}in, {array(out)})'


def sudoku(ed):
    pz = ed.pz
    lv = R.SUDOKU_LEVELS[pz['sudoku_level']]['label']
    head = (f'block(below: 2pt, {{ kicker([Games]); hed(T.h2, [Sudoku] + h(6pt) + box(baseline: -2pt, caps(9pt, weight: 700, '
            f'track: 0.14em, {rich("&middot; " + lv)}))); pinstr(above: 3pt, [Fill the grid so every row, column and 3×3 box contains '
            f'the digits 1 through 9. Sudoku gets a little harder each day from Monday to Sunday.]) }})')
    parts = [head, 'v(4pt)', f'align(center, {sudoku_grid(pz["sudoku"], R.SIZES["sudoku_cell"])})']
    if pz.get('teasers') and R.SUDOKU_EXTRA == 'teasers':
        src = ed.meta.get('teaser_source', 'stories')
        sub = 'FROM TODAY&rsquo;S STORIES' if src == 'stories' else 'FOR THE COFFEE BREAK'
        tz = array(f'({rich(f"{i}. {t}.")}, {rich(qq)})' for i, (t, qq, _) in enumerate(pz['teasers'], 1))
        parts += ['rule(above: 12pt, below: 6pt, weight: 2pt)', f'teasers({rich(sub)}, {tz})']
    elif R.SUDOKU_EXTRA in ('kenken', 'futoshiki') and pz.get(R.SUDOKU_EXTRA + '_mini'):
        from .puzzles import extra as PX
        parts += ['rule(above: 12pt, below: 6pt, weight: 2pt)', PX.render(R.SUDOKU_EXTRA + '_mini', pz[R.SUDOKU_EXTRA + '_mini'], small=True)]
    return code_block(parts)


def xw_table(grid, fill=False, cell=None, letter_pt=7.5):
    nums, _, _ = PZ.entries(grid)
    H, W = len(grid), len(grid[0])
    cell = cell or R.CROSSWORD['cell_in']
    cells = []
    for r in range(H):
        for c in range(W):
            if grid[r][c] == '#':
                cells.append('table.cell(fill: ink, [])')
            elif fill:
                cells.append(f'sans({letter_pt}pt, weight: 700, [{grid[r][c]}])')
            elif (r, c) in nums:
                cells.append(f'place(top + left, dx: 1.5pt, dy: 1pt, sans(6.3pt, weight: 600, [{nums[(r, c)]}]))')
            else:
                cells.append('[]')
    return f'xw-grid({W}, {H}, {cell:.3f}in, {array(cells)})'


def xword(ed):
    if 'crossword' not in ed.pz:          # no crossword today: the page carries logic puzzles instead
        return logic(ed, ('kenken', 'futoshiki', 'wordsearch'))
    xw = ed.pz['crossword']
    H, W = len(xw['grid']), len(xw['grid'][0])
    rg = Region('xword')
    clues = [f'blk({rg.args()}, clue-head([Across]))']
    clues += [f'blk({rg.args()}, clue({q(n)}, {rich(t)}))' for n, t in xw['across']]
    clues += [f'blk({rg.args()}, clue-head([Down], above: 6pt))']
    clues += [f'blk({rg.args()}, clue({q(n)}, {rich(t)}))' for n, t in xw['down']]
    pt = ed.fit.get('xw_pt', 8.1)
    side = W * R.CROSSWORD['cell_in'] <= (R.PAGE_W - R.MARGIN['inner'] - R.MARGIN['outer']) * 0.47
    reg = f'text(size: {pt}pt, {region("xword", clues, height="100%")})'
    head = (f'block(below: 6pt, {{ kicker([Games]); hed(T.h2, [The Morning Crossword]); '
            f'pinstr(above: 2pt, below: 0pt, [A {H}-by-{W} grid today. Answers in tomorrow’s paper.]) }})')
    if side:
        body = f'block(height: 1fr, grid(columns: (auto, 1fr), column-gutter: 14pt, rows: (100%,), {xw_table(xw["grid"])}, {reg}))'
    else:
        body = f'align(center, {xw_table(xw["grid"])})\nv(10pt)\nblock(height: 1fr, {reg})'
    return code_block([head, body])


def logic(ed, names=None):
    from .puzzles import extra as PX
    items = [(n, ed.pz[n]) for n in (names or R.LOGIC_PUZZLES) if ed.pz.get(n)][:3]
    cells = []
    for n, p in items:
        r = PX.render(n, p)
        cells.append(f'grid.cell(colspan: 2, {r})' if n in ('wordsearch', 'nonogram') else r)
    z = ed.fit.get('logic_zoom', 1.0)
    head = (f'block(below: 6pt, {{ kicker([Games]); hed(T.h2, [Logic Corner]); pinstr(above: 2pt, below: 0pt, [Pure reasoning, '
            f'no guessing needed: every puzzle has exactly one solution. Answers in tomorrow’s paper.]) }})')
    body = (f'scale({z * 100:.0f}%, origin: top + left, reflow: true, grid(columns: (1fr, 1fr), column-gutter: 16pt, row-gutter: 12pt, '
            f'{", ".join(cells) or "[]"}))')
    return code_block([head, body])


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
    """The previous edition's answers (whatever puzzles it had), as Typst code."""
    from .puzzles import extra as PX
    cols = []
    if prev.get('crossword'):
        cols.append(f'stack(ans-head([Crossword]), {xw_table(prev["crossword"]["grid"], True, cell=0.19, letter_pt=7)})')
    cols.append(f'stack(ans-head([Sudoku]), {sudoku_grid(prev["sudoku_sol"], 0.19, givens=prev["sudoku"], small=True)})')
    words = []
    if prev.get('crypt_plain'):
        plainq = prev['crypt_plain'].strip().lower()
        plainq = plainq[:1].upper() + plainq[1:]
        who = prev['crypt_who'].title()
        words += ['ans-head([Cryptogram])', f'ans-text({rich(f"&ldquo;{plainq}&rdquo; &mdash; {who}")})']
    if prev.get('garage'):
        scr = ' '.join(f'{i}. {w.title()}' for i, (_, w) in enumerate(prev['garage'], 1))
        words += [f'block(above: 5pt, ans-head({rich(prev.get("scramble_title", "Scramble"))}))', f'ans-text({rich(scr)})']
    if prev.get('ladder'):
        words += ['block(above: 5pt, ans-head([Word Ladder]))', f'ans-text({rich(" &rarr; ".join(prev["ladder"]))})']
    if prev.get('teasers'):
        tz = ' '.join(f'{i}. {a}.' for i, (_, _, a) in enumerate(prev['teasers'], 1))
        words += ['block(above: 5pt, ans-head([Teasers]))', f'ans-text({rich(tz)})']
    for name in PX.NAMES:
        if prev.get(name):
            a = PX.answer(name, prev[name])
            if a:
                words.append(a)
    cols.append(f'stack({", ".join(words) or "[]"})')
    widths = ', '.join(['auto'] * (len(cols) - 1) + ['1fr'])
    return f'grid(columns: ({widths}), column-gutter: 12pt, {", ".join(cols)})'


def back(ed):
    prev, label = ed.prev_puzzles()
    if prev:
        box = (f'ibox({{ block(below: 5pt, width: 100%, stroke: (bottom: 1.4pt + ink), inset: (bottom: 2pt), grid(columns: (1fr, auto), '
               f'caps(7.2pt, track: 0.16em, {rich("Answers to " + label)}), caps(7.2pt, weight: 600, track: 0.06em, [Printed upside down]))); '
               f'upside({answers(prev)}); v(5pt); small-note(emph([Today’s answers appear in tomorrow’s paper.])) }})')
    else:
        box = 'ibox(par(first-line-indent: 0pt, [No previous edition’s answers today. Today’s appear tomorrow.]))'
    rg = Region('back')
    parts = [f'blk({rg.args()}, about-box({rich(about_text(ed))}))', f'blk({rg.args()}, boxhead([Sources]))']
    parts += [f'blk({rg.args()}, src-row({rich(t)}, {rich(o)}))' for t, o in ed.source_rows()]
    parts.append(f'blk({rg.args()}, block(above: 9pt, {{ boxhead([Notes], stroke: false, below: 0pt); notes-lines({ed.fit["note_lines"]}) }}))')
    return code_block(['headblock([The Back Page], "h2", [Answers & Sources], none)', box, region('back', parts)])
