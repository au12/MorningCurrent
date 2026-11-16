"""Load an edition's content, plan its pages and render the HTML.

An edition's content lives in `<data>/editions/<date>/edition.json` (or, for editions written by
hand or by the original Claude Code routine, a trusted `edition.py` module). It holds only content:
stories as block lists, briefs, Small Wonders, roundups, puzzle inputs and crossword clues. Page
order, running heads, page references, the index, the sources list, the almanac and every puzzle are
derived here from rules.

Content format (JSON; the legacy Python module uses the same names in UPPER CASE):

    lead      story dict (+ cont_head)         sidebar   story dict or null
    units     [["feature", S], ["split", A, B], ["roundup", R], ["spread", S]]
    wonders_deck, wonders [brief], reserve [brief]
    almanac   {word, extra, src, teaser, lookup}
    puzzles   {cryptogram, scramble, ladder, teasers, crossword}
    number    optional edition number (default: ledger max + 1)
    meta      {generator, notes, ...}   (free-form, not printed)
"""
import datetime
import importlib.util
import json
import os
import re

from . import paths, rules as R, almanac as A, puzzles as PZ, templates as T

EDITIONS = None   # legacy name; use paths.editions_dir()


def ledger():
    p = paths.ledger_file()
    if not os.path.exists(p):
        return {'editions': []}
    with open(p) as f:
        return json.load(f)


# ------------------------------------------------------------------ content loading
def _norm(x):
    """Tuples -> lists and dates -> ISO strings, recursively (so legacy modules match JSON)."""
    if isinstance(x, (list, tuple)):
        return [_norm(v) for v in x]
    if isinstance(x, dict):
        return {k: _norm(v) for k, v in x.items()}
    if isinstance(x, (datetime.date, datetime.datetime)):
        return x.isoformat()
    return x


def load_legacy_module(path):
    name = 'edition_' + re.sub(r'\W', '_', os.path.basename(os.path.dirname(path)))
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    out = dict(lead=m.LEAD, sidebar=getattr(m, 'SIDEBAR', None), units=m.UNITS,
               wonders_deck=getattr(m, 'WONDERS_DECK', ''), wonders=getattr(m, 'WONDERS', []),
               reserve=list(getattr(m, 'RESERVE', [])), almanac=getattr(m, 'ALMANAC', {}),
               puzzles=getattr(m, 'PUZZLES', {}), meta={'generator': 'manual', 'format': 'edition.py'})
    if hasattr(m, 'NUMBER'):
        out['number'] = m.NUMBER
    return _norm(out)


def load_content(d, allow_py=True):
    j, py = os.path.join(d, 'edition.json'), os.path.join(d, 'edition.py')
    if os.path.exists(j):
        with open(j) as f:
            return json.load(f)
    if os.path.exists(py):
        if not allow_py:
            raise PermissionError(f'{py}: Python edition files run only from the command line '
                                  f'(convert it with `python -m mc convert {os.path.basename(d)}`)')
        return load_legacy_module(py)
    raise FileNotFoundError(f'no edition.json or edition.py in {d}')


def save_content(d, content):
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, 'edition.json.tmp')
    with open(tmp, 'w') as f:
        json.dump(_norm(content), f, indent=1, ensure_ascii=False)
    os.replace(tmp, os.path.join(d, 'edition.json'))


def _src_url(src):
    return src if isinstance(src, str) else src[0]


