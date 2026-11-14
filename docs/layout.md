# Layout reference

The layout engine turns one edition's content into a finished, checked booklet. Layout, numbering, the almanac and the
puzzles are produced by code; [`mc/rules.py`](../mc/rules.py) holds the format constants, filled from `config.yaml` by
`config.activate()`. The automatic pipeline (`python -m mc make`) writes the content itself; the original household
paper's editions were written by hand (by a Claude Code routine) and built with the same code.

## Layout

```
mc/
  rules.py               format and editorial constants (geometry, type, fill targets, categories, sudoku levels...)
  config.py, profiles.py settings model and paper sizes; rules are derived from them
  paper.typ              the paper's styles and page parts as a Typst library (the type scale and geometry come from
                         the active paper profile, prepended by style.py)
  style.py               the Typst preamble: profile parameters + paper.typ
  ty.py                  inline HTML in edition text -> Typst code (text is always passed as string literals)
  components.py          QR/source boxes, heads, blocks, briefs, fact boxes, charts (bars, timeline, flow, checklist, svg), as Typst code
  templates.py           page templates: front, cont, feature, split, spread L/R, roundup, Small Wonders, almanac, games, logic, back
  almanac.py             PyEphem: sun/moon tables, phases, DST, ranked sky calendar, look-up box
  puzzles/               graded sudoku, cryptogram, scramble, ladder, crossword library + filler + checks (__init__),
                         logic puzzles (extra.py), daily puzzle inputs from the stories (auto.py)
  edition.py             loads an edition (edition.json, or a legacy edition.py), plans the pages, writes the Typst source
  measure.py             compiles with Typst, reads back marker positions: per-column fill, hidden lines, the PDF
  build.py               fit loop, PDFs, imposition, QR verification, contact sheets, QA, ledger, publish, deliver
  pipeline.py            the nightly job: ingest, plan, write, puzzles, build, publish, deliver
  template_edition.py    documented skeleton for a hand-written edition.py
  data/                  fonts, categories, source packs, crossword patterns, ban list, quote corpus, edition template
<data>/editions/
  ledger.json            every edition's date, number, pages, URLs used and topics
  <date>/edition.json    that edition's content (or edition.py for hand-written ones)
  <date>/puzzles.json    that edition's puzzles and answers (the next paper prints the answers)
  <date>/fit.json        where the fitter settled (re-builds start from it)
<data>/out/<date>/       build outputs (edition.typ, reading.pdf, booklet.pdf, contact sheets, qa.json)
```

## Commands

```bash
python3 -m mc make 2026-11-16            # the automatic nightly job for one date
python3 -m mc new 2026-11-16 [--json]    # start a hand-written edition from the template
python3 -m mc sky 2026-11-16             # preview the computed sky calendar
python3 -m mc ladder BEAN BREW           # find a word ladder
python3 -m mc crossword 2026-11-16       # pattern unlike the last five editions'; prints candidate fills
python3 -m mc build 2026-11-16           # layout, fit, PDFs, QA; exit 0 only when QA passes
python3 -m mc record 2026-11-16 "topic; topic; ..."
PRESS_TOKEN=... python3 -m mc deliver 2026-11-16
python3 -m mc convert all                # turn edition.py files into edition.json
```

## The edition file

It holds content only. The fields are documented in `mc/template_edition.py`:

- `LEAD`, with `cont_head`; optional `SIDEBAR`.
- `UNITS`: an ordered list of `('feature', S)`, `('split', A, B)` and one `('spread', S)`.
- `WONDERS` and `WONDERS_DECK`; `RESERVE` briefs; `ALMANAC` (word, extra rows, sky-guide source); `PUZZLES` (cryptogram, scramble, ladder, teasers, crossword grid plus clues).

A story is a dict with `id`, `category` (from `rules.CATEGORIES`), `kicker`, `headline`, `deck`, `src=(url, label, note)`, optional `more`, `teaser`, `briefs` and `also`, and `blocks`. Block types are `dropcap`, `p`, `h4`, `quote`, `chart`, `facts`, plus `jump` (lead) and `turn` (spread) as starting points the fitter adjusts. Charts are data, never hand-placed SVG, so every edition shares one look. The `svg` kind is the escape hatch for a one-off explainer diagram.

`{p:id}` anywhere (text, clues, teasers, almanac rows) resolves to that story's page. The spread resolves to "8–9".

## What the build does

1. **Puzzles.** Sudoku is graded to the weekday's level. The cryptogram, scramble and ladder are verified. The crossword is checked against the previous edition's pattern and every answer must have a clue.
2. **Plan.** The spread goes on the centre pair, then the fixed tail. Running heads come from categories, the front index from stories with a `teaser`, and the back-page sources are grouped by page.
3. **Fit loop.** The build renders and measures every column, then adjusts. It moves the lead's jump and the spread's turn, adds reserve briefs (same category first) under short columns, removes any brief that causes overflow, and sizes the sky calendar, look-up box and note lines. It stops when stable.
4. **Outputs.** The reading PDF and the booklet (sheet s: front (N−2s, 1+2s), back (2+2s, N−1−2s)). QR codes are decoded at 300 dpi, contact sheets are made, `qa.json` is written, and `puzzles.json` and `fit.json` are saved.
5. **QA.** It lists failures and warnings (spec §6). Anything the fitter couldn't fix, usually overflow or a short column with no reserve left, is for the writer: trim or add copy, then rebuild.

## How measuring works

Each column region is a fixed-height `region(...)` in `mc/paper.typ`; content that does not fit runs past its bottom edge
instead of starting a new page, so every logical page stays one page. Invisible markers (`mk`) sit at the start of each
page, the top and bottom of each region and the start and end of every block. `mc/measure.py` compiles the edition,
queries the markers' positions and reports, per region, how far down each column's content reaches and how many lines
run past the bottom; the fitter in `mc/build.py` acts on that report. The edition source is kept as `out/<date>/edition.typ`;
it compiles on its own with the [Typst CLI](https://github.com/typst/typst) (`typst compile --font-path mc/data/fonts/ttf --root / edition.typ`).

Fonts: Typst reads the TTF copies in `mc/data/fonts/ttf/`, made from the bundled web fonts by `scripts/make_fonts.py`.
