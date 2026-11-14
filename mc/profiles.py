"""Paper profiles: page size, sheet, margins, type scale and fixed element sizes.

A *booklet* profile prints two pages side by side on each side of a sheet, duplexed on the short
edge; folding the stack once makes a saddle-stapled booklet. A *flat* profile prints pages as they
are (one page per side), for printers or readers that don't want to fold.

Every size here is in inches or points. rules.apply() copies the chosen profile into rules.
"""
import copy

_LEGAL_BOOKLET = dict(
    label='Legal sheets, folded (7 x 8.5 in pages)',
    page_w=7.0, page_h=8.5, booklet=True, sheet='Legal', sheet_w=14.0, sheet_h=8.5, sides='two-sided-short-edge',
    margin=dict(inner=0.58, outer=0.42, top=0.62, top_front=0.38, bottom=0.52, rhead=0.34, folio=0.26),
    col_gap=0.19, body_pt=9.1, leading=1.31, body_min=8.8,
    type=dict(title=40, h1=27, h2=21, h3=15, h3_split=16, deck=10.6, deck_split=9.6, kicker=7, h4=7.4,
              brief_head=7.2, brief=8.8, odd_head=11.5, src=6.7, chart_title=6.8, chart_note=6.0, skystrip=6.6,
              pull=13, ptitle=16),
    qr=dict(size='0.54in', inline='0.46in', inline_long='0.56in', long_url=90),
    sudoku_cell=0.5, xword_cell=0.31, ladder_cell=0.3, logic_cell=0.42, index_cols=4, teaser_cols=3,
)

_LETTER_BOOKLET = dict(
    label='Letter sheets, folded (5.5 x 8.5 in pages)',
    page_w=5.5, page_h=8.5, booklet=True, sheet='Letter', sheet_w=11.0, sheet_h=8.5, sides='two-sided-short-edge',
    margin=dict(inner=0.5, outer=0.36, top=0.56, top_front=0.34, bottom=0.48, rhead=0.3, folio=0.23),
    col_gap=0.16, body_pt=8.6, leading=1.3, body_min=8.2,
    type=dict(title=34, h1=21, h2=17, h3=12.6, h3_split=13.2, deck=9.4, deck_split=8.8, kicker=6.4, h4=6.8,
              brief_head=6.6, brief=8.2, odd_head=10, src=6.2, chart_title=6.2, chart_note=5.6, skystrip=5.4,
              pull=11.5, ptitle=13.5),
    qr=dict(size='0.5in', inline='0.44in', inline_long='0.54in', long_url=90),
    sudoku_cell=0.45, xword_cell=0.28, ladder_cell=0.27, logic_cell=0.36, index_cols=2, teaser_cols=1,
)

_A4_BOOKLET = dict(_LETTER_BOOKLET, label='A4 sheets, folded (A5 pages)', page_w=5.83, page_h=8.27, sheet='A4',
                   sheet_w=11.69, sheet_h=8.27)

_TABLOID_BOOKLET = dict(
    label='Tabloid (11 x 17 in) sheets, folded (8.5 x 11 in pages)',
    page_w=8.5, page_h=11.0, booklet=True, sheet='Tabloid', sheet_w=17.0, sheet_h=11.0, sides='two-sided-short-edge',
    margin=dict(inner=0.7, outer=0.55, top=0.75, top_front=0.45, bottom=0.62, rhead=0.42, folio=0.32),
    col_gap=0.24, body_pt=9.6, leading=1.32, body_min=9.0,
    type=dict(title=50, h1=32, h2=25, h3=17, h3_split=18, deck=11.6, deck_split=10.4, kicker=7.6, h4=8,
              brief_head=7.8, brief=9.2, odd_head=12.5, src=7.2, chart_title=7.2, chart_note=6.4, skystrip=7.2,
              pull=15, ptitle=18),
    qr=dict(size='0.6in', inline='0.5in', inline_long='0.6in', long_url=90),
    sudoku_cell=0.6, xword_cell=0.36, ladder_cell=0.34, logic_cell=0.5, index_cols=4, teaser_cols=3,
)

_LETTER_FLAT = dict(_TABLOID_BOOKLET, label='Letter pages, not folded (8.5 x 11 in)', booklet=False, sheet='Letter',
                    sheet_w=8.5, sheet_h=11.0, sides='two-sided-long-edge')

_A4_FLAT = dict(_TABLOID_BOOKLET, label='A4 pages, not folded', page_w=8.27, page_h=11.69, booklet=False, sheet='A4',
                sheet_w=8.27, sheet_h=11.69, sides='two-sided-long-edge')

PROFILES = {
    'legal-booklet': _LEGAL_BOOKLET,
    'letter-booklet': _LETTER_BOOKLET,
    'a4-booklet': _A4_BOOKLET,
    'tabloid-booklet': _TABLOID_BOOKLET,
    'letter-flat': _LETTER_FLAT,
    'a4-flat': _A4_FLAT,
}
DEFAULT = 'legal-booklet'


def get(name):
    """A deep copy of the named profile (unknown names fall back to the default)."""
    return copy.deepcopy(PROFILES.get(name) or PROFILES[DEFAULT])


def choices():
    return [(k, v['label']) for k, v in PROFILES.items()]


def column_width_in(p, one_column=False):
    inner = p['page_w'] - p['margin']['inner'] - p['margin']['outer']
    return inner if one_column else (inner - p['col_gap']) / 2


def words_per_column(p, height_in=None):
    """Rough body-text capacity of one full-height column (used to pick stories of the right length)."""
    h = height_in if height_in is not None else p['page_h'] - p['margin']['top'] - p['margin']['bottom']
    lines = h * 72 / (p['body_pt'] * p['leading'])
    chars = column_width_in(p) * 72 / (p['body_pt'] * 0.468)
    return int(lines * chars / 6.1 * 0.76)     # 0.76: calibrated on printed editions (leading, justification, hyphens)


def budgets(p):
    """Target body-text word counts for each story slot of a profile (before charts and briefs)."""
    w = words_per_column(p)
    return dict(column=w, split=int(0.74 * w), feature=int(1.62 * w), lead=int(2.45 * w), sidebar=int(0.4 * w),
                spread=int(3.2 * w), brief=60, wonder=65)
