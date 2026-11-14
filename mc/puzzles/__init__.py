"""Puzzle generation and verification. Everything printed on the games pages is produced or checked here.

- sudoku(level): unique solution, 180-degree symmetric givens, graded by a logical solver against
  rules.SUDOKU_LEVELS (difficulty follows the weekday, rules.SUDOKU_BY_WEEKDAY).
- cryptogram(quote): derangement cipher of letters only, hint = 4th most frequent plaintext letter.
- scramble(words), check_ladder(words), find_ladder(a, b), crossword fill (pattern library + solver).
"""
import random, string, json, os, time, multiprocessing as mp
from .. import rules as R, paths

DATA = paths.BUNDLED

# ================================================================== sudoku
UNITS = ([[r * 9 + c for c in range(9)] for r in range(9)] + [[r * 9 + c for r in range(9)] for c in range(9)] +
         [[(br + r) * 9 + bc + c for r in range(3) for c in range(3)] for br in (0, 3, 6) for bc in (0, 3, 6)])
PEERS = [set(j for u in UNITS if i in u for j in u) - {i} for i in range(81)]
BOXES, LINES = UNITS[18:], UNITS[:18]

def count_solutions(g, limit=2):
    g = g[:]; n = [0]
    def cand(i): return set(range(1, 10)) - {g[j] for j in PEERS[i]}
    def rec():
        if n[0] >= limit: return
        empty = [i for i in range(81) if not g[i]]
        if not empty: n[0] += 1; return
        i = min(empty, key=lambda i: len(cand(i)))
        for v in cand(i):
            g[i] = v; rec(); g[i] = 0
            if n[0] >= limit: return
    rec(); return n[0]

def _full(rng):
    g = [0] * 81
    def rec(k=0):
        if k == 81: return True
        vs = list(set(range(1, 10)) - {g[j] for j in PEERS[k]}); rng.shuffle(vs)
        for v in vs:
            g[k] = v
            if rec(k + 1): return True
        g[k] = 0; return False
    rec(); return g

def grade(puz):
    """Solve with human techniques in order of difficulty. Returns (solved, stats) where stats counts
    naked singles, hidden singles and locked-candidate eliminations, and 'hardest' names the top technique used."""
    g = puz[:]; st = dict(naked=0, hidden=0, locked=0, hardest='singles')
    C = [set() if g[i] else set(range(1, 10)) - {g[j] for j in PEERS[i]} for i in range(81)]
    def place(i, v):
        g[i] = v; C[i] = set()
        for j in PEERS[i]: C[j].discard(v)
    while True:
        moved = False
        for i in range(81):
            if not g[i] and len(C[i]) == 1: place(i, next(iter(C[i]))); st['naked'] += 1; moved = True; break
        if moved: continue
        for u in UNITS:
            for v in range(1, 10):
                sp = [i for i in u if v in C[i]]
                if len(sp) == 1 and v not in [g[i] for i in u]: place(sp[0], v); st['hidden'] += 1; moved = True; break
            if moved: break
        if moved: continue
        # locked candidates: pointing (box -> line) and claiming (line -> box)
        for a_set, b_set in ((BOXES, LINES), (LINES, BOXES)):
            for a in a_set:
                for v in range(1, 10):
                    sp = [i for i in a if v in C[i]]
                    if len(sp) < 2: continue
                    for b in b_set:
                        if all(i in b for i in sp):
                            hit = [j for j in b if j not in a and v in C[j]]
                            if hit:
                                for j in hit: C[j].discard(v)
                                st['locked'] += 1; st['hardest'] = 'locked'; moved = True
                    if moved: break
                if moved: break
            if moved: break
        if not moved: break
    return all(g), st

def _fits(level, n, ok, st):
    L = R.SUDOKU_LEVELS[level]
    if not ok or not (L['givens'][0] <= n <= L['givens'][1]): return False
    if not (L['hidden'][0] <= st['hidden'] <= L['hidden'][1]): return False
    return st['hardest'] == L['technique']

