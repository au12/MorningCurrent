"""Every format and editorial rule that code enforces, in one place.

The values below are the defaults (they reproduce the original Morning Current: Legal sheets folded
to 7 x 8.5 in, 16 pages). `apply(config)` overwrites them from the installation's settings, so
templates, CSS, the planner, the puzzle generator and QA all follow config.yaml. Code reads these
names at call time (`rules.PAGE_W`), never at import time, so a reloaded config takes effect.
"""
from . import profiles as _profiles

# ------------------------------------------------------------------ product
TITLE = 'The Morning Current'
TAGLINE = 'Good news, told in full'
VOLUME = 'I'
ABOUT = ''
HOUSEHOLD = ''
LOCATION = dict(name='New York, N.Y.', lat='40.7128', lon='-74.0060', elevation=10, tz='America/New_York', note='')

# ------------------------------------------------------------------ physical format (inches)
PROFILE = _profiles.DEFAULT
PAGE_W, PAGE_H = 7.0, 8.5                 # finished page; legal sheet folded once
BOOKLET = True
SHEET = 'Legal'
SIDES = 'two-sided-short-edge'
PAGES_DEFAULT, PAGES_LIGHT, PAGES_MIN = 16, 12, 12
MARGIN = dict(inner=0.58, outer=0.42, top=0.62, top_front=0.38, bottom=0.52, rhead=0.34, folio=0.26)
COL_GAP = 0.19                             # two body columns, hairline rule between
PALETTE = dict(ink='#111', dark='#222', mid='#333', grey='#666', rule='#9a9a9a', light='#bbb',
               shade='#ececec', shade2='#e4e4e4')

# ------------------------------------------------------------------ type (points)
BODY_PT, BODY_LEADING, BODY_MIN_PT = 9.1, 1.31, 8.8
TYPE = dict(title=40, h1=27, h2=21, h3=15, h3_split=16, deck=10.6, deck_split=9.6, kicker=7, h4=7.4,
            brief_head=7.2, brief=8.8, odd_head=11.5, src=6.7, chart_title=6.8, chart_note=6.0, skystrip=6.6,
            pull=13, ptitle=16)
FONTS = dict(title='Fraktur', head='Playfair', body='SSerif', sans='Franklin')
HEADLINE_MAX_CHARS = dict(h1=75, h2=70, split=48)   # keeps H2 to 2 lines (3 max), split heads to 3
SIZES = dict(sudoku_cell=0.5, xword_cell=0.31, ladder_cell=0.3, logic_cell=0.42, index_cols=4, teaser_cols=3)

# ------------------------------------------------------------------ QR codes
QR_SIZE, QR_INLINE, QR_INLINE_LONG, QR_LONG_URL = '0.54in', '0.46in', '0.56in', 90

# ------------------------------------------------------------------ fit (QA thresholds, % of column height)
FILL_STORY = 90      # every column of a story page
FILL_OTHER = 85      # almanac, back page and puzzle pages with columns
LINE_PX = 12.4       # one body line at 96 dpi, for hidden-line counts
CLOCK = '24h'
UNITS = 'imperial'

# ------------------------------------------------------------------ page plan
# Pages run: front, cont, story units..., [spread on the centre pair], story units..., tail sections.
# Tail sections that don't fit after the spread move, in order, to just before it.
HEAD = ('front', 'cont')
TAIL = ('wonders', 'almanac', 'word', 'sudoku', 'xword', 'back')
DEEP_DIVE = True
SIDEBAR_OK = True
INDEX_ON_FRONT = True
SKY_STRIP = True
PHOTOS = True
SHAPES = {   # story unit shapes and how many pages each takes
    'feature': 1,      # one story, two columns (classic, Q&A, how-it-works, list, profile, data page, essay)
    'split': 1,        # two stories, one column each, each with its own head and source box
    'roundup': 1,      # four to seven short items with QR codes (headline + summary), themed by category
    'spread': 2,       # the Deep Dive, centre pair only
}
ALLOWED_SHAPES = ('feature', 'split', 'roundup')
MAX_SAME_CATEGORY = 2          # story pages per category (spread counts as 1)
NO_ADJACENT_SAME_CATEGORY = True

