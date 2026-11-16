"""Settings: one YAML file in the data directory, validated with pydantic.

Everything a household might want to change lives here: the paper's name and place, page format,
which sections run, categories and their keywords, sources, filters, puzzles, schedule, printer,
delivery and AI. `load()` reads the file (missing keys take defaults), and `activate()` copies
the values into `rules`, which the layout, planner, puzzles and QA read.

Secrets (API keys, SMTP and admin passwords, push tokens) never go in config.yaml; see secrets.py.
"""
from __future__ import annotations

import copy
import datetime
import os
import re
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from . import paths, profiles

SECTION_NAMES = ('wonders', 'almanac', 'word', 'sudoku', 'xword', 'logic', 'back')
SECTION_LABELS = {'wonders': 'Small Wonders', 'almanac': 'Almanac', 'word': 'Word Play (cryptogram, scramble, ladder)',
                  'sudoku': 'Sudoku and teasers', 'xword': 'Crossword', 'logic': 'Logic puzzles (KenKen, futoshiki, word search...)',
                  'back': 'Back page (answers, sources, notes)'}
LICENSES = ('public-domain', 'cc-by', 'cc-by-sa', 'cc-by-nd', 'cc-by-nc', 'cc-by-nc-sa', 'cc-by-nc-nd', 'copyrighted')
TIERS = ('full', 'verbatim', 'excerpt', 'headline')
LOGIC_PUZZLES = ('kenken', 'futoshiki', 'wordsearch', 'nonogram', 'kakuro')


def _load_yaml(name):
    with open(os.path.join(paths.BUNDLED, name)) as f:
        return yaml.safe_load(f)


def tier_for(license_: str) -> str:
    """How much of an article a license lets the paper print without rewriting it."""
    if license_ in ('public-domain', 'cc-by', 'cc-by-sa', 'cc-by-nc', 'cc-by-nc-sa'):
        return 'full'
    if license_ in ('cc-by-nd', 'cc-by-nc-nd'):
        return 'verbatim'
    return 'excerpt'


# ------------------------------------------------------------------ sections of the file
class Paper(BaseModel):
    title: str = 'The Morning Current'
    tagline: str = 'Good news, told in full'
    volume: str = 'I'
    about: str = ''                       # back-page "About this paper"; blank = generated from the settings
    household: str = ''                   # e.g. "one household in the Upstate" (used in the generated About text)
    language: Literal['en'] = 'en'


class Location(BaseModel):
    name: str = 'New York, N.Y.'
    lat: float = 40.7128
    lon: float = -74.0060
    elevation: float = 10
    tz: str = 'America/New_York'
    note: str = ''                        # printed after the almanac's "Times are for ..." line

    @field_validator('tz')
    @classmethod
    def _tz(cls, v):
        from zoneinfo import ZoneInfo
        ZoneInfo(v)
        return v


class Format(BaseModel):
    profile: str = profiles.DEFAULT
    pages: int = 16                       # the usual (and maximum) page count; a multiple of 4
    pages_light: int = 12                 # thin days
    pages_min: int = 12                   # the smallest paper the planner may make
    deep_dive: bool = True                # a two-page story on the centre spread
    sections: list[str] = Field(default_factory=lambda: ['wonders', 'almanac', 'word', 'sudoku', 'xword', 'back'])
    shapes: list[Literal['feature', 'split', 'roundup']] = Field(default_factory=lambda: ['feature', 'split', 'roundup'])
    sidebar: bool = True                  # allow a second story under the lead's continuation on page 2
    index_on_front: bool = True
    sky_strip: bool = True
    photos: bool = True                   # print public-domain photos (grayscale) when a source allows it
    clock: Literal['24h', '12h'] = '24h'
    units: Literal['imperial', 'metric', 'both'] = 'imperial'
    fill_story: int = 90                  # % of column height every story column must reach
    fill_other: int = 85

    @field_validator('sections')
    @classmethod
    def _sections(cls, v):
        bad = [s for s in v if s not in SECTION_NAMES]
        if bad:
            raise ValueError(f'unknown sections {bad}; choose from {SECTION_NAMES}')
        return list(dict.fromkeys(v))

    @field_validator('profile')
    @classmethod
    def _profile(cls, v):
        if v not in profiles.PROFILES:
            raise ValueError(f'unknown paper profile {v!r}; choose from {list(profiles.PROFILES)}')
        return v

    @model_validator(mode='after')
    def _pages(self):
        for name in ('pages', 'pages_light', 'pages_min'):
            n = getattr(self, name)
            if n % 4 or n < 4 or n > 32:
                raise ValueError(f'{name} must be a multiple of 4 between 4 and 32 (got {n})')
        if not (self.pages_min <= self.pages_light <= self.pages):
            raise ValueError('page counts must satisfy pages_min <= pages_light <= pages')
        return self


