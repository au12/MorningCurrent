"""Puzzle inputs and the Word of the Day, made from today's content without hand-writing.

- cryptogram: a verified quote from one of today's stories (pull quotes are copied verbatim from the
  source, with the speaker it names), else a well-attributed line from the bundled public-domain corpus
- scramble: seven everyday words from today's headlines, with their pages
- word ladder: a themed pair (warm/cool, head/tail...) joined by common words
- teasers: three computed puzzles (a number sequence, make-the-target, a calendar question)
- crossword: a library pattern filled with clueable words, today's words tried first; clues are
  fill-in-the-blank lines from today's stories (with page references) or dictionary definitions
- word ladder, word search words and the almanac's Word of the Day (an uncommon word from a story,
  with a WordNet definition and a respelling)
"""
import datetime
import itertools
import json
import os
import random
import re

from .. import paths, rules as R, words as W
from ..ingest.text import esc, plain, sentences
from . import common, dictionary, entries, find_ladder, mask

CAT_TAGS = {
    'Space': ['space'], 'Earth & Climate': ['earth', 'weather'], 'Nature & Wildlife': ['nature'], 'Oceans & Weather': ['oceans', 'weather'],
    'Physics & Chemistry': ['physics', 'science'], 'Materials': ['materials'], 'Biology & the Brain': ['biology', 'brain'],
    'Health & Medicine': ['people'], 'Human Origins & Archaeology': ['history'], 'History & Everyday Things': ['history', 'everyday'],
    'Engineering & Energy': ['engineering'], 'Cars & Motorsport': ['cars'], 'Transport & Aviation': ['transport'],
    'Robotics': ['engineering', 'makers'], 'Computing & Codes': ['computing'], 'Home Tech & Self-Hosting': ['home'],
    'Makers & DIY': ['makers'], 'Photography & Imaging': ['photography'], 'Art & Design': ['art', 'design'],
    'Architecture': ['architecture'], 'Food & Farming': ['food', 'farming'], 'Language & Words': ['words', 'books'],
    'Music & Sound': ['art'], 'Sport & Games': ['sport'], 'Math & Puzzles': ['math'], 'Places & Maps': ['places'],
    'People & Odd Jobs': ['people'], 'Clever Businesses & Inventions': ['inventions', 'business'],
}
LADDER_PAIRS = [('warm', 'cool'), ('cold', 'warm'), ('head', 'tail'), ('fast', 'slow'), ('dusk', 'dawn'), ('hard', 'soft'),
                ('east', 'west'), ('give', 'take'), ('lose', 'find'), ('rise', 'fall'), ('work', 'play'), ('snow', 'rain'),
                ('star', 'moon'), ('lake', 'pond'), ('wind', 'rain'), ('fish', 'bird'), ('seed', 'tree'), ('sail', 'boat'),
                ('cat', 'dog'), ('hot', 'ice'), ('coal', 'fire'), ('wild', 'tame'), ('dark', 'lite'), ('love', 'hate'),
                ('mild', 'wild'), ('bake', 'cake'), ('farm', 'barn'), ('wolf', 'deer'), ('ship', 'port'), ('slow', 'zoom'),
                ('page', 'book'), ('mind', 'body'), ('lead', 'gold'), ('song', 'bird'), ('ape', 'man'), ('rock', 'sand'),
                ('nose', 'chin'), ('foot', 'shoe'), ('heat', 'cold'), ('wet', 'dry'), ('dry', 'wet'), ('ink', 'pen')]
GRIM = re.compile(r'(?i)(kill|murder|death|dead|die|disease|injur|wound|violen|weapon|war\b|crime|criminal|poison|torture|'
                  r'abuse|suicid|corpse|decay|infect|tumor|cancer|blood|pain|fear|hate|insult|offensive|obscene|vulgar)')
STOP = set('about after again against already also always among another around because before being below between both '
           'could during every first found from have having into just like little made make many might more most much must '
           'never new news only other over said same says should show shows since some still such than that their them then '
           'there these they this those through under until very want week what when where which while will with within '
           'without would years year study studies scientists researchers research people today report reports'.split())


def _stories(content):
    out = []
    if content.get('lead'):
        out.append(content['lead'])
    if content.get('sidebar'):
        out.append(content['sidebar'])
    for u in content.get('units', []):
        if u[0] != 'roundup':
            out += u[1:]
    return out


def _story_text(st):
    return ' '.join(plain(b[1]) for b in st.get('blocks', []) if b and b[0] in ('p', 'dropcap') and isinstance(b[1], str))