# ------------------------------------------------------------------ editorial
RECENCY_DAYS = 31              # default window: about the last month
RECENCY_EXCEPTION_DAYS = 180   # allowed for something extraordinary, important or a perfect fit for the reader
MEDICINE_MAX_FEATURES = 1
HEALTH_CATEGORIES = ['Health & Medicine']
CATEGORIES = [   # a broad wheel; each paper should span many of these (>= MIN_CATEGORIES)
    'Space', 'Earth & Climate', 'Nature & Wildlife', 'Oceans & Weather', 'Physics & Chemistry', 'Materials',
    'Biology & the Brain', 'Health & Medicine', 'Human Origins & Archaeology', 'History & Everyday Things',
    'Engineering & Energy', 'Cars & Motorsport', 'Transport & Aviation', 'Robotics', 'Computing & Codes',
    'Home Tech & Self-Hosting', 'Makers & DIY', 'Photography & Imaging', 'Art & Design', 'Architecture',
    'Food & Farming', 'Language & Words', 'Music & Sound', 'Sport & Games', 'Math & Puzzles',
    'Places & Maps', 'People & Odd Jobs', 'Clever Businesses & Inventions',
]
ALL_CATEGORIES = list(CATEGORIES)   # includes disabled ones, so old editions still validate
FAVORITES = []                 # the reader's favorite categories (about three stories a day come from these)
SCIENCE_FAMILY = ['Space', 'Earth & Climate', 'Nature & Wildlife', 'Oceans & Weather', 'Physics & Chemistry',
                  'Materials', 'Biology & the Brain', 'Human Origins & Archaeology']
CATEGORY_CAPS = {}
MIN_CATEGORIES = 6             # distinct categories across story pages + Small Wonders
WONDERS_COUNT = (5, 6)

# ------------------------------------------------------------------ almanac
ALMANAC_DAYS = 30              # sky calendar look-ahead
CONJUNCTION_MAX_DEG = 3.0      # Moon-planet / planet-planet pairs worth a calendar row
VIEW_TIMES = ((6, 30), (19, 0))   # local morning / evening check times for visibility
METEOR_SHOWERS = [  # (name, peak month, peak day, typical ZHR) — dates shift a day or so by year
    ('Quadrantids', 1, 3, 80), ('Lyrids', 4, 22, 18), ('Eta Aquariids', 5, 6, 50), ('Perseids', 8, 12, 100),
    ('Draconids', 10, 8, 10), ('Orionids', 10, 21, 20), ('Southern Taurids', 11, 5, 5), ('Northern Taurids', 11, 12, 5),
    ('Leonids', 11, 17, 15), ('Geminids', 12, 14, 120), ('Ursids', 12, 22, 10),
]
FULL_MOON_NAMES = {1: 'Wolf', 2: 'Snow', 3: 'Worm', 4: 'Pink', 5: 'Flower', 6: 'Strawberry', 7: 'Buck',
                   8: 'Sturgeon', 9: 'Harvest', 10: "Hunter's", 11: 'Beaver', 12: 'Cold'}
SKY_GUIDE = ('https://science.nasa.gov/skywatching/whats-up/', 'This month&rsquo;s sky guide',
             'NASA, What&rsquo;s Up; times and positions computed with PyEphem')

# ------------------------------------------------------------------ puzzles
# Sudoku difficulty rises through the week. givens = clue count range; techniques = the hardest
# technique the logical solver may need; hidden = (min, max) hidden-single steps.
SUDOKU_LEVELS = {
    'easy':        dict(label='Easy',          givens=(36, 38), technique='singles', hidden=(0, 8)),
    'easy+':       dict(label='Easy+',         givens=(34, 35), technique='singles', hidden=(6, 14)),
    'easy-medium': dict(label='Easy–Medium',   givens=(32, 33), technique='singles', hidden=(9, 99)),
    'medium':      dict(label='Medium',        givens=(29, 31), technique='singles', hidden=(12, 99)),
    'medium+':     dict(label='Medium+',       givens=(27, 28), technique='locked', hidden=(12, 99)),
}
SUDOKU_BY_WEEKDAY = ['easy', 'easy', 'easy+', 'easy-medium', 'easy-medium', 'medium', 'medium+']  # Mon..Sun
SUDOKU_EXTRA = 'teasers'
LOGIC_PUZZLES = ['kenken', 'futoshiki', 'wordsearch']
CROSSWORD = dict(min_size=9, max_size=11, min_word=3, cell_in=0.31, symmetric=True)
WORD_ZIPF = {3: 3.4, 4: 3.1, 'long': 2.8}      # crossword / ladder dictionary frequency floors
SCRAMBLE_WORDS = 7
TEASERS = 3
CRYPTOGRAM_SOURCE = 'stories'
CUSTOM_QUOTES = []

# ------------------------------------------------------------------ delivery
PRESS_URL = ''                 # legacy CLI `deliver`; set delivery.remote.url (or $PRESS_URL)