class Puzzles(BaseModel):
    sudoku_by_weekday: list[str] = Field(default_factory=lambda: ['easy', 'easy', 'easy+', 'easy-medium', 'easy-medium', 'medium', 'medium+'])
    sudoku_extra: Literal['teasers', 'kenken', 'futoshiki', 'none'] = 'teasers'   # what fills the bottom of the sudoku page
    logic: list[str] = Field(default_factory=lambda: ['kenken', 'futoshiki', 'wordsearch'])   # the optional logic page
    crossword_min: int = 9
    crossword_max: int = 11
    scramble_words: int = 7
    teasers: int = 3
    cryptogram_source: Literal['stories', 'corpus'] = 'stories'   # stories = a verified quote from today's sources, else the corpus
    custom_quotes: list[dict] = Field(default_factory=list)     # [{quote, who}] added to the corpus

    @field_validator('sudoku_by_weekday')
    @classmethod
    def _sdk(cls, v):
        ok = ('easy', 'easy+', 'easy-medium', 'medium', 'medium+')
        if len(v) != 7 or any(x not in ok for x in v):
            raise ValueError(f'sudoku_by_weekday needs 7 levels (Mon..Sun) from {ok}')
        return v

    @field_validator('logic')
    @classmethod
    def _logic(cls, v):
        bad = [x for x in v if x not in LOGIC_PUZZLES]
        if bad:
            raise ValueError(f'unknown logic puzzles {bad}; choose from {LOGIC_PUZZLES}')
        return v


class Category(BaseModel):
    name: str
    family: Literal['science', 'health', 'tech', 'culture'] = 'culture'
    keywords: list[str] = Field(default_factory=list)
    weight: float = 1.0                   # 0 = never pick stories from it
    favorite: bool = False
    enabled: bool = True
    cap: Optional[int] = None             # most story pages per paper (None = editorial.max_same_category)


def _default_categories():
    return [Category(**c) for c in _load_yaml('categories.yaml')]


DEFAULT_BLOCKLIST = [
    # crime and courts
    'murder*', 'homicide*', 'shooting*', 'gunman', 'stabbing*', 'stabbed', 'arrested', 'indicted', 'convicted', 'sentenced',
    'prison', 'jailed', 'robbery', 'kidnap*', 'assault*', 'rape*', 'trafficking', 'cartel*', 'lawsuit*', 'sued',
    # disasters and death
    'killed', 'kills', 'death toll', 'dead', 'deaths', 'fatal*', 'casualt*', 'tragedy', 'tragic', 'disaster*', 'catastroph*',
    'plane crash*', 'massacre*', 'famine', 'evacuat*', 'wildfire*', 'mass extinction',
    # politics and conflict
    'trump', 'biden', 'harris', 'vance', 'republican*', 'democrat*', 'gop', 'senate', 'senator*', 'congressman',
    'congresswoman', 'election*', 'ballot*', 'campaign trail', 'white house', 'prime minister', 'parliament*',
    'impeach*', 'partisan', 'lawmaker*', 'tariff*', 'sanction*', 'supreme court', 'war', 'wars', 'warfare', 'airstrike*',
    'missile*', 'troops', 'invasion', 'ceasefire', 'hostage*', 'terror*', 'militant*', 'genocide', 'military', 'weapon*',
    'adversar*', 'pentagon', 'anduril', 'drone strike*', 'nuclear weapon*', 'politic*', 'lobbyist*', 'lobbying', 'congressional', 'espionage', 'honey trap*', 'extramarital',
    # sensational, business gloom
    'shocking', 'horrifying', 'outrage*', 'slams', 'feud', 'scandal*', 'layoff*', 'bankrupt*', 'recession', 'stock market',
    'cryptocurrenc*', 'crypto', 'bitcoin', 'celebrity', 'kardashian*',
]


