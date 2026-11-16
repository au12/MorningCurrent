import datetime

import pytest

from mc import puzzles as P
from mc.puzzles import extra as X

DATE = datetime.date(2026, 11, 14)


def test_sudoku_has_one_solution():
    puz, sol, st = P.sudoku('easy', seed=3, timeout=60)
    assert P.count_solutions(puz) == 1
    assert all(p in (0, s) for p, s in zip(puz, sol))
    for i in range(9):
        assert sorted(sol[i * 9:(i + 1) * 9]) == list(range(1, 10))
        assert sorted(sol[i::9]) == list(range(1, 10))
    assert st['level'] == 'easy'


def test_cryptogram_never_maps_a_letter_to_itself():
    q = 'THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG'
    enc, hint = P.cryptogram(q, seed=1)
    assert len(enc) == len(q)
    assert all(a != b for a, b in zip(q, enc) if a.isalpha())
    assert [i for i, c in enumerate(enc) if c == ' '] == [i for i, c in enumerate(q) if c == ' ']


def test_scramble_changes_every_word():
    for s, w in P.scramble(['puzzle', 'morning', 'current'], seed=2):
        assert s != w and sorted(s) == sorted(w)


def test_word_ladder():
    path = P.find_ladder('COLD', 'WARM')
    assert path[0] == 'COLD' and path[-1] == 'WARM'
    P.check_ladder(path)


def _latin_ok(g):
    n = len(g)
    return all(sorted(r) == list(range(1, n + 1)) for r in g) and all(sorted(c) == list(range(1, n + 1)) for c in zip(*g))


@pytest.mark.parametrize('name', ['kenken', 'kenken_mini', 'futoshiki', 'futoshiki_mini', 'kakuro', 'nonogram', 'wordsearch'])
def test_logic_puzzles(name):
    p = X.make(name, DATE, seed=5)
    assert p is not None
    base = name.replace('_mini', '')
    if base == 'kenken':
        assert _latin_ok(p['solution'])
        for cg in p['cages']:
            vals = [p['solution'][r][c] for r, c in cg['cells']]
            assert X._cage_ok(cg['op'], cg['target'], vals, True, p['n'])
    elif base == 'futoshiki':
        assert _latin_ok(p['solution'])
        for key, s in p['signs'].items():
            r, c, d = key.split(',')
            r, c = int(r), int(c)
            a, b = p['solution'][r][c], (p['solution'][r][c + 1] if d == 'h' else p['solution'][r + 1][c])
            assert (a < b) if s == '<' else (a > b)
    elif base == 'wordsearch':
        for w in p['placed']:
            got = ''.join(p['grid'][w['r'] + w['dr'] * i][w['c'] + w['dc'] * i] for i in range(len(w['word'])))
            assert got == w['word']
    elif base == 'nonogram':
        sol = p['solution']
        runs = lambda line: [len(x) for x in ''.join(line).split('0') if x] or [0]
        assert [runs(r) for r in sol] == [list(x) for x in p['rows']]
        assert [runs(c) for c in zip(*sol)] == [list(x) for x in p['cols']]
    typeset(X.render(name, p, small=name.endswith('_mini')))
    typeset(f'stack({X.answer(name, p)})')


def typeset(code):
    """Compile a snippet of puzzle code on a page of the paper (raises if the Typst is invalid)."""
    import tempfile
    import typst
    from mc import config, style
    config.activate()
    with tempfile.NamedTemporaryFile('w', suffix='.typ', delete=False) as f:
        f.write(style.source() + f'#page-frame(14, {{ {code} }})\n')
    pdf = typst.compile(f.name, font_paths=[style.TTF_DIR], root='/')
    assert pdf.startswith(b'%PDF')


def test_almanac_sun_times(data):
    from mc import almanac as A
    t = A.day_table(DATE)
    h, m = (int(x) for x in t['sr'].split(':'))
    assert 5 <= h <= 8                       # default place: sunrise between 5 and 8 local time in November
    assert t['dl'].endswith('m')
    assert len(A.phases(DATE)) == 4
    assert A.sky_rows(DATE)