def sudoku(level, seed=0, timeout=120):
    """Generate a puzzle graded exactly to `level`. Returns (puzzle, solution, stats)."""
    rng = random.Random(seed); t0 = time.time(); L = R.SUDOKU_LEVELS[level]
    while time.time() - t0 < timeout:
        sol = _full(rng); puz = sol[:]; target = rng.randint(*L['givens'])
        cells = list(range(41)); rng.shuffle(cells)
        for i in cells:
            j = 80 - i; keep = (puz[i], puz[j]); puz[i] = puz[j] = 0
            if count_solutions(puz) != 1: puz[i], puz[j] = keep
            n = sum(1 for x in puz if x)
            if n <= target: break
            if L['technique'] == 'singles' and not grade(puz)[0]: puz[i], puz[j] = keep
        n = sum(1 for x in puz if x); ok, st = grade(puz)
        if _fits(level, n, ok, st):
            assert count_solutions(puz) == 1
            st['givens'] = n; st['level'] = level
            return puz, sol, st
    raise RuntimeError(f'no {level} sudoku within {timeout}s')

def level_for(date):
    return R.SUDOKU_BY_WEEKDAY[date.weekday()]

# ================================================================== word puzzles
def cryptogram(quote, seed=0):
    rng = random.Random(seed); L = list(string.ascii_uppercase)
    while True:
        p = L[:]; rng.shuffle(p)
        if all(a != b for a, b in zip(L, p)): break
    key = dict(zip(L, p)); q = quote.upper()
    enc = ''.join(key.get(c, c) for c in q)
    letters = sorted(set(c for c in q if c.isalpha()), key=lambda c: (-q.count(c), c))
    hint = letters[3]
    return enc, [key[hint], hint]

def scramble(words, seed=0):
    rng = random.Random(seed); out = []
    for w in words:
        w = w.upper()
        while True:
            l = list(w); rng.shuffle(l); s = ''.join(l)
            if s != w: break
        out.append([s, w])
    return out

_DICT = None
def dictionary():
    global _DICT
    if _DICT is None:
        from english_words import get_english_words_set
        _DICT = get_english_words_set(['gcide'], lower=True, alpha=True) & get_english_words_set(['web2'], lower=True, alpha=True)
    return _DICT

def common(w):
    from wordfreq import zipf_frequency
    z = R.WORD_ZIPF.get(len(w), R.WORD_ZIPF['long'])
    return w.lower() in dictionary() and zipf_frequency(w.lower(), 'en') >= z

def check_ladder(words):
    ws = [w.upper() for w in words]
    assert all(w.lower() in dictionary() for w in ws), [w for w in ws if w.lower() not in dictionary()]
    assert all(len(w) == len(ws[0]) for w in ws)
    assert all(sum(a != b for a, b in zip(x, y)) == 1 for x, y in zip(ws, ws[1:])), 'each rung must change one letter'
    return ws

def find_ladder(a, b):
    """Shortest ladder between two words using common dictionary words (for writers choosing a pair)."""
    from collections import deque
    a, b = a.upper(), b.upper(); n = len(a)
    W = {w.upper() for w in dictionary() if len(w) == n and common(w)} | {a, b}
    prev = {a: None}; q = deque([a])
    while q:
        x = q.popleft()
        if x == b: break
        for i in range(n):
            for c in string.ascii_uppercase:
                y = x[:i] + c + x[i + 1:]
                if y in W and y not in prev: prev[y] = x; q.append(y)
    if b not in prev: return None
    path = [b]
    while prev[path[-1]]: path.append(prev[path[-1]])
    return path[::-1]