class Editorial(BaseModel):
    categories: list[Category] = Field(default_factory=_default_categories)
    favorites: list[str] = Field(default_factory=list)   # favorite category names (or tick favorite on a category)
    recency_days: int = 31
    recency_exception_days: int = 180
    min_categories: int = 6
    max_same_category: int = 2
    no_adjacent_same_category: bool = True
    science_share: tuple[float, float] = (0.33, 0.5)
    favorites_target: int = 3
    health_max_features: int = 1
    blocklist: list[str] = Field(default_factory=lambda: list(DEFAULT_BLOCKLIST))
    allowlist: list[str] = Field(default_factory=lambda: ['dead sea', 'dead zone recovery', 'war of the worlds', 'star wars'])
    downweight: list[str] = Field(default_factory=lambda: [
        'emergency', 'evict*', 'displac*', 'crisis', 'crises', 'fail*', 'threat*', 'warn*', 'outage*', 'protest*', 'conflict*',
        'illegal*', 'controvers*', 'decline*', 'dying', 'collapse*', 'pollut*', 'toxic', 'shortage*', 'banned', 'audit*',
        'lawsuit*', 'cuts', 'deadline', 'disease*', 'invasive', 'poach*', 'smuggl*', 'loss', 'losses', 'deadly', 'risk*',
        # housekeeping and promotion rather than stories
        'shortlist*', 'award*', 'conference', 'webinar', 'apply', 'applications', 'podcast', 'livestream', 'register',
        'registration', 'nominat*', 'press release', 'hiring', 'internship*', 'funding opportunit*', 'call for', 'outage*',
        'calendar', 'town hall', 'archive', 'apod'])
    upweight: list[str] = Field(default_factory=lambda: [
        'discover*', 'first', 'record', 'rebound*', 'recover*', 'breakthrough*', 'new species', 'surpris*', 'clever',
        'invent*', 'restor*', 'reviv*', 'success*', 'celebrat*', 'solv*', 'found', 'reveal*', 'unexpected', 'curious',
        'mystery', 'ancient', 'tiny', 'giant', 'how', 'why', 'build*', 'designed', 'innovat*'])
    tone_threshold: float = -0.7          # reject headlines whose VADER sentiment is below this (milder ones score lower)
    wonders_count: tuple[int, int] = (5, 6)
    reserve_count: int = 6
    filler_wikipedia: bool = True         # Wikipedia "On this day" and featured-article extracts as filler
    reader_profile: str = 'A technical, curious reader who likes clear explanations and surprising details.'
    classifier: Literal['keywords', 'learned', 'embeddings'] = 'learned'

    def category_names(self, enabled_only=True):
        return [c.name for c in self.categories if c.enabled or not enabled_only]

    def category(self, name):
        return next((c for c in self.categories if c.name == name), None)

    def favorite_names(self):
        names = self.category_names()
        return [n for n in dict.fromkeys([c.name for c in self.categories if c.favorite] + list(self.favorites)) if n in names]