# ------------------------------------------------------------------ trimming (auto-written stories)
def trimmed_blocks(st, n):
    """The story's blocks with its first `n` trim steps applied. Dropped blocks become None so that
    jump/turn indexes keep pointing at the same blocks. Steps: int (drop block) or [block, sentence].
    Paragraphs with a sentence list carry it as a third element ({'s': [...]}) for page-break splitting."""
    bl = [list(b) for b in st['blocks']]
    sents = {int(k): list(v) for k, v in st.get('sents', {}).items()}
    drop_s = {}
    for step in (st.get('trim') or [])[:n or 0]:
        if isinstance(step, int):
            bl[step] = None
        else:
            drop_s.setdefault(step[0], set()).add(step[1])
    for i, ss in sents.items():
        if i >= len(bl) or bl[i] is None or bl[i][0] not in ('p', 'dropcap'):
            continue
        keep = [x for k, x in enumerate(ss) if k not in drop_s.get(i, set())]
        bl[i] = [bl[i][0], ' '.join(keep), {'s': keep}] if keep else None
    # a subhead with nothing left under it goes too
    nxt = None
    for i in range(len(bl) - 1, -1, -1):
        if bl[i] is None:
            continue
        if bl[i][0] == 'h4' and (nxt is None or nxt in ('h4', 'note')):
            bl[i] = None
            continue
        nxt = bl[i][0]
    if st.get('verbatim') and any(b is None for b in bl) and st.get('excerpt_note'):
        last = max(i for i, b in enumerate(bl) if b is not None)
        bl.insert(last + 1, ['note', st['excerpt_note']])
    return bl


def live(bl):
    return [b for b in bl if b is not None]