# ================================================================== crossword
def slots(pattern):
    H, W = len(pattern), len(pattern[0]); out = []
    for r in range(H):
        c = 0
        while c < W:
            if pattern[r][c] != '#':
                s = c
                while c < W and pattern[r][c] != '#': c += 1
                out.append([(r, x) for x in range(s, c)])
            else: c += 1
    for c in range(W):
        r = 0
        while r < H:
            if pattern[r][c] != '#':
                s = r
                while r < H and pattern[r][c] != '#': r += 1
                out.append([(x, c) for x in range(s, r)])
            else: r += 1
    return out

def valid_pattern(p):
    H, W = len(p), len(p[0])
    if any(len(r) != W for r in p): return False
    if R.CROSSWORD['symmetric'] and any(p[r][c] != p[H - 1 - r][W - 1 - c] for r in range(H) for c in range(W)): return False
    sl = slots(p)
    if any(len(s) < R.CROSSWORD['min_word'] for s in sl): return False
    cover = {}
    for s in sl:
        for x in s: cover[x] = cover.get(x, 0) + 1
    return all(cover.get((r, c)) == 2 for r in range(H) for c in range(W) if p[r][c] != '#')

def pattern_library():
    """Known-fillable patterns plus their mirror/transpose variants (all distinct, all valid)."""
    base = json.load(open(os.path.join(DATA, 'patterns.json')))
    out = []
    for p in base:
        for v in (p, [r[::-1] for r in p], [''.join(p[r][c] for r in range(len(p))) for c in range(len(p[0]))]):
            if valid_pattern(v) and v not in out and R.CROSSWORD['min_size'] <= max(len(v), len(v[0])) <= R.CROSSWORD['max_size']:
                out.append(v)
    return out

def mask(grid):
    return ['' .join('#' if ch == '#' else '.' for ch in r) for r in grid]

_WORDS_CACHE = {}


def _fill_words(ban, need_clue):
    key = (frozenset(ban), need_clue)
    if key not in _WORDS_CACHE:
        from wordfreq import top_n_list
        out = []
        for w in top_n_list('en', 50000):
            if not (w.isalpha() and w.isascii() and len(w) >= 3 and w not in ban and common(w)):
                continue
            if need_clue:
                from .. import words as W
                try:
                    if W.is_proper_only(w) or not W.clue(w):
                        continue
                except Exception:  # noqa: BLE001 - a dictionary hiccup just skips the word
                    continue
            out.append(w.upper())
        _WORDS_CACHE[key] = out
    return _WORDS_CACHE[key]


def _fill_worker(args):
    pattern, seed, seconds, ban = args[:4]
    prefer = set(args[4]) if len(args) > 4 and args[4] else set()
    need_clue = bool(args[5]) if len(args) > 5 else False
    rng = random.Random(seed)
    words = list(_fill_words(ban, need_clue))
    if prefer:   # today's words are tried first, so the grid echoes the paper
        words = [w for w in words if w in prefer] + [w for w in words if w not in prefer]
    bylen = {}
    for w in words: bylen.setdefault(len(w), []).append(w)
    idx = {}
    for L, ws in bylen.items():
        for i, w in enumerate(ws):
            for p, ch in enumerate(w): idx.setdefault((L, p, ch), set()).add(i)
    sl = slots(pattern); grid = {}; used = set(); t0 = time.time()
    n_pref = {L: sum(1 for w in ws if w in prefer) for L, ws in bylen.items()}
    def cands(s):
        L = len(s); S = None
        for p, x in enumerate(s):
            if x in grid:
                st = idx.get((L, p, grid[x]), set()); S = st if S is None else S & st
                if not S: return []
        return list(range(len(bylen.get(L, [])))) if S is None else sorted(S)
    def solve():
        if time.time() - t0 > seconds: return False
        best = None
        for s in sl:
            if all(x in grid for x in s): continue
            cs = [i for i in cands(s) if bylen[len(s)][i] not in used]
            if best is None or len(cs) < len(best[1]):
                best = (s, cs)
                if not cs: return False
        if best is None: return True
        s, cs = best
        pref = [i for i in cs if i < n_pref.get(len(s), 0)][:12]
        rest = [i for i in cs if i >= n_pref.get(len(s), 0)][:40]
        rng.shuffle(pref); rng.shuffle(rest)
        for i in pref + rest:
            w = bylen[len(s)][i]; new = [x for x in s if x not in grid]
            for x, ch in zip(s, w): grid[x] = ch
            used.add(w)
            if all(cands(t) for t in sl) and solve(): return True
            used.discard(w)
            for x in new: del grid[x]
        return False
    if not solve(): return None
    out = [''.join(grid.get((r, c), '#') if pattern[r][c] != '#' else '#' for c in range(len(pattern[0]))) for r in range(len(pattern))]
    _, ac, dn = entries(out)
    ws = [w for _, w in ac + dn]
    if len(set(ws)) != len(ws) or any(w not in set(words) for w in ws):
        return None            # a crossing completed a repeated or unlisted word
    return out


