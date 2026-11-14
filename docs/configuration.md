# Configuration

Everything is set in the web UI (Settings, Sources, Categories) and saved to **`config.yaml`** in the data folder.
Only values that differ from the defaults are written, so improved defaults (keywords, filters, source packs) reach
existing installations when you upgrade. The file can be edited by hand or under Settings > config.yaml; the whole file
is validated before it is saved. [examples/config.example.yaml](../examples/config.example.yaml) shows a typical one.

Secrets never go in `config.yaml`. They come from environment variables first, then from `secrets.json` (mode 0600)
when entered in the UI:

| Secret | Environment variable |
| --- | --- |
| Admin password | `ADMIN_PASSWORD` |
| Anthropic API key | `ANTHROPIC_API_KEY` |
| OpenAI-compatible API key | `OPENAI_API_KEY` |
| SMTP password | `SMTP_PASSWORD` |
| Token for pushing to another server | `REMOTE_TOKEN` |
| This server's API token | `PUSH_TOKEN` |
| Session cookie key (generated) | `SESSION_SECRET` |

## The data folder

`/data` in the container; otherwise `$MC_DATA`, else the current directory if it holds `config.yaml`, else `./data`.

```
config.yaml              settings
secrets.json             keys and passwords entered in the UI
mc.db                    article database: feeds, candidates, your votes and corrections
activity.jsonl           the press room's activity log
editions/ledger.json     every paper: number, stories, URLs and titles (so nothing repeats)
editions/<date>/         edition.json (content), puzzles.json, fit.json, meta.json, qa.json, build.log,
                         booklet.pdf (imposed for printing), reading.pdf (pages in order)
out/<date>/              build scratch: HTML, contact sheets, QR renders (pruned with old PDFs)
cache/                   images and robots.txt
```

Back up `config.yaml`, `secrets.json`, `mc.db` and `editions/`. PDFs older than *Keep PDFs for* days are deleted;
content and the ledger are kept.

## Sections of config.yaml

**`paper`**: `title`, `tagline`, `volume` (printed as "Vol. I"), `household`, `about` (back-page text; blank = generated).

**`location`**: `name`, `lat`, `lon` (west negative), `elevation` (m), `tz` (IANA name; every schedule and printed time
uses it), `note` (printed under the almanac's times).

**`format`**: `profile` (`legal-booklet`, `letter-booklet`, `a4-booklet`, `tabloid-booklet`, `letter-flat`, `a4-flat`),
`pages`, `pages_light` (thin days), `pages_min` (all multiples of 4), `deep_dive` (two-page centre story), `sections`
(in page order, from `wonders`, `almanac`, `word`, `sudoku`, `xword`, `logic`, `back`), `shapes` (`feature`, `split`,
`roundup`), `sidebar`, `index_on_front`, `sky_strip`, `photos`, `clock` (`24h`/`12h`), `units`, `fill_story` and
`fill_other` (the column fill QA expects, %).

A paper has the front page, page 2 (the lead's continuation), one page per section, the Deep Dive's two pages, and
single story pages for the rest. The settings page refuses a combination that doesn't fit.

**`puzzles`**: `sudoku_by_weekday` (seven of `easy`, `easy+`, `easy-medium`, `medium`, `medium+`), `sudoku_extra`
(`teasers`, `kenken`, `futoshiki` or `none` under the sudoku), `logic` (up to three of `kenken`, `futoshiki`,
`wordsearch`, `nonogram`, `kakuro` for the logic page), `crossword_min`/`crossword_max` (grid size), `scramble_words`,
`teasers`, `cryptogram_source` (`stories`: a verified quote from today's sources, else the classics; `corpus`),
`custom_quotes` (a list of `{quote, who}`).

**`editorial`**: `categories` (each with `name`, `family` of `science`/`health`/`tech`/`culture`, `keywords`, `weight`,
`favorite`, `enabled`, `cap`), `favorites`, `recency_days`, `recency_exception_days`, `min_categories`,
`max_same_category`, `no_adjacent_same_category`, `favorites_target`, `health_max_features`, `blocklist`, `allowlist`,
`downweight`, `upweight` (word lists; `*` matches any ending), `tone_threshold` (VADER compound score, -1 to 1),
`wonders_count`, `reserve_count`, `filler_wikipedia`, `reader_profile` (for AI), `classifier` (`keywords`, `learned`,
`embeddings`; embeddings need `pip install fastembed`, which the image does not include).

**`sources`**: `feeds` (see [sources-and-licensing.md](sources-and-licensing.md)), `refresh_hours`, `user_agent`,
`respect_robots`, `per_host_delay`, `timeout`, `keep_days` (how long fetched articles stay in the database).

**`schedule`**: `build_enabled`, `build_time` (after noon makes the next day's paper), `print_enabled`,
`weekday_enabled`/`weekday_time`, `weekend_enabled`/`weekend_time`, `pause_until` (a date: vacation hold),
`missing_policy` (`skip`, or `latest` to print the newest unprinted paper), `keep_days`, `ship_on_cosmetic_qa`.

**`printer`**: `cups_server` (`host:631`; blank uses `CUPS_SERVER` or the client default), `printer` (queue name),
`copies`, `sides` and `media` (blank = the paper size's defaults), `extra_options` (each becomes `lp -o`).

**`delivery`**: `folder` (copy PDFs to a path inside the container, e.g. a mounted `/output`), `email` (`enabled`,
`smtp_host`, `smtp_port`, `starttls`, `username`, `sender`, `to`, `attach`: `reading`, `booklet` or `both`), `remote`
(`enabled`, `url`: another Morning Current or Morning Press `/api/editions`), `webhook` (receives a JSON summary).

**`ai`**: see [ai.md](ai.md).

**`web`**: `public_reader` (anyone can read `/read` and `/archive`), `public_feedback` (anyone can vote), `base_url`.