class Source(BaseModel):
    name: str
    url: str
    homepage: str = ''
    category: Optional[str] = None        # default category for the feed's items
    license: Literal[LICENSES] = 'copyrighted'
    tier: Optional[Literal[TIERS]] = None # override: full | verbatim | excerpt | headline
    trust: float = 1.0
    enabled: bool = True
    fetch_full_text: bool = True          # fetch the article page when the feed carries only a summary
    images: bool = False
    attribution: str = ''
    max_per_edition: int = 3
    pack: str = ''
    notes: str = ''

    @property
    def use(self):
        return self.tier or tier_for(self.license)

    @field_validator('url')
    @classmethod
    def _url(cls, v):
        if not re.match(r'^https?://', v.strip()):
            raise ValueError('feed URL must start with http:// or https://')
        return v.strip()


def source_packs():
    return _load_yaml('sources.yaml')


def _default_sources():
    out = []
    for pack in source_packs():
        if pack.get('default'):
            out += [Source(pack=pack['id'], **s) for s in pack['sources']]
    return out


class Sources(BaseModel):
    feeds: list[Source] = Field(default_factory=_default_sources)
    refresh_hours: int = 3
    user_agent: str = 'MorningCurrent/1.0 (+https://github.com/au12/MorningCurrent)'
    respect_robots: bool = True
    per_host_delay: float = 1.0
    timeout: float = 20.0
    keep_days: int = 120                  # how long fetched articles stay in the database


class Schedule(BaseModel):
    build_enabled: bool = True
    build_time: str = '00:30'             # local time the nightly paper is made
    print_enabled: bool = False
    weekday_enabled: bool = True
    weekday_time: str = '06:30'
    weekend_enabled: bool = True
    weekend_time: str = '08:00'
    pause_until: str = ''
    missing_policy: Literal['skip', 'latest'] = 'skip'
    keep_days: int = 60                   # editions older than this are pruned (0 = keep forever)
    ship_on_cosmetic_qa: bool = True      # deliver even if a column misses its fill target

    @field_validator('build_time', 'weekday_time', 'weekend_time')
    @classmethod
    def _hhmm(cls, v):
        if not re.match(r'^([01]\d|2[0-3]):[0-5]\d$', v):
            raise ValueError('times are HH:MM, 24-hour')
        return v


class Printer(BaseModel):
    cups_server: str = ''
    printer: str = ''
    copies: int = 1
    sides: str = ''                       # blank = from the paper profile
    media: str = ''                       # blank = from the paper profile
    extra_options: str = ''


class Email(BaseModel):
    enabled: bool = False
    smtp_host: str = ''
    smtp_port: int = 587
    starttls: bool = True
    username: str = ''
    sender: str = ''
    to: list[str] = Field(default_factory=list)
    attach: Literal['reading', 'booklet', 'both'] = 'reading'


class Remote(BaseModel):
    enabled: bool = False
    url: str = ''                         # another Morning Current/Press server's /api/editions


class Delivery(BaseModel):
    folder: str = ''                      # also copy PDFs here (e.g. a mounted /output)
    email: Email = Field(default_factory=Email)
    remote: Remote = Field(default_factory=Remote)
    webhook: str = ''                     # POST a JSON summary here after each build


class AI(BaseModel):
    provider: Literal['none', 'claude', 'openai'] = 'none'
    mode: Literal['rewrite', 'research'] = 'rewrite'
    model: str = 'claude-sonnet-5-5'
    base_url: str = ''                    # OpenAI-compatible endpoint, e.g. http://ollama:11434/v1
    max_cost_usd: float = 1.50            # per edition; the build falls back to no-AI when it runs out
    prices: dict[str, tuple[float, float]] = Field(default_factory=dict)   # model -> (USD per M input, per M output)
    write_stories: bool = True
    write_puzzles: bool = True            # crossword clues, teasers, word of the day
    research_searches: int = 20
    house_style: str = ''                 # blank = the built-in style guide
    verify: bool = True                   # check every quote and number against the fetched source
    temperature: float = 0.4


