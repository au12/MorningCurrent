"""Logic puzzles generated and verified in code: KenKen, futoshiki, word search, nonogram and kakuro.

Each generator is deterministic for a seed and checks that its puzzle has exactly one solution (word
search excepted: it just has to contain every word). `make(name, ...)` returns a JSON-able dict that
goes into puzzles.json; `render()` draws it for the logic page (or the bottom of the sudoku page), and
`answer()` draws the solution for the next day's back page.
"""
import random
import string

NAMES = ['kenken', 'futoshiki', 'wordsearch', 'nonogram', 'kakuro', 'kenken_mini', 'futoshiki_mini']
TITLES = {'kenken': 'KenKen', 'futoshiki': 'Futoshiki', 'wordsearch': 'Word Search', 'nonogram': 'Nonogram',
          'kakuro': 'Kakuro', 'kenken_mini': 'Mini KenKen', 'futoshiki_mini': 'Mini Futoshiki'}


# ------------------------------------------------------------------ Latin squares
def latin(n, rng):
    base = [[(r + c) % n + 1 for c in range(n)] for r in range(n)]
    rows, cols, syms = list(range(n)), list(range(n)), list(range(1, n + 1))
    rng.shuffle(rows)
    rng.shuffle(cols)
    rng.shuffle(syms)
    return [[syms[base[r][c] - 1] for c in cols] for r in rows]


def _count_latin(n, ok_cell, limit=2, givens=None):
    """Count completions of an n x n Latin square where ok_cell(grid, r, c, v) adds constraints."""
    grid = [[0] * n for _ in range(n)]
    if givens:
        for (r, c), v in givens.items():
            grid[r][c] = v
    found = [0]
    sol = [None]
    cells = [(r, c) for r in range(n) for c in range(n) if not grid[r][c]]

    def cand(r, c):
        used = set(grid[r]) | {grid[i][c] for i in range(n)}
        return [v for v in range(1, n + 1) if v not in used and ok_cell(grid, r, c, v)]

    def rec():
        if found[0] >= limit:
            return
        empty = [(r, c) for r, c in cells if not grid[r][c]]
        if not empty:
            found[0] += 1
            sol[0] = [row[:] for row in grid]
            return
        best, bc = None, None
        for r, c in empty:
            cs = cand(r, c)
            if best is None or len(cs) < len(bc):
                best, bc = (r, c), cs
                if not cs:
                    return
        r, c = best
        for v in bc:
            grid[r][c] = v
            rec()
            grid[r][c] = 0
            if found[0] >= limit:
                return
    rec()
    return found[0], sol[0]


