"""Settings forms: which fields each tab shows, how they render and how a submitted form becomes a config patch."""
from zoneinfo import available_timezones

from .. import config, profiles

LEVELS = ['easy', 'easy+', 'easy-medium', 'medium', 'medium+']
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def F(path, label, help='', widget=None, choices=None, **kw):
    return dict(path=path, label=label, help=help, widget=widget, choices=choices, **kw)


def tabs():
    cfg = config.load()
    cats = cfg.editorial.category_names(False)
    return {
        'general': ('Paper & place', [
            F('paper.title', 'Paper name', 'Printed in the masthead (it shrinks to fit).'),
            F('paper.tagline', 'Tagline'),
            F('paper.volume', 'Volume', 'Printed as "Vol. I" next to the edition number.'),
            F('paper.household', 'Who it is for', 'Used in the About box, e.g. "one household in the Upstate". Optional.'),
            F('paper.about', 'About box text', 'Leave blank for a generated description.', 'textarea'),
            F('location.name', 'Place name', 'For the almanac, e.g. "Greenville, S.C."'),
            F('location.lat', 'Latitude', 'Decimal degrees, north positive.', 'number', step='0.0001'),
            F('location.lon', 'Longitude', 'Decimal degrees, east positive (west is negative).', 'number', step='0.0001'),
            F('location.elevation', 'Elevation (m)', '', 'number'),
            F('location.tz', 'Time zone', 'All schedules and printed times use it.', 'select', sorted(available_timezones())),
            F('location.note', 'Almanac note', 'Optional, e.g. "Asheville runs about two minutes later."'),
            F('format.clock', 'Clock', '', 'select', [('24h', '24-hour (06:30)'), ('12h', '12-hour (6:30 a.m.)')]),
            F('format.units', 'Units', 'A hint for AI writing.', 'select', ['imperial', 'metric', 'both']),
            F('web.public_reader', 'Public reader', 'Anyone with the address can read editions at /read (no login).', 'checkbox'),
            F('web.public_feedback', 'Public feedback', 'Let readers who are not signed in vote on stories.', 'checkbox'),
            F('web.base_url', 'Public address', 'e.g. https://news.example.com (used in links sent by webhook).'),
        ]),
        'layout': ('Layout & puzzles', [
            F('format.profile', 'Paper size', 'Booklets print two pages per side and fold once.', 'select', profiles.choices()),
            F('format.pages', 'Pages', 'The usual (and largest) paper. A multiple of 4.', 'number', step='4'),
            F('format.pages_light', 'Pages on a thin day', '', 'number', step='4'),
            F('format.pages_min', 'Fewest pages', '', 'number', step='4'),
            F('format.deep_dive', 'Deep Dive', 'A two-page story on the centre spread.', 'checkbox'),
            F('format.sections', 'Sections (in page order)', 'Untick to drop a section; the story pages adjust.', 'multi',
              [(k, config.SECTION_LABELS[k]) for k in config.SECTION_NAMES]),
            F('format.shapes', 'Story page shapes', '', 'multi', [('feature', 'Feature (one story)'), ('split', 'Split (two stories)'),
                                                                  ('roundup', 'Roundup (short items)')]),
            F('format.sidebar', 'Page-2 sidebar', 'A short second story under the lead.', 'checkbox'),
            F('format.index_on_front', 'Front-page index', '', 'checkbox'),
            F('format.sky_strip', 'Sun and moon strip under the masthead', '', 'checkbox'),
            F('format.photos', 'Photos', 'Public-domain photos only, printed in grayscale.', 'checkbox'),
            F('format.fill_story', 'Story column fill target (%)', 'QA flags columns that end higher on the page.', 'number'),
            F('format.fill_other', 'Almanac/back fill target (%)', '', 'number'),
            F('puzzles.sudoku_by_weekday', 'Sudoku difficulty by weekday', 'Monday to Sunday.', 'weekdays', LEVELS),
            F('puzzles.sudoku_extra', 'Under the sudoku', '', 'select', [('teasers', 'Two-minute teasers'), ('kenken', 'Mini KenKen'),
                                                                        ('futoshiki', 'Mini futoshiki'), ('none', 'Nothing')]),
            F('puzzles.logic', 'Logic page puzzles', 'Shown when the Logic section is on (up to three).', 'multi',
              [(x, x.capitalize()) for x in config.LOGIC_PUZZLES]),
            F('puzzles.crossword_min', 'Crossword size from', '', 'number'),
            F('puzzles.crossword_max', 'Crossword size to', '', 'number'),
            F('puzzles.scramble_words', 'Scramble words', '', 'number'),
            F('puzzles.teasers', 'Teasers', '', 'number'),
            F('puzzles.cryptogram_source', 'Cryptogram quote', '', 'select',
              [('stories', "A quote from today's stories (else the classics)"), ('corpus', 'Always a classic line')]),
            F('puzzles.custom_quotes', 'Your own cryptogram quotes', 'One per line: quote | who said it.', 'quotes'),
        ]),
        'content': ('Content & filters', [
            F('editorial.favorites', 'Favorite categories', 'About three stories a day come from these.', 'multi', [(c, c) for c in cats]),
            F('editorial.reader_profile', 'About the reader', 'Shapes AI writing and research.', 'textarea'),
            F('editorial.recency_days', 'Recent means (days)', '', 'number'),
            F('editorial.recency_exception_days', 'Never older than (days)', '', 'number'),
            F('editorial.min_categories', 'Categories per paper (at least)', '', 'number'),
            F('editorial.max_same_category', 'Story pages per category (at most)', '', 'number'),
            F('editorial.no_adjacent_same_category', 'Neighbouring pages differ in category', '', 'checkbox'),
            F('editorial.health_max_features', 'Health stories (at most)', '', 'number'),
            F('editorial.favorites_target', 'Stories from favorites', '', 'number'),
            F('editorial.wonders_count', 'Small Wonders (from, to)', '', 'pair'),
            F('editorial.reserve_count', 'Reserve briefs', 'Extra items the fitter can use to close short columns.', 'number'),
            F('editorial.tone_threshold', 'Tone filter', 'Headlines scoring below this (VADER, -1 to 1) are skipped.', 'number', step='0.05'),
            F('editorial.blocklist', 'Blocklist', 'One term per line; * matches any ending. A headline hit skips the story.', 'lines'),
            F('editorial.allowlist', 'Allowed phrases', 'Phrases that override the blocklist (e.g. "dead sea").', 'lines'),
            F('editorial.downweight', 'Score lower', 'Words that make a story less likely to run.', 'lines'),
            F('editorial.upweight', 'Score higher', 'Words that make a story more likely to run.', 'lines'),
            F('editorial.filler_wikipedia', 'Wikipedia filler', '"On this day" and featured-article briefs for short columns.', 'checkbox'),
            F('editorial.classifier', 'Category classifier', 'Learned improves with every paper; embeddings needs the fastembed package.',
              'select', [('keywords', 'Keywords'), ('learned', 'Keywords + learned'), ('embeddings', 'Keywords + learned + embeddings')]),
        ]),
        'schedule': ('Schedule & delivery', [
            F('schedule.build_enabled', 'Make a paper every day', '', 'checkbox'),
            F('schedule.build_time', 'Build time', 'After noon makes the next day\'s paper.', 'time'),
            F('schedule.ship_on_cosmetic_qa', 'Ship when a column falls a little short', 'Overflow and broken QR codes never ship.', 'checkbox'),
            F('schedule.print_enabled', 'Print automatically', '', 'checkbox'),
            F('schedule.weekday_enabled', 'Print on weekdays', '', 'checkbox'),
            F('schedule.weekday_time', 'Weekday print time', '', 'time'),
            F('schedule.weekend_enabled', 'Print on weekends', '', 'checkbox'),
            F('schedule.weekend_time', 'Weekend print time', '', 'time'),
            F('schedule.pause_until', 'Pause printing through', 'Vacation hold; papers are still made.', 'date'),
            F('schedule.missing_policy', "If today's paper isn't ready", '', 'select',
              [('skip', 'Print nothing'), ('latest', 'Print the newest unprinted paper')]),
            F('schedule.keep_days', 'Keep PDFs for (days)', '0 keeps them forever. Content and the ledger are always kept.', 'number'),
            F('printer.cups_server', 'CUPS server', 'host:631, blank for the container\'s own CUPS client default.'),
            F('printer.printer', 'Printer queue', 'Use Find printers.'),
            F('printer.copies', 'Copies', '', 'number'),
            F('printer.sides', 'Sides', 'Blank uses the paper size\'s default.', 'select',
              [('', 'Paper default'), ('two-sided-short-edge', 'Duplex, short edge (booklet)'),
               ('two-sided-long-edge', 'Duplex, long edge'), ('one-sided', 'One-sided')]),
            F('printer.media', 'Paper', 'Blank uses the paper size\'s sheet.', 'select', ['', 'Letter', 'Legal', 'Tabloid', 'A4', 'A3']),
            F('printer.extra_options', 'Extra lp options', 'Space-separated; each becomes -o option.'),
            F('delivery.folder', 'Copy PDFs to folder', 'A path inside the container, e.g. /output.'),
            F('delivery.email.enabled', 'Email each paper', '', 'checkbox'),
            F('delivery.email.smtp_host', 'SMTP server'),
            F('delivery.email.smtp_port', 'SMTP port', '', 'number'),
            F('delivery.email.starttls', 'STARTTLS', '', 'checkbox'),
            F('delivery.email.username', 'SMTP user'),
            F('delivery.email.sender', 'From address'),
            F('delivery.email.to', 'To addresses', 'One per line.', 'lines'),
            F('delivery.email.attach', 'Attach', '', 'select', [('reading', 'Reading PDF'), ('booklet', 'Print booklet'), ('both', 'Both')]),
            F('delivery.remote.enabled', 'Send to another server', 'Another Morning Current or Morning Press push API.', 'checkbox'),
            F('delivery.remote.url', 'Remote push URL', 'e.g. https://news.example.com/api/editions'),
            F('delivery.webhook', 'Webhook URL', 'Receives a JSON summary after each build.'),
        ]),
        'ai': ('AI', [
            F('ai.provider', 'Provider', 'Off makes the paper entirely without AI.', 'select',
              [('none', 'Off'), ('claude', 'Claude (Anthropic API)'), ('openai', 'OpenAI-compatible (Ollama, LM Studio, OpenAI...)')]),
            F('ai.mode', 'Mode', '', 'select', [('rewrite', 'Rewrite: code picks the stories, AI writes them'),
                                                 ('research', 'Research: AI also searches the web for candidates (Claude only)')]),
            F('ai.model', 'Model', 'e.g. claude-sonnet-5-5, claude-haiku-5-5, or a local model name.'),
            F('ai.base_url', 'Endpoint (OpenAI-compatible)', 'e.g. http://ollama:11434/v1'),
            F('ai.max_cost_usd', 'Budget per paper (USD)', 'The build stops using AI when it is spent.', 'number', step='0.05'),
            F('ai.write_stories', 'Write stories', '', 'checkbox'),
            F('ai.write_puzzles', 'Write crossword clues and teasers', '', 'checkbox'),
            F('ai.research_searches', 'Web searches per paper (research mode)', '', 'number'),
            F('ai.temperature', 'Temperature', '', 'number', step='0.1'),
            F('ai.house_style', 'House style', 'Blank uses the built-in style guide (shown as the placeholder).', 'textarea', rows=10),
        ]),
    }