# ------------------------------------------------------------------ the edition
class Edition:
    def __init__(self, date, content=None, allow_py=True, data_dir=None):
        self.dir = paths.edition_dir(date)
        self.c = c = content if content is not None else load_content(self.dir, allow_py=allow_py)
        self.date = datetime.date.fromisoformat(date)
        self.pretty = f'{self.date:%A, %B} {self.date.day}, {self.date.year}'
        prior = [e['number'] for e in ledger()['editions'] if e['date'] < date and isinstance(e.get('number'), int)]
        self.number = c.get('number') or (max(prior) + 1 if prior else 1)
        self.lead, self.sidebar = c['lead'], c.get('sidebar')
        self.units = [list(u) for u in c.get('units', [])]
        self.wonders, self.wonders_deck = c.get('wonders', []), c.get('wonders_deck', '')
        self.reserve = list(c.get('reserve', []))
        self.alm = dict(c.get('almanac') or {})
        if self.alm.get('extra'):
            self.alm['extra'] = [[datetime.date.fromisoformat(r[0]) if isinstance(r[0], str) else r[0]] + list(r[1:])
                                 for r in self.alm['extra']]
        self.puzzles = c.get('puzzles', {})
        self.meta = c.get('meta', {})
        self.sky_today, self.sky_tomorrow = A.day_table(self.date), A.day_table(self.date + datetime.timedelta(days=1))
        spreads = [u for u in self.units if u[0] == 'spread']
        assert len(spreads) <= 1, 'at most one spread (the Deep Dive)'
        self.spread = spreads[0][1] if spreads else None
        self.tail = [t for t in R.TAIL]
        if 'wonders' in self.tail and not self.wonders:
            self.tail.remove('wonders')
        self.pages_n = self._page_count()
        st = self.spread
        self.fit = dict(jump=self._default_jump(), turn=self._default_turn(st) if st else 0, jump_s=0, turn_s=0, extra={},
                        graphics={}, cal_rows=11, lookup=True, note_lines=10, trim={}, space={}, tried=set(), search={})
        saved = os.path.join(self.dir, 'fit.json')   # the last build's fit, so a rebuild starts where it ended
        if os.path.exists(saved):
            with open(saved) as f:
                sv = json.load(f)
            for k in ('jump', 'turn', 'jump_s', 'turn_s', 'cal_rows', 'lookup', 'note_lines', 'trim', 'space', 'xw_pt', 'logic_zoom'):
                if k in sv:
                    self.fit[k] = sv[k]
            for sid, heads in sv.get('extra', {}).items():
                for h in heads:
                    b = next((x for x in self.reserve if x['head'] == h), None)
                    if b:
                        self.reserve.remove(b)
                        self.fit['extra'].setdefault(sid, []).append(b)
        self.plan()

    # -------------------------------------------------------------- page count and plan
    def _page_count(self):
        singles = [u for u in self.units if u[0] != 'spread']
        n = len(R.HEAD) + len(singles) + len(self.tail) + (2 if self.spread else 0)
        if n % 4:
            raise ValueError(f'{len(singles)} single-page units, {len(self.tail)} tail sections'
                             f'{" and a spread" if self.spread else ""} make {n} pages, not a multiple of 4; '
                             f'units needed for 16 pp: {R.unit_count(16, self.tail, bool(self.spread))}, '
                             f'12 pp: {R.unit_count(12, self.tail, bool(self.spread))}')
        return n

    def save_fit(self):
        f = {k: v for k, v in self.fit.items() if k in ('jump', 'turn', 'cal_rows', 'lookup', 'note_lines')}
        for k in ('jump_s', 'turn_s', 'xw_pt', 'logic_zoom'):
            if self.fit.get(k) not in (None, 0, 8.1, 1.0):
                f[k] = self.fit[k]
        f['trim'] = {k: v for k, v in self.fit['trim'].items() if v}
        f['space'] = {k: v for k, v in self.fit['space'].items() if v}
        f['extra'] = {k: [b['head'] for b in v] for k, v in self.fit['extra'].items() if v}
        if not f['trim']:
            del f['trim']
        if not f['space']:
            del f['space']
        with open(os.path.join(self.dir, 'fit.json'), 'w') as fh:
            json.dump(f, fh, indent=1)

    def _default_jump(self):
        b = self.lead['blocks']
        j = [i for i, x in enumerate(b) if x[0] == 'jump']
        return j[0] if j else max(2, len(b) // 3)

    def _default_turn(self, st):
        b = st['blocks']
        j = [i for i, x in enumerate(b) if x[0] == 'turn']
        return j[0] if j else len(b) // 2 + 1

    def stories(self):
        """Every story with a head and source box (roundup items are briefs, not stories)."""
        out = [self.lead] + ([self.sidebar] if self.sidebar else [])
        for u in self.units:
            if u[0] != 'roundup':
                out += list(u[1:])
        return out

    def roundups(self):
        return [u[1] for u in self.units if u[0] == 'roundup']

    def items_of(self, r):
        """A roundup's items after the fitter's trim (items drop from the end)."""
        n = self.fit['trim'].get(r['id'], 0)
        return r['items'][:len(r['items']) - n] if n else r['items']

    def printed_wonders(self):
        n = self.fit['trim'].get('wonders', 0)
        return self.wonders[:len(self.wonders) - n] if n else self.wonders

    def plan(self):
        """Page list: (id, template, args, section). The spread lands on N/2, N/2+1; tail sections run last
        in order, and any that don't fit after the spread move (in order) to just before it."""
        N = self.pages_n
        singles = [u for u in self.units if u[0] != 'spread']
        tail = list(self.tail)
        P = [('front', T.front, (), self.lead['category']), ('cont', T.cont, (), self.lead['category'])]
        names = {'wonders': (T.wonders, 'Odds &amp; Ends'), 'almanac': (T.almanac, 'Almanac'), 'word': (T.word, 'Games'),
                 'sudoku': (T.sudoku, 'Games'), 'xword': (T.xword, 'Games'), 'logic': (T.logic, 'Games'),
                 'back': (T.back, 'Back Page')}
        tail_pages = [(t, names[t][0], (), names[t][1]) for t in tail]
        if self.spread:
            after = N - (N // 2 + 1)                     # pages after the spread
            overflow = max(0, len(tail_pages) - after)    # tail pages that must sit before it
            n_after_units = after - (len(tail_pages) - overflow)
            n_before_units = len(singles) - n_after_units
            before_slots = N // 2 - 1 - len(R.HEAD)
            if n_before_units < 0 or n_before_units + overflow != before_slots:
                raise ValueError(f'plan does not fit {N} pages: {len(singles)} units, {len(tail)} tail sections')
            for u in singles[:n_before_units]:
                P.append(self._unit_page(u))
            P += tail_pages[:overflow]
            st = self.spread
            P += [(st['id'], T.spread_left, (st,), 'Deep Dive'), (st['id'] + '_r', T.spread_right, (st,), 'Deep Dive')]
            for u in singles[n_before_units:]:
                P.append(self._unit_page(u))
            P += tail_pages[overflow:]
        else:
            for u in singles:
                P.append(self._unit_page(u))
            P += tail_pages
        assert len(P) == N and N % 4 == 0, 'plan does not fit the page count'
        if self.spread:
            assert P[N // 2 - 1][1] is T.spread_left, 'the spread must sit on the centre pair'
        self.pages = P
        self.page_of = {}
        for i, (pid, fn, args, _) in enumerate(P, 1):
            self.page_of.setdefault(pid, i)
            for a in args:
                self.page_of.setdefault(a['id'], i)
        self.page_of[self.lead['id']] = 1
        if self.sidebar:
            self.page_of[self.sidebar['id']] = 2
        if self.spread:
            sp = self.page_of[self.spread['id']]
            self.page_of[self.spread['id']] = f'{sp}&ndash;{sp + 1}'

    def _unit_page(self, u):
        shape, *ss = u
        if shape == 'roundup':
            r = ss[0]
            return (r['id'], T.roundup, (r,), r.get('section') or r.get('category', 'In Brief'))
        cats = list(dict.fromkeys(s['category'] for s in ss))
        sec = ' &middot; '.join(cats) if len(cats) < 3 else cats[0]
        fn = T.feature if shape == 'feature' else T.split
        return (ss[0]['id'], fn, tuple(ss), sec)

    def has(self, section):
        return section in self.page_of

    # -------------------------------------------------------------- derived content
    def index(self):
        """Front-page index: the spread, stories flagged with a teaser, and the almanac & games cell."""
        cand = [s for s in self.stories() if s.get('teaser') and s is not self.lead]
        cand += [r for r in self.roundups() if r.get('teaser')]
        sp = self.spread
        pick = ([sp] if sp in cand else []) + [s for s in cand if s is not sp][:3 - (sp in cand)]
        cells = []
        for s in pick:
            p = self.page_of[s['id']]
            lab = f'Pages {p}' if '&ndash;' in str(p) else f'Page {p}'
            cells.append((lab, s['teaser'][0], s['teaser'][1]))
        games = [k for k in ('almanac', 'word', 'sudoku', 'xword', 'logic') if self.has(k)]
        if games:
            a, b = self.page_of[games[0]], self.page_of[games[-1]]
            lab = f'Pages {a}&ndash;{b}' if a != b else f'Page {a}'
            title = 'Almanac &amp; games' if 'almanac' in games and len(games) > 1 else (
                'The almanac' if games == ['almanac'] else 'Games')
            hook = []
            if 'almanac' in games:
                hook.append('The sky this month')
            if 'sudoku' in games:
                lv = R.SUDOKU_LEVELS[PZ.level_for(self.date)]['label'].lower()
                hook.append(f'a {lv} sudoku')
            if 'xword' in games:
                hook.append('a new crossword')
            text = self.alm.get('teaser') or ('; '.join(hook) + '.' if hook else 'Puzzles and more.')
            cells.append((lab, title, text[:1].upper() + text[1:]))
        return cells[:4]

    def source_rows(self):
        rows = []
        for pid, fn, args, sec in self.pages:
            if fn is T.front:
                ss = [self.lead] + ([self.sidebar] if self.sidebar else [])
                p = '1&ndash;2'
            elif fn in (T.cont, T.spread_right):
                continue
            elif fn is T.roundup:
                ss = self.items_of(args[0])
                p = self.page_of[pid]
            elif args:
                ss = list(args)
                p = self.page_of[pid] if fn is not T.spread_left else self.page_of[args[0]['id']]
            elif fn is T.wonders:
                ss = self.printed_wonders()
                p = self.page_of['wonders']
            else:
                continue
            urls = [_src_url(s['src']) for s in ss] + [u for s in ss for u in s.get('more', [])]
            urls += [b['src'] for s in ss if isinstance(s, dict) and s.get('id')
                     for b in s.get('briefs', []) + self.fit['extra'].get(s.get('id'), []) if b.get('src')]
            doms = list(dict.fromkeys(T.dom(u) for u in urls))
            label = sec if fn is not T.wonders else 'Small Wonders'
            if fn is T.roundup:
                label = args[0].get('headline', sec)
            rows.append((f'{label} (p{"p" if "&ndash;" in str(p) else ""}. {p})', '; '.join(doms)))
        if self.alm.get('src') and self.has('almanac'):
            rows.append((f'Sky calendar (p. {self.page_of["almanac"]})', 'Computed with PyEphem; ' + T.dom(self.alm['src'][0])))
        return rows

    def _brief_srcs(self, s):
        return [b['src'] for b in s.get('briefs', []) + self.fit['extra'].get(s['id'], []) if b.get('src')]

    def urls(self):
        u = []
        for s in self.stories():
            u += [_src_url(s['src'])] + s.get('more', []) + self._brief_srcs(s)
        for r in self.roundups():
            u += [i['src'] for i in self.items_of(r)] + self._brief_srcs(r)
        u += [w['src'] for w in self.printed_wonders()] + [b['src'] for b in self.fit['extra'].get('wonders', []) if b.get('src')]
        if self.alm.get('src'):
            u.append(self.alm['src'][0])
        return list(dict.fromkeys(u))

    def printed_urls(self):
        u = [_src_url(s['src']) for s in self.stories()]
        u += [x for s in self.stories() for x in self._brief_srcs(s)]
        for r in self.roundups():
            u += [i['src'] for i in self.items_of(r)] + self._brief_srcs(r)
        if self.has('wonders'):
            u += [w['src'] for w in self.printed_wonders()] + [b['src'] for b in self.fit['extra'].get('wonders', []) if b.get('src')]
        if self.alm.get('src') and self.has('almanac'):
            u.append(self.alm['src'][0])
        return set(u)

    def titles(self):
        out = [re.sub(r'<[^>]+>|&[a-z#0-9]+;', '', s['headline']) for s in self.stories()]
        out += [re.sub(r'<[^>]+>|&[a-z#0-9]+;', '', i['head']) for r in self.roundups() for i in self.items_of(r)]
        out += [re.sub(r'<[^>]+>|&[a-z#0-9]+;', '', w['head']) for w in self.printed_wonders()]
        return out

    def prev_puzzles(self):
        root = paths.editions_dir()
        prior = sorted(d for d in os.listdir(root) if re.match(r'^\d{4}-\d{2}-\d{2}$', d) and d < self.date.isoformat()
                       and os.path.exists(os.path.join(root, d, 'puzzles.json')))
        if not prior:
            return None, ''
        d = prior[-1]
        with open(os.path.join(root, d, 'puzzles.json')) as f:
            p = json.load(f)
        num = next((e['number'] for e in ledger()['editions'] if e['date'] == d), '?')
        dd = datetime.date.fromisoformat(d)
        return p, f'No. {num} ({dd:%b}. {dd.day})'

    # -------------------------------------------------------------- puzzles
    def make_puzzles(self, seed=None):
        from .puzzles import extra as PX
        P = self.puzzles
        seed = seed if seed is not None else int(self.date.strftime('%m%d'))
        path = os.path.join(self.dir, 'puzzles.json')
        old = {}
        if os.path.exists(path):
            with open(path) as f:
                old = json.load(f)
        level = PZ.level_for(self.date)
        if old.get('sudoku_level') == level and old.get('sudoku'):
            puz, sol, st = old['sudoku'], old['sudoku_sol'], old['sudoku_stats']
        else:
            puz, sol, st = PZ.sudoku(level, seed)
        self.pz = dict(sudoku=puz, sudoku_sol=sol, sudoku_stats=st, sudoku_level=level)
        res = lambda t: self.resolve(t)
        if P.get('cryptogram'):
            C = P['cryptogram']
            enc, hint = PZ.cryptogram(C['quote'], seed)
            self.pz.update(crypt=enc, crypt_plain=C['quote'].upper(), crypt_who=C['who'].upper(), hint=hint)
        if P.get('scramble'):
            assert len(P['scramble']['words']) == R.SCRAMBLE_WORDS, f'scramble needs {R.SCRAMBLE_WORDS} words'
            self.pz.update(scramble_title=P['scramble']['title'], garage=PZ.scramble(P['scramble']['words'], seed))
        if P.get('ladder'):
            self.pz['ladder'] = PZ.check_ladder(P['ladder']['words'])
        if P.get('teasers'):
            assert len(P['teasers']) == R.TEASERS, f'{R.TEASERS} teasers needed'
            self.pz['teasers'] = [list(t) for t in P['teasers']]
        if P.get('crossword') and P['crossword'].get('grid'):
            prev, _ = self.prev_puzzles()
            grid = P['crossword']['grid']
            ac, dn = PZ.check_crossword(grid, P['crossword']['clues'], prev and prev.get('crossword', {}).get('grid'))
            self.pz['crossword'] = dict(grid=grid, across=[[n, res(P['crossword']['clues'][w])] for n, w in ac],
                                        down=[[n, res(P['crossword']['clues'][w])] for n, w in dn])
        # generated-only puzzles (logic page, sudoku-page extra); kept stable across rebuilds
        need = set(R.LOGIC_PUZZLES) if 'logic' in self.tail else set()
        if 'xword' in self.tail and 'crossword' not in self.pz:
            need |= {'kenken', 'futoshiki', 'wordsearch'}      # the crossword page becomes a puzzle page
        if R.SUDOKU_EXTRA in ('kenken', 'futoshiki') and 'sudoku' in self.tail:
            need.add(R.SUDOKU_EXTRA + '_mini')
        words = P.get('wordsearch_words') or [w for _, w in self.pz.get('garage', [])]
        for name in sorted(need):
            if old.get(name):
                self.pz[name] = old[name]
            else:
                made = PX.make(name, self.date, seed, words=words, title=P.get('wordsearch_title'))
                if made:
                    self.pz[name] = made
        return self.pz

    def save_puzzles(self):
        pz = dict(self.pz)
        if 'teasers' in pz:
            pz['teasers'] = [[a, self.resolve(b), c] for a, b, c in pz['teasers']]
        with open(os.path.join(self.dir, 'puzzles.json'), 'w') as f:
            json.dump(pz, f, indent=1)

    # -------------------------------------------------------------- render
    def resolve(self, html):
        def f(m):
            k = m.group(1)
            if k not in self.page_of:
                raise KeyError(f'unknown page reference {{p:{k}}}')
            return str(self.page_of[k])
        return re.sub(r'\{p:([a-z_0-9]+)\}', f, html)

    def blocks_of(self, st):
        return trimmed_blocks(st, self.fit['trim'].get(st['id'], 0))

    def source(self):
        """The whole edition as Typst source (preamble + one page-frame per page)."""
        import html as _html
        from . import style
        if not hasattr(self, 'pz'):
            self.make_puzzles()
        out = [style.source()]
        for i, (pid, fn, args, sec) in enumerate(self.pages, 1):
            out.append(T.page(i, fn(self, *args), sec, front=(fn is T.front)))
        body = ''.join(out).replace('{date}', _html.unescape(self.pretty).replace('"', ''))

        def f(m):
            k = m.group(1)
            if k not in self.page_of:
                raise KeyError(f'unknown page reference {{p:{k}}}')
            return _html.unescape(str(self.page_of[k]))
        return re.sub(r'\{p:([a-z_0-9]+)\}', f, body)