def fill_crossword(avoid=(), seeds=8, seconds=100, procs=2, extra_ban=(), prefer=(), need_clue=False, first=False):
    """Pick a library pattern not in `avoid` (recent masks) and fill it; returns a list of candidate grids
    for human review (reject names, abbreviations and dull words; add them to data/ban.txt and rerun).
    With first=True it stops at the first fill (for unattended builds)."""
    ban = set(open(os.path.join(DATA, 'ban.txt')).read().split()) | {w.lower() for w in extra_ban}
    if need_clue:          # load WordNet once here so worker processes inherit it instead of racing to load it
        from .. import words as W
        W.wordnet(); W.is_proper_only('test'); W.clue('test')
        _fill_words(ban, need_clue)
    lib = [p for p in pattern_library() if p not in [list(a) for a in avoid]]
    rng = random.Random(time.time() if not first else len(avoid) * 7 + len(prefer)); rng.shuffle(lib)
    for pattern in lib[:4]:
        jobs = [(pattern, s, seconds, ban, list(prefer), need_clue) for s in range(seeds)]
        if procs <= 1:
            res = []
            for j in jobs:
                g = _fill_worker(j)
                if g:
                    res.append(g)
                    if first: break
        else:
            with mp.Pool(procs) as pool:
                res = []
                for g in pool.imap_unordered(_fill_worker, jobs):
                    if g:
                        res.append(g)
                        if first:
                            pool.terminate(); break
        if res: return pattern, res
    return None, []


def entries(grid):
    """Standard numbering. Returns (numbers {(r,c): n}, across [(n, word)], down [(n, word)])."""
    H, W = len(grid), len(grid[0]); nums = {}; ac = []; dn = []; k = 1
    for r in range(H):
        for c in range(W):
            if grid[r][c] == '#': continue
            a = (c == 0 or grid[r][c - 1] == '#') and c + 1 < W and grid[r][c + 1] != '#'
            d = (r == 0 or grid[r - 1][c] == '#') and r + 1 < H and grid[r + 1][c] != '#'
            if a or d:
                nums[(r, c)] = k
                if a:
                    w = ''; cc = c
                    while cc < W and grid[r][cc] != '#': w += grid[r][cc]; cc += 1
                    ac.append((k, w))
                if d:
                    w = ''; rr = r
                    while rr < H and grid[rr][c] != '#': w += grid[rr][c]; rr += 1
                    dn.append((k, w))
                k += 1
    return nums, ac, dn

def check_crossword(grid, clues, prev_grid=None):
    assert valid_pattern(mask(grid)), 'crossword pattern breaks the rules (symmetry, 3+ letters, every cell checked)'
    if prev_grid: assert mask(grid) != mask(prev_grid), 'crossword pattern must differ from the previous edition'
    _, ac, dn = entries(grid)
    words = [w for _, w in ac + dn]
    assert len(set(words)) == len(words), 'duplicate answers'
    missing = [w for w in words if w not in clues]
    assert not missing, f'unclued answers: {missing}'
    return ac, dn