def apply(cfg):
    """Copy a config.Config into this module's names."""
    g = globals()
    p = _profiles.get(cfg.format.profile)
    g.update(
        TITLE=cfg.paper.title, TAGLINE=cfg.paper.tagline, VOLUME=cfg.paper.volume, ABOUT=cfg.paper.about,
        HOUSEHOLD=cfg.paper.household,
        LOCATION=dict(name=cfg.location.name, lat=str(cfg.location.lat), lon=str(cfg.location.lon),
                      elevation=cfg.location.elevation, tz=cfg.location.tz, note=cfg.location.note),
        PROFILE=cfg.format.profile, PAGE_W=p['page_w'], PAGE_H=p['page_h'], BOOKLET=p['booklet'], SHEET=p['sheet'],
        SIDES=p['sides'], MARGIN=p['margin'], COL_GAP=p['col_gap'],
        BODY_PT=p['body_pt'], BODY_LEADING=p['leading'], BODY_MIN_PT=p['body_min'], TYPE=p['type'],
        SIZES={k: p[k] for k in ('sudoku_cell', 'xword_cell', 'ladder_cell', 'logic_cell', 'index_cols', 'teaser_cols')},
        QR_SIZE=p['qr']['size'], QR_INLINE=p['qr']['inline'], QR_INLINE_LONG=p['qr']['inline_long'],
        QR_LONG_URL=p['qr']['long_url'],
        LINE_PX=round(p['body_pt'] * 4 / 3 * 1.02, 2),
        PAGES_DEFAULT=cfg.format.pages, PAGES_LIGHT=cfg.format.pages_light, PAGES_MIN=cfg.format.pages_min,
        TAIL=tuple(cfg.format.sections), DEEP_DIVE=cfg.format.deep_dive, SIDEBAR_OK=cfg.format.sidebar,
        INDEX_ON_FRONT=cfg.format.index_on_front, SKY_STRIP=cfg.format.sky_strip, PHOTOS=cfg.format.photos,
        ALLOWED_SHAPES=tuple(cfg.format.shapes), CLOCK=cfg.format.clock, UNITS=cfg.format.units,
        FILL_STORY=cfg.format.fill_story, FILL_OTHER=cfg.format.fill_other,
        RECENCY_DAYS=cfg.editorial.recency_days, RECENCY_EXCEPTION_DAYS=cfg.editorial.recency_exception_days,
        MEDICINE_MAX_FEATURES=cfg.editorial.health_max_features,
        HEALTH_CATEGORIES=[c.name for c in cfg.editorial.categories if c.family == 'health'],
        CATEGORIES=cfg.editorial.category_names(),
        ALL_CATEGORIES=list(dict.fromkeys(cfg.editorial.category_names(False) + ALL_CATEGORIES)),
        FAVORITES=cfg.editorial.favorite_names(),
        SCIENCE_FAMILY=[c.name for c in cfg.editorial.categories if c.family == 'science'],
        CATEGORY_CAPS={c.name: c.cap for c in cfg.editorial.categories if c.cap is not None},
        MIN_CATEGORIES=cfg.editorial.min_categories, MAX_SAME_CATEGORY=cfg.editorial.max_same_category,
        NO_ADJACENT_SAME_CATEGORY=cfg.editorial.no_adjacent_same_category,
        WONDERS_COUNT=tuple(cfg.editorial.wonders_count),
        SUDOKU_BY_WEEKDAY=list(cfg.puzzles.sudoku_by_weekday), SUDOKU_EXTRA=cfg.puzzles.sudoku_extra,
        LOGIC_PUZZLES=list(cfg.puzzles.logic), SCRAMBLE_WORDS=cfg.puzzles.scramble_words, TEASERS=cfg.puzzles.teasers,
        CRYPTOGRAM_SOURCE=cfg.puzzles.cryptogram_source, CUSTOM_QUOTES=list(cfg.puzzles.custom_quotes),
        CROSSWORD=dict(CROSSWORD, min_size=cfg.puzzles.crossword_min, max_size=cfg.puzzles.crossword_max,
                       cell_in=p['xword_cell']),
        PRESS_URL=cfg.delivery.remote.url,
    )


def unit_count(pages, tail=None, deep_dive=None):
    """Single-page story units needed for a paper of `pages`."""
    tail = TAIL if tail is None else tail
    deep_dive = DEEP_DIVE if deep_dive is None else deep_dive
    return pages - len(HEAD) - len(tail) - (2 if deep_dive else 0)