SECRET_FIELDS = {
    'ai': [('anthropic_api_key', 'Anthropic API key'), ('openai_api_key', 'OpenAI-compatible API key')],
    'schedule': [('smtp_password', 'SMTP password'), ('remote_token', 'Remote push token'), ('push_token', 'This server\'s push token')],
}


def get_value(cfg, path):
    v = cfg
    for part in path.split('.'):
        v = getattr(v, part)
    return v


def display(cfg, field):
    v = get_value(cfg, field['path'])
    w = field['widget']
    if w in ('lines',):
        return '\n'.join(v)
    if w == 'quotes':
        return '\n'.join(f'{q.get("quote", "")} | {q.get("who", "")}' for q in v)
    return v


def _set(patch, path, value):
    parts = path.split('.')
    d = patch
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = value


def parse(tab, form):
    """Turn a submitted settings form into a nested config patch."""
    _, fields = tabs()[tab]
    patch = {}
    cfg = config.load()
    for f in fields:
        path, w = f['path'], f['widget']
        cur = get_value(cfg, path)
        if w == 'checkbox':
            _set(patch, path, form.get(path) in ('on', 'true', '1'))
        elif w == 'multi':
            _set(patch, path, form.getlist(path))
        elif w == 'weekdays':
            _set(patch, path, [form.get(f'{path}.{i}', cur[i]) for i in range(7)])
        elif w == 'pair':
            _set(patch, path, [int(form.get(f'{path}.0', cur[0])), int(form.get(f'{path}.1', cur[1]))])
        elif w == 'lines':
            _set(patch, path, [x.strip() for x in form.get(path, '').splitlines() if x.strip()])
        elif w == 'quotes':
            qs = []
            for line in form.get(path, '').splitlines():
                if '|' in line:
                    q, who = line.split('|', 1)
                    if q.strip():
                        qs.append({'quote': q.strip(), 'who': who.strip()})
            _set(patch, path, qs)
        elif path in form:
            raw = form.get(path)
            if isinstance(cur, bool):
                val = raw in ('on', 'true', '1')
            elif isinstance(cur, int) and not isinstance(cur, bool):
                val = int(float(raw)) if raw != '' else cur
            elif isinstance(cur, float):
                val = float(raw) if raw != '' else cur
            else:
                val = raw.strip()
            _set(patch, path, val)
    return patch