def _recent_puzzles(date, days=90):
    root = paths.editions_dir()
    out = []
    if not os.path.isdir(root):
        return out
    cutoff = (date - datetime.timedelta(days=days)).isoformat()
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d, 'puzzles.json')
        if re.match(r'^\d{4}-\d{2}-\d{2}$', d) and cutoff <= d < date.isoformat() and os.path.exists(p):
            try:
                with open(p) as f:
                    out.append(json.load(f))
            except (OSError, json.JSONDecodeError):
                pass
    return out


# ------------------------------------------------------------------ cryptogram
def cryptogram(content, date, rng):
    recent = {(p.get('crypt_plain') or '').strip().upper() for p in _recent_puzzles(date)}
    if R.CRYPTOGRAM_SOURCE == 'stories':
        for st in _stories(content):
            for b in st.get('blocks', []):
                if b and b[0] == 'quote' and len(b) > 2:
                    q = plain(b[1])
                    letters = sum(ch.isalpha() for ch in q)
                    if 35 <= letters <= 110 and q.isascii() and q.upper() not in recent:
                        return dict(quote=q.upper(), who=plain(b[2]),
                                    intro=f'A line from today&rsquo;s paper (page {{p:{st["id"]}}}).')
    with open(os.path.join(paths.BUNDLED, 'quotes.json')) as f:
        corpus = json.load(f) + list(R.CUSTOM_QUOTES)
    tags = set()
    for st in _stories(content):
        tags.update(CAT_TAGS.get(st.get('category'), []))
    pool = [q for q in corpus if q['quote'].upper() not in recent]
    pool.sort(key=lambda q: (-len(tags & set(q.get('tags', []))), rng.random()))
    q = pool[0] if pool else corpus[0]
    return dict(quote=q['quote'].upper(), who=q['who'], intro='A classic line for the morning.')


# ------------------------------------------------------------------ scramble and word search
def _good_word(w, lo=4, hi=9):
    """An everyday, concrete word: in the dictionary, common but not a filler word, and a noun, verb or adjective."""
    wl = w.lower()
    if not (w.isalpha() and w.isascii() and lo <= len(w) <= hi and wl not in STOP and wl in dictionary()
            and common(wl) and 3.0 <= W.zipf(wl) <= 4.9 and not W.is_proper_only(wl)):
        return False
    d = W.definition(wl)
    return bool(d) and d[0] in ('noun', 'verb', 'adjective')


def headline_words(content, n=7, lo=5, hi=8):
    """[(word, story id)] picked from headlines (then decks), one word per story where possible."""
    picks, seen = [], set()
    stories = _stories(content)
    for field in ('headline', 'deck'):
        for st in stories:
            for w in re.findall(r"[A-Za-z]+", plain(st.get(field, ''))):
                wl = w.lower()
                if wl in seen or not _good_word(w, lo, hi):
                    continue
                if any(sid == st['id'] for _, sid in picks) and len(picks) < len(stories):
                    continue
                seen.add(wl)
                picks.append((wl.upper(), st['id']))
                break
            if len(picks) >= n:
                return picks
    for st in stories:     # still short: words from story text
        for w in re.findall(r"[A-Za-z]+", _story_text(st))[:400]:
            if len(picks) >= n:
                return picks
            wl = w.lower()
            if wl not in seen and _good_word(w, lo, hi):
                seen.add(wl)
                picks.append((wl.upper(), st['id']))
    return picks


def scramble(content):
    picks = headline_words(content, R.SCRAMBLE_WORDS)
    if len(picks) < R.SCRAMBLE_WORDS:
        extra = ['MORNING', 'COFFEE', 'GARDEN', 'PLANET', 'CANDLE', 'BRIDGE', 'RIVER', 'PUZZLE', 'LANTERN', 'MEADOW']
        picks += [(w, None) for w in extra if w not in {p for p, _ in picks}][:R.SCRAMBLE_WORDS - len(picks)]
    pages = [f'{{p:{sid}}}' for sid in dict.fromkeys(sid for _, sid in picks if sid)]
    pg = ', '.join(pages[:-1]) + (' and ' if len(pages) > 1 else '') + pages[-1] if pages else ''
    return dict(title='Headline Scramble', words=[w for w, _ in picks[:R.SCRAMBLE_WORDS]],
                intro=f'Unscramble seven words from today&rsquo;s headlines{" (pages " + pg + ")" if pg else ""}.')


def wordsearch_words(content, scramble_words):
    words = list(scramble_words)
    for w, _ in headline_words(content, 14, 4, 10):
        if w not in words:
            words.append(w)
    return words[:12]