class Web(BaseModel):
    public_reader: bool = True
    public_feedback: bool = False
    base_url: str = ''


class Config(BaseModel):
    version: int = 1
    paper: Paper = Field(default_factory=Paper)
    location: Location = Field(default_factory=Location)
    format: Format = Field(default_factory=Format)
    puzzles: Puzzles = Field(default_factory=Puzzles)
    editorial: Editorial = Field(default_factory=Editorial)
    sources: Sources = Field(default_factory=Sources)
    schedule: Schedule = Field(default_factory=Schedule)
    printer: Printer = Field(default_factory=Printer)
    delivery: Delivery = Field(default_factory=Delivery)
    ai: AI = Field(default_factory=AI)
    web: Web = Field(default_factory=Web)
    setup_complete: bool = False

    @model_validator(mode='after')
    def _layout_fits(self):
        problems = layout_problems(self)
        if problems:
            raise ValueError('; '.join(problems))
        return self


def units_needed(pages, sections, deep_dive=True):
    """Single-page story units a paper of `pages` needs between page 2 and the tail sections."""
    return pages - 2 - len(sections) - (2 if deep_dive else 0)


def layout_problems(cfg):
    out = []
    f = cfg.format
    for n in sorted({f.pages, f.pages_light, f.pages_min}):
        k = units_needed(n, f.sections, f.deep_dive)
        before = n // 2 - 3 if f.deep_dive else None
        if k < 0:
            out.append(f'{n} pages is too few for {len(f.sections)} sections plus the front pages')
        elif f.deep_dive:
            after = n // 2 - 1
            overflow = max(0, len(f.sections) - after)
            if overflow > before:
                out.append(f'{n} pages cannot fit the {len(f.sections)} tail sections around a centre spread; '
                           f'add pages, drop a section or turn off the Deep Dive')
    return out


# ------------------------------------------------------------------ load / save
_cache = {'mtime': None, 'path': None, 'cfg': None}


def load(path=None, use_cache=True) -> Config:
    path = path or paths.config_file()
    mtime = os.path.getmtime(path) if os.path.exists(path) else None
    if use_cache and _cache['path'] == path and _cache['mtime'] == mtime and _cache['cfg'] is not None:
        return _cache['cfg']
    raw = {}
    if mtime is not None:
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
    cfg = Config(**raw)
    _cache.update(mtime=mtime, path=path, cfg=cfg)
    return cfg


def dump(cfg: Config, full=False) -> str:
    """YAML for config.yaml. By default only values that differ from the defaults are written, so
    improvements to the defaults (keywords, blocklist, sources) reach existing installations."""
    data = cfg.model_dump(mode='json', exclude_defaults=not full)
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110) if data else '{}\n'



def save(cfg: Config, path=None):
    path = path or paths.config_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        f.write('# The Morning Current settings. Edit here or in the web UI (Settings).\n')
        f.write(dump(cfg))
    os.replace(tmp, path)
    _cache.update(mtime=None, path=None, cfg=None)
    return path


def update(cfg: Config, patch: dict) -> Config:
    """Return a new validated Config with `patch` (nested dict) merged in."""
    data = cfg.model_dump(mode='python')

    def merge(a, b):
        for k, v in b.items():
            if isinstance(v, dict) and isinstance(a.get(k), dict):
                merge(a[k], v)
            else:
                a[k] = v
    merge(data, copy.deepcopy(patch))
    return Config(**data)


def activate(cfg: Config | None = None) -> Config:
    """Load (if needed) and copy settings into rules. Returns the Config."""
    from . import rules
    cfg = cfg or load()
    rules.apply(cfg)
    return cfg


def today(cfg: Config | None = None) -> datetime.date:
    from zoneinfo import ZoneInfo
    cfg = cfg or load()
    return datetime.datetime.now(ZoneInfo(cfg.location.tz)).date()