# ------------------------------------------------------------------ KenKen
def kenken(n=5, seed=0, attempts=200):
    rng = random.Random(seed)
    for _ in range(attempts):
        sol = latin(n, rng)
        cage = [[-1] * n for _ in range(n)]
        cages = []
        cells = [(r, c) for r in range(n) for c in range(n)]
        rng.shuffle(cells)
        for r, c in cells:
            if cage[r][c] != -1:
                continue
            size = rng.choices([1, 2, 3, 4], weights=[1, 6, 5, 1])[0]
            group = [(r, c)]
            cage[r][c] = len(cages)
            while len(group) < size:
                opts = [(a + dr, b + dc) for a, b in group for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
                        if 0 <= a + dr < n and 0 <= b + dc < n and cage[a + dr][b + dc] == -1]
                if not opts:
                    break
                x = rng.choice(opts)
                cage[x[0]][x[1]] = len(cages)
                group.append(x)
            vals = [sol[a][b] for a, b in group]
            if len(group) == 1:
                op, target = '', vals[0]
            elif len(group) == 2:
                a, b = max(vals), min(vals)
                choices = ['+', '−', '×'] + (['÷'] if a % b == 0 else [])
                op = rng.choice(choices)
                target = {'+': a + b, '−': a - b, '×': a * b, '÷': a // max(b, 1)}[op]
            else:
                op = rng.choice(['+', '×'])
                target = sum(vals) if op == '+' else _prod(vals)
            cages.append(dict(cells=group, op=op, target=target))
        if sum(1 for cg in cages if len(cg['cells']) == 1) > n // 2 + 1:
            continue

        def ok(grid, r, c, v, cages=cages, cage=cage):
            cg = cages[cage[r][c]]
            vals = [grid[a][b] for a, b in cg['cells'] if (a, b) != (r, c) and grid[a][b]] + [v]
            full = len(vals) == len(cg['cells'])
            return _cage_ok(cg['op'], cg['target'], vals, full, n)
        count, _ = _count_latin(n, ok)
        if count == 1:
            return dict(n=n, cage=cage, cages=[dict(cells=[list(x) for x in cg['cells']], op=cg['op'], target=cg['target'])
                                               for cg in cages], solution=sol)
    raise RuntimeError('no unique KenKen found')


def _prod(v):
    p = 1
    for x in v:
        p *= x
    return p


def _cage_ok(op, target, vals, full, n):
    if not op:
        return vals[0] == target
    if op == '+':
        s = sum(vals)
        return s == target if full else s < target
    if op == '×':
        p = _prod(vals)
        return p == target if full else target % p == 0
    if not full:
        return True
    a, b = max(vals), min(vals)
    return (a - b == target) if op == '−' else (b and a % b == 0 and a // b == target)


# ------------------------------------------------------------------ futoshiki
def futoshiki(n=5, seed=0):
    rng = random.Random(seed)
    sol = latin(n, rng)
    signs = {}
    for r in range(n):
        for c in range(n):
            if c + 1 < n:
                signs[f'{r},{c},h'] = '<' if sol[r][c] < sol[r][c + 1] else '>'
            if r + 1 < n:
                signs[f'{r},{c},v'] = '<' if sol[r][c] < sol[r + 1][c] else '>'
    keys = list(signs)
    rng.shuffle(keys)
    shown = dict(signs)
    givens = {(r, c): sol[r][c] for r in range(n) for c in range(n)}

    def unique(shown, givens):
        def ok(grid, r, c, v):
            for (key, s) in shown.items():
                a, b, d = key.split(',')
                a, b = int(a), int(b)
                o = (a, b + 1) if d == 'h' else (a + 1, b)
                if (a, b) == (r, c) and grid[o[0]][o[1]]:
                    w = grid[o[0]][o[1]]
                    if (s == '<' and not v < w) or (s == '>' and not v > w):
                        return False
                if o == (r, c) and grid[a][b]:
                    w = grid[a][b]
                    if (s == '<' and not w < v) or (s == '>' and not w > v):
                        return False
            return True
        return _count_latin(n, ok, givens=givens)[0] == 1
    cells = list(givens)
    rng.shuffle(cells)
    for cell in cells:
        v = givens.pop(cell)
        if not unique(shown, givens):
            givens[cell] = v
    for key in keys:
        s = shown.pop(key)
        if not unique(shown, givens):
            shown[key] = s
    return dict(n=n, givens={f'{r},{c}': v for (r, c), v in givens.items()}, signs=shown, solution=sol)


# ------------------------------------------------------------------ word search
DIRS = [(0, 1), (1, 0), (1, 1), (-1, 1), (0, -1), (-1, 0), (-1, -1), (1, -1)]


def wordsearch(words, seed=0, size=12, title=None):
    rng = random.Random(seed)
    words = [w.upper() for w in dict.fromkeys(w for w in words if w and w.isalpha() and 4 <= len(w) <= size)]
    words.sort(key=len, reverse=True)
    grid = [[''] * size for _ in range(size)]
    placed = []
    for w in words:
        for _ in range(300):
            dr, dc = rng.choice(DIRS if len(placed) > 2 else DIRS[:4])
            r, c = rng.randrange(size), rng.randrange(size)
            er, ec = r + dr * (len(w) - 1), c + dc * (len(w) - 1)
            if not (0 <= er < size and 0 <= ec < size):
                continue
            if all(grid[r + dr * i][c + dc * i] in ('', w[i]) for i in range(len(w))):
                for i in range(len(w)):
                    grid[r + dr * i][c + dc * i] = w[i]
                placed.append(dict(word=w, r=r, c=c, dr=dr, dc=dc))
                break
        if len(placed) >= 12:
            break
    mask = [[bool(x) for x in row] for row in grid]
    letters = string.ascii_uppercase
    for r in range(size):
        for c in range(size):
            if not grid[r][c]:
                grid[r][c] = rng.choice(letters)
    return dict(size=size, grid=[''.join(row) for row in grid], words=sorted(p['word'] for p in placed), placed=placed,
                mask=[''.join('1' if x else '0' for x in row) for row in mask], title=title or 'Word Search')


# ------------------------------------------------------------------ nonogram
def _runs(line):
    out, k = [], 0
    for x in line:
        if x:
            k += 1
        elif k:
            out.append(k)
            k = 0
    if k:
        out.append(k)
    return out or [0]


def _line_solve(clue, cur):
    """Intersect every arrangement of `clue` consistent with cur (None = unknown). Returns new line or None."""
    n = len(cur)
    if clue == [0]:
        return [0] * n if all(x in (None, 0) for x in cur) else None
    sols = []

    def place(i, pos, acc):
        if len(sols) > 4000:
            return
        if i == len(clue):
            line = acc + [0] * (n - len(acc))
            if all(c is None or c == v for c, v in zip(cur, line)):
                sols.append(line)
            return
        rest = sum(clue[i + 1:]) + len(clue) - i - 1
        for start in range(pos, n - rest - clue[i] + 1):
            line = acc + [0] * (start - len(acc)) + [1] * clue[i]
            if i + 1 < len(clue):
                line += [0]
            if all(c is None or c == v for c, v in zip(cur, line)):
                place(i + 1, len(line), line)
    place(0, 0, [])
    if not sols:
        return None
    return [sols[0][k] if all(s[k] == sols[0][k] for s in sols) else None for k in range(n)]


def nonogram(size=10, seed=0, attempts=200):
    rng = random.Random(seed)
    for _ in range(attempts):
        g = [[1 if rng.random() < 0.55 else 0 for _ in range(size)] for _ in range(size)]
        for _ in range(2):        # smooth into blobs
            g = [[1 if sum(g[rr][cc] for rr in range(max(0, r - 1), min(size, r + 2)) for cc in range(max(0, c - 1), min(size, c + 2)))
                  >= 5 else 0 for c in range(size)] for r in range(size)]
        if any(sum(row) == 0 for row in g):
            continue
        rows = [_runs(row) for row in g]
        cols = [_runs([g[r][c] for r in range(size)]) for c in range(size)]
        cur = [[None] * size for _ in range(size)]
        changed = True
        while changed:
            changed = False
            for r in range(size):
                new = _line_solve(rows[r], cur[r])
                if new is None:
                    break
                if new != cur[r]:
                    cur[r] = new
                    changed = True
            for c in range(size):
                col = [cur[r][c] for r in range(size)]
                new = _line_solve(cols[c], col)
                if new is None:
                    break
                if new != col:
                    for r in range(size):
                        cur[r][c] = new[r]
                    changed = True
        if all(x is not None for row in cur for x in row) and cur == g:
            return dict(size=size, rows=rows, cols=cols, solution=[''.join(map(str, row)) for row in g])
    raise RuntimeError('no line-solvable nonogram found')


# ------------------------------------------------------------------ kakuro
def kakuro(size=7, seed=0, attempts=400):
    rng = random.Random(seed)
    for _ in range(attempts):
        black = [[r == 0 or c == 0 for c in range(size)] for r in range(size)]
        for _ in range(size):
            r, c = rng.randrange(1, size), rng.randrange(1, size)
            black[r][c] = True
            black[size - r][size - c] = True if 0 < size - r < size and 0 < size - c < size else black[size - r][size - c]
        runs = _kakuro_runs(black, size)
        if not runs or any(len(cells) < 2 or len(cells) > 6 for _, cells in runs):
            continue
        white = [(r, c) for r in range(size) for c in range(size) if not black[r][c]]
        if len(white) < size * size * 0.4:
            continue
        sol = {}
        cell_runs = {}
        for i, (_, cells) in enumerate(runs):
            for x in cells:
                cell_runs.setdefault(x, []).append(i)

        def fill(k=0):
            if k == len(white):
                return True
            x = white[k]
            used = {sol[y] for i in cell_runs[x] for y in runs[i][1] if y in sol}
            vals = [v for v in range(1, 10) if v not in used]
            rng.shuffle(vals)
            for v in vals:
                sol[x] = v
                if fill(k + 1):
                    return True
                del sol[x]
            return False
        if not fill():
            continue
        sums = [sum(sol[x] for x in cells) for _, cells in runs]
        givens = {}
        for _ in range(5):
            sols = _kakuro_solutions(white, runs, sums, cell_runs, givens)
            if len(sols) <= 1:
                break
            diff = [x for x in white if sols[0][x] != sols[1][x] and x not in givens]
            x = rng.choice(diff)
            givens[x] = sol[x]
        if len(_kakuro_solutions(white, runs, sums, cell_runs, givens)) == 1:
            clues = {}
            for (head, cells), s in zip(runs, sums):
                d = 'ac' if cells[0][0] == head[0] else 'dn'
                clues.setdefault(f'{head[0]},{head[1]}', {})[d] = s
            return dict(size=size, black=[''.join('1' if b else '0' for b in row) for row in black], clues=clues,
                        givens={f'{r},{c}': v for (r, c), v in givens.items()},
                        solution={f'{r},{c}': v for (r, c), v in sol.items()})
    raise RuntimeError('no unique kakuro found')


def _kakuro_runs(black, size):
    runs = []
    for r in range(size):
        c = 0
        while c < size:
            if black[r][c]:
                j = c + 1
                cells = []
                while j < size and not black[r][j]:
                    cells.append((r, j))
                    j += 1
                if cells:
                    runs.append(((r, c), cells))
                c = j if cells else c + 1
            else:
                c += 1
    for c in range(size):
        r = 0
        while r < size:
            if black[r][c]:
                j = r + 1
                cells = []
                while j < size and not black[j][c]:
                    cells.append((j, c))
                    j += 1
                if cells:
                    runs.append(((r, c), cells))
                r = j if cells else r + 1
            else:
                r += 1
    covered = {}
    for _, cells in runs:
        for x in cells:
            covered[x] = covered.get(x, 0) + 1
    whites = [(r, c) for r in range(size) for c in range(size) if not black[r][c]]
    if any(covered.get(x, 0) != 2 for x in whites):
        return None
    return runs


def _kakuro_solutions(white, runs, sums, cell_runs, givens=None, limit=2):
    val = dict(givens or {})
    found = []

    def ok(x, v):
        for i in cell_runs[x]:
            cells = runs[i][1]
            vs = [val[y] for y in cells if y in val] + [v]
            if len(set(vs)) != len(vs):
                return False
            s = sum(vs)
            left = len(cells) - len(vs)
            if left == 0 and s != sums[i]:
                return False
            if left and (s + sum(range(1, left + 1)) > sums[i] or s + sum(range(10 - left, 10)) < sums[i]):
                return False
        return True

    order = [x for x in white if x not in val]

    def rec(k=0):
        if len(found) >= limit:
            return
        if k == len(order):
            found.append(dict(val))
            return
        x = order[k]
        for v in range(1, 10):
            if ok(x, v):
                val[x] = v
                rec(k + 1)
                del val[x]
    for x in list(val):        # givens must themselves be consistent
        v = val.pop(x)
        if not ok(x, v):
            return []
        val[x] = v
    rec()
    return found


# ------------------------------------------------------------------ dispatch
def make(name, date, seed, words=(), title=None, tries=6):
    """Generate puzzle `name`; tries a few seeds before giving up (returns None if all fail)."""
    for k in range(tries):
        try:
            return _make(name, seed + 7919 * k, words, title)
        except RuntimeError:
            continue
    return None


def _make(name, seed, words=(), title=None):
    s = seed * 31 + sum(map(ord, name))
    if name == 'kenken':
        return kenken(5, s)
    if name == 'kenken_mini':
        return kenken(4, s)
    if name == 'futoshiki':
        return futoshiki(5, s)
    if name == 'futoshiki_mini':
        return futoshiki(4, s)
    if name == 'wordsearch':
        return wordsearch(list(words) or ['MORNING', 'CURRENT', 'PUZZLE', 'ALMANAC', 'SUDOKU', 'PAPER', 'COFFEE', 'NEWS'], s,
                          title=title)
    if name == 'nonogram':
        return nonogram(10, s)
    if name == 'kakuro':
        return kakuro(7, s)
    raise KeyError(name)


INSTR = {
    'kenken': 'Fill the grid with 1&ndash;{n} so no digit repeats in a row or column. The numbers in each outlined cage combine '
              'to the target with the operation shown.',
    'futoshiki': 'Fill the grid with 1&ndash;{n}, no repeats in a row or column. Each sign points to the smaller neighbor.',
    'wordsearch': 'Find these words from today&rsquo;s paper, across, down or diagonally, forwards or backwards.',
    'nonogram': 'Shade cells so each row and column holds runs of the lengths given, in order, with at least one gap between runs. '
                'A picture appears.',
    'kakuro': 'Fill each white cell with 1&ndash;9 so every run adds up to its clue (down clues bottom left, across clues top right), '
              'with no digit repeated within a run.',
}


# ------------------------------------------------------------------ rendering (Typst code; see mc/paper.typ)
def _len(x):
    return f'{x:.3f}in'


def _cell(content='[]', stroke=None, fill=None):
    args = []
    if stroke:
        args.append(f'stroke: {stroke}')
    if fill:
        args.append(f'fill: {fill}')
    return f'table.cell({", ".join(args)}, {content})' if args else content


def _grid(n_cols, n_rows, size, cells, stroke='0.6pt + rgb("#888")', size_rows=None):
    rows = size_rows or size
    return (f'table(columns: ({_len(size)},) * {n_cols}, rows: ({_len(rows)},) * {n_rows}, align: center + horizon, '
            f'stroke: {stroke}, {", ".join(cells)})')


def _num(v, size):
    return f'sans({size * 26 * 0.95:.1f}pt, weight: 600, [{v}])' if v != '' else '[]'


def _cage_table(p, small=False, solution=False, size=None):
    from .. import rules as R
    n, cage = p['n'], p['cage']
    size = size or R.SIZES['logic_cell'] * (0.8 if small else 1)
    label = {}
    for cg in p['cages']:
        r, c = min(tuple(x) for x in cg['cells'])
        op = {'x': '×', '*': '×', '/': '÷', '-': '−'}.get(cg['op'], cg['op'])
        label[(r, c)] = f'{cg["target"]}{op}'
    thick = '1.2pt' if small else '1.8pt'
    cells = []
    for r in range(n):
        for c in range(n):
            sides = []
            for side, (dr, dc) in (('top', (-1, 0)), ('bottom', (1, 0)), ('left', (0, -1)), ('right', (0, 1))):
                rr, cc = r + dr, c + dc
                edge = not (0 <= rr < n and 0 <= cc < n) or cage[rr][cc] != cage[r][c]
                sides.append(f'{side}: {thick} + ink' if edge else f'{side}: (paint: rgb("#999"), thickness: 0.4pt, dash: "dotted")')
            lab = ''
            if (r, c) in label and not solution:
                lab = f'place(top + left, dx: 1.5pt, dy: 1pt, sans({max(5.5, size * 14):.1f}pt, weight: 700, [{label[(r, c)]}]))'
            val = _num(p['solution'][r][c], size) if solution else '[]'
            content = f'[#{lab}#{val}]' if lab else val
            cells.append(_cell(content, '(' + ', '.join(sides) + ')'))
    return _grid(n, n, size, cells, stroke='none')


def _fut_table(p, solution=False, size=None):
    from .. import rules as R
    n = p['n']
    size = size or R.SIZES['logic_cell']
    gap = size * 0.42
    sym = {'<': '<', '>': '>'}
    vsym = {'<': '∧', '>': '∨'}
    cols = ', '.join([_len(size) if k % 2 == 0 else _len(gap) for k in range(2 * n - 1)])
    rows = cols
    cells = []
    for r in range(2 * n - 1):
        for c in range(2 * n - 1):
            if r % 2 == 0 and c % 2 == 0:
                rr, cc = r // 2, c // 2
                v = p['solution'][rr][cc] if solution else p['givens'].get(f'{rr},{cc}', '')
                cells.append(_cell(_num(v, size), '0.8pt + ink'))
            elif r % 2 == 0:
                sgn = sym.get(p['signs'].get(f'{r // 2},{c // 2},h'), '')
                cells.append(f'sans(9pt, weight: 700, [{sgn}])' if sgn else '[]')
            elif c % 2 == 0:
                sgn = vsym.get(p['signs'].get(f'{r // 2},{c // 2},v'), '')
                cells.append(f'sans(9pt, weight: 700, [{sgn}])' if sgn else '[]')
            else:
                cells.append('[]')
    return f'table(columns: ({cols}), rows: ({rows}), align: center + horizon, stroke: none, {", ".join(cells)})'


def _ws_table(p, mask=False, size=None):
    from .. import rules as R
    size = size or R.SIZES['logic_cell'] * 0.62
    cells = []
    for row, mrow in zip(p['grid'], p['mask']):
        for ch, m in zip(row, mrow):
            cells.append(f'sans({size * 32:.1f}pt, weight: 600, [{ch if (m == "1" or not mask) else ""}])')
    return _grid(p['size'], p['size'], size, cells, stroke='none')


def _non_table(p, size=None):
    from .. import rules as R
    size = size or R.SIZES['logic_cell'] * 0.55
    mx = max(len(cl) for cl in p['cols'])
    n = p['size']
    cells = []
    for k in range(mx):
        cells.append('[]')
        for cl in p['cols']:
            v = cl[k - (mx - len(cl))] if k >= mx - len(cl) else ''
            cells.append(f'align(center + bottom, sans(6.4pt, weight: 600, [{v}]))')
    for r, cl in enumerate(p['rows']):
        cells.append(f'align(right + horizon, pad(right: 2pt, sans(6.4pt, weight: 600, [{" ".join(map(str, cl))}])))')
        for c in range(n):
            st = ['0.4pt + rgb("#999")']
            sides = []
            if c % 5 == 0:
                sides.append('left: 1pt + ink')
            if r % 5 == 0:
                sides.append('top: 1pt + ink')
            if c == n - 1:
                sides.append('right: 1pt + ink')
            if r == n - 1:
                sides.append('bottom: 1pt + ink')
            stroke = '(rest: 0.4pt + rgb("#999")' + (', ' + ', '.join(sides) if sides else '') + ')'
            cells.append(_cell('[]', stroke))
    return (f'table(columns: (auto,) + ({_len(size)},) * {n}, rows: (auto,) * {mx} + ({_len(size)},) * {n}, '
            f'align: center + horizon, stroke: none, inset: 0pt, {", ".join(cells)})')


def _non_solution(p, size=0.16):
    cells = [_cell('[]', None, 'ink' if x == '1' else 'white') for row in p['solution'] for x in row]
    return _grid(p['size'], p['size'], size, cells, stroke='0.3pt + rgb("#999")')


def _kakuro_table(p, solution=False, size=None):
    from .. import rules as R
    size = size or R.SIZES['logic_cell']
    n = p['size']
    cells = []
    for r in range(n):
        for c in range(n):
            if p['black'][r][c] == '1':
                cl = p['clues'].get(f'{r},{c}', {})
                inner = []
                if cl:
                    inner.append('place(top + left, line(start: (0%, 0%), end: (100%, 100%), stroke: 0.5pt + rgb("#777")))')
                fs = max(5.5, size * 13)
                if 'dn' in cl:
                    inner.append(f'place(bottom + left, dx: 2pt, dy: -1pt, sans({fs:.1f}pt, weight: 700, text(fill: white, [{cl["dn"]}])))')
                if 'ac' in cl:
                    inner.append(f'place(top + right, dx: -2pt, dy: 1pt, sans({fs:.1f}pt, weight: 700, text(fill: white, [{cl["ac"]}])))')
                content = '[' + ''.join('#' + x for x in inner) + ']'
                cells.append(_cell(content, '0.6pt + rgb("#888")', 'ink'))
            else:
                v = p['solution'][f'{r},{c}'] if solution else p.get('givens', {}).get(f'{r},{c}', '')
                cells.append(_cell(_num(v, size), '0.6pt + rgb("#888")'))
    return _grid(n, n, size, cells, stroke='none')


def render(name, p, small=False):
    """A logic puzzle with its title and instructions, as Typst code."""
    base = name.replace('_mini', '')
    title = TITLES.get(name, name)
    instr = INSTR[base].format(n=p.get('n', 5))
    from ..ty import rich
    head = f'ptitle({rich(p.get("title") or title)}, size: T.ptitle * 0.82pt), pinstr({rich(instr)})'
    if base == 'kenken':
        body = _cage_table(p, small)
    elif base == 'futoshiki':
        body = _fut_table(p)
    elif base == 'wordsearch':
        words = ', '.join(f'[{w}]' for w in p['words'])
        body = (f'stack(spacing: 4pt, {_ws_table(p)}, columns(4, gutter: 6pt, sans(7.6pt, weight: 600, track: 0.06em, '
                f'par(leading: lh(1.5), justify: false, first-line-indent: 0pt, ({words},).join(linebreak())))))')
    elif base == 'nonogram':
        body = _non_table(p)
    elif base == 'kakuro':
        body = _kakuro_table(p)
    else:
        body = '[]'
    if small:
        return f'grid(columns: (auto, 1fr), column-gutter: 12pt, {body}, stack({head}))'
    return f'stack({head}, {body})'


def answer(name, p):
    """A logic puzzle's solution for the back page, as Typst code (or '' for unknown names)."""
    base = name.replace('_mini', '')
    t = TITLES.get(name, name)
    s = 0.16
    if base == 'kenken':
        body = _cage_table(p, solution=True, size=s)
    elif base == 'futoshiki':
        cells = [f'sans(6.4pt, [{p["solution"][r][c]}])' for r in range(p['n']) for c in range(p['n'])]
        body = _grid(p['n'], p['n'], s, cells)
    elif base == 'wordsearch':
        body = _ws_table(p, mask=True, size=0.13)
    elif base == 'nonogram':
        body = _non_solution(p)
    elif base == 'kakuro':
        body = _kakuro_table(p, solution=True, size=s)
    else:
        return ''
    return f'block(above: 5pt, ans-head([{t}])), {body}'