# ------------------------------------------------------------------ ladder
def ladder(date, rng):
    recent = {tuple(p.get('ladder', [])[:1] + p.get('ladder', [])[-1:]) for p in _recent_puzzles(date, 60)}
    pairs = list(LADDER_PAIRS)
    rng.shuffle(pairs)
    bad = {'anal', 'oral', 'dead', 'death', 'evil', 'hate', 'curse', 'kill'}
    pairs += [p for p in W.antonym_pairs() if not (set(p) & bad)]
    for a, b in pairs:
        if (a.upper(), b.upper()) in recent:
            continue
        try:
            path = find_ladder(a, b)
        except Exception:  # noqa: BLE001
            path = None
        if path and 4 <= len(path) <= 7:
            return dict(words=path, note=f'From {a} to {b}.')
    return dict(words=find_ladder('cold', 'warm') or ['COLD', 'CORD', 'WORD', 'WORM', 'WARM'], note='From cold to warm.')


# ------------------------------------------------------------------ teasers
def _sequence(rng):
    kind = rng.choice(['arith', 'geom', 'square', 'tri', 'fib', 'alt'])
    if kind == 'arith':
        a, d = rng.randint(2, 20), rng.randint(3, 13)
        seq = [a + d * i for i in range(6)]
    elif kind == 'geom':
        a, r = rng.randint(1, 5), rng.choice([2, 3])
        seq = [a * r ** i for i in range(6)]
    elif kind == 'square':
        k = rng.randint(0, 5)
        seq = [i * i + k for i in range(1, 7)]
    elif kind == 'tri':
        seq = [i * (i + 1) // 2 for i in range(1, 7)]
    elif kind == 'fib':
        a, b = rng.randint(1, 4), rng.randint(2, 6)
        seq = [a, b]
        while len(seq) < 6:
            seq.append(seq[-1] + seq[-2])
    else:
        a, x, y = rng.randint(1, 9), rng.randint(2, 9), rng.randint(1, 5)
        seq = [a]
        for i in range(5):
            seq.append(seq[-1] + (x if i % 2 == 0 else -y))
    return ['Next in line', f'What number comes next: {", ".join(map(str, seq[:5]))}, ?', str(seq[5])]


def _target(rng, target=24):
    ops = [('+', lambda a, b: a + b), ('−', lambda a, b: a - b), ('×', lambda a, b: a * b),
           ('÷', lambda a, b: a / b if b else None)]

    def solve(nums):
        if len(nums) == 1:
            v, e = nums[0]
            return e if v is not None and abs(v - target) < 1e-9 else None
        for i, j in itertools.permutations(range(len(nums)), 2):
            rest = [nums[k] for k in range(len(nums)) if k not in (i, j)]
            (a, ea), (b, eb) = nums[i], nums[j]
            for sym, f in ops:
                v = f(a, b)
                if v is None:
                    continue
                r = solve(rest + [(v, f'({ea} {sym} {eb})')])
                if r:
                    return r
        return None
    for _ in range(400):
        ns = sorted(rng.randint(1, 9) for _ in range(4))
        e = solve([(float(n), str(n)) for n in ns])
        if e:
            e = e[1:-1] if e.startswith('(') and e.endswith(')') else e
            return ['Make ' + str(target), f'Use {ns[0]}, {ns[1]}, {ns[2]} and {ns[3]} once each, with + &minus; &times; &divide; '
                    f'and parentheses, to make {target}.', f'One way: {e} = {target}']
    return ['Make 24', 'Use 3, 3, 8 and 8 once each, with + &minus; &times; &divide; and parentheses, to make 24.', 'One way: 8 ÷ (3 − 8 ÷ 3) = 24']


def _calendar(date, rng):
    import ephem
    from .. import almanac as A
    events = []
    for name, fn in (('the winter solstice', ephem.next_winter_solstice), ('the summer solstice', ephem.next_summer_solstice),
                     ('the spring equinox', ephem.next_spring_equinox), ('the autumn equinox', ephem.next_autumn_equinox)):
        t = A.local(fn(A.edate(date)))
        events.append(((t.date() - date).days, name, t.date()))
    days, name, when = min(events)
    if rng.random() < 0.5 and days > 2:
        return ['Countdown', f'Counting from today, how many days until {name}? (Hint: it falls in {when:%B}.)', f'{days} days ({when:%b}. {when.day})']
    k = rng.choice([50, 100, 150, 200, 250])
    d2 = date + datetime.timedelta(days=k)
    return ['Calendar', f'Today is a {date:%A}. What day of the week will it be {k} days from today?', f'{d2:%A} ({d2:%b}. {d2.day}, {d2.year})']


def teasers(date, rng):
    return [_sequence(rng), _target(rng), _calendar(date, rng)][:R.TEASERS]


# ------------------------------------------------------------------ crossword
def _blank_clue(word, content):
    """A fill-in-the-blank clue from a story sentence containing the word, or None."""
    rx = re.compile(r'\b' + re.escape(word) + r'\b', re.I)
    for st in _stories(content):
        for s in sentences(_story_text(st)):
            m = rx.search(s)
            if not m or len(s.split()) > 40:
                continue
            ws = s.split()
            idx = next((i for i, w in enumerate(ws) if rx.search(w)), None)
            if idx is None:
                continue
            lo, hi = max(0, idx - 6), min(len(ws), idx + 6)
            frag = ' '.join(ws[lo:hi])
            frag = rx.sub('___', frag, count=1)
            frag = ('&hellip;' if lo else '') + esc(frag.strip(' ,;:')) + ('&hellip;' if hi < len(ws) else '')
            return f'&ldquo;{frag}&rdquo; (page {{p:{st["id"]}}})'
    return None


def crossword(content, date, log=print, seconds=45):
    avoid = []
    for p in _recent_puzzles(date, 10)[-5:]:
        if p.get('crossword', {}).get('grid'):
            avoid.append(mask(p['crossword']['grid']))
    prefer = set()
    for st in _stories(content):
        for w in re.findall(r'[A-Za-z]+', plain(st.get('headline', '')) + ' ' + _story_text(st)[:3000]):
            if 3 <= len(w) <= 11:
                prefer.add(w.upper())
    extra_ban = []
    import time as _t
    for attempt in range(3):
        t0 = _t.time()
        try:
            pat, grids = fill_first(avoid, prefer, extra_ban, seconds)
        except Exception as e:  # noqa: BLE001
            log(f'crossword: filler failed ({e})')
            grids = []
        log(f'crossword: fill attempt {attempt + 1} took {_t.time() - t0:.0f} s')
        if not grids:
            continue
        grid = grids[0]
        _, ac, dn = entries(grid)
        clues, blanks = {}, 0
        for _, wd in ac + dn:
            if wd in clues:
                continue
            c = None
            if blanks < 5 and wd in prefer and len(wd) >= 4:
                c = _blank_clue(wd, content)
                blanks += 1 if c else 0
            c = c or (W.clue(wd) and esc(W.clue(wd)))
            if not c:
                extra_ban.append(wd.lower())
                break
            clues[wd] = c
        else:
            return dict(grid=grid, clues=clues)
        log(f'crossword: no clue for {extra_ban[-1]}; refilling')
    log('crossword: could not fill a grid; leaving it out')
    return None


def fill_first(avoid, prefer, extra_ban, seconds):
    from . import fill_crossword
    return fill_crossword(avoid=avoid, seeds=6, seconds=seconds, procs=2, extra_ban=extra_ban, prefer=prefer,
                          need_clue=True, first=True)


# ------------------------------------------------------------------ word of the day
def word_of_the_day(content, date):
    best = None
    for st in _stories(content):
        for w in set(re.findall(r'\b[a-z]{6,14}\b', _story_text(st))):
            z = W.zipf(w)
            if not 2.0 <= z <= 3.5 or W.is_proper_only(w):
                continue
            d = W.definition(w)
            rs = W.respell(w)
            if not d or not rs:
                continue
            if GRIM.search(d[1]) or GRIM.search(w) or d[0] == 'adverb' or len(d[1].split()) < 3:
                continue
            score = (3.5 - z) + (0.3 if st is content.get('lead') else 0)
            if best is None or score > best[0]:
                best = (score, w, rs, d, st['id'])
    if not best:
        return None
    _, w, rs, (pos, gloss), sid = best
    return [w, rs, pos, f'{esc(gloss)}. It appears in today&rsquo;s paper on page {{p:{sid}}}.']


# ------------------------------------------------------------------ all inputs
def inputs(content, date, log=print, want_crossword=True):
    rng = random.Random(int(date.strftime('%Y%m%d')))
    pz = {}
    secs = set(R.TAIL)
    if 'word' in secs:
        pz['cryptogram'] = cryptogram(content, date, rng)
        pz['scramble'] = scramble(content)
        pz['ladder'] = ladder(date, rng)
    if 'sudoku' in secs and R.SUDOKU_EXTRA == 'teasers':
        pz['teasers'] = teasers(date, rng)
    if 'xword' in secs and want_crossword:
        xw = crossword(content, date, log)
        if xw:
            pz['crossword'] = xw
    if 'logic' in secs and 'wordsearch' in R.LOGIC_PUZZLES:
        pz['wordsearch_words'] = wordsearch_words(content, pz.get('scramble', {}).get('words', []))
        pz['wordsearch_title'] = 'Word Search: Today&rsquo;s Paper'
    return pz
