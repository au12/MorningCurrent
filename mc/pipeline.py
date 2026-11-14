"""The nightly job, start to finish:

  1. refresh feeds if the last ingest is stale (and, in AI research mode, let Claude add candidates)
  2. plan the paper from the scored candidates (mc.auto.select)
  3. write it: license-aware assembly (mc.auto.assemble), or AI rewriting when configured (mc.ai.writer)
  4. make puzzle inputs and the Word of the Day (mc.puzzles.auto, optionally improved by AI)
  5. build: layout, fit, PDFs, booklet, QR check, QA (mc.build)
  6. on a blocking QA failure, re-plan once at the light page count
  7. publish the PDFs with the edition, record it in the ledger, mark its articles used, and deliver
"""
import datetime
import json
import os
import time

from . import config, paths, rules as R
from .auto import select
from .edition import save_content
from .ingest import store


def _log_to(path, echo):
    f = open(path, 'a')

    def log(msg):
        line = f'{datetime.datetime.now().strftime("%H:%M:%S")} {msg}'
        f.write(line + '\n')
        f.flush()
        if echo:
            echo(msg)
    return log, f


def ingest_if_stale(log=print, force=False):
    from . import ingest
    cfg = config.load()
    last = store.kv_get('last_ingest') or {}
    try:
        age_h = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(last['at'])).total_seconds() / 3600
    except (KeyError, TypeError, ValueError):
        age_h = 1e9
    if force or age_h > min(cfg.sources.refresh_hours, 6):
        log('fetching feeds...')
        return ingest.run(log=log)
    log(f'feeds fetched {age_h:.1f} h ago; skipping refresh')
    return None


def make_content(date, pages=None, log=print):
    """Plan and write tonight's content (no layout yet). Returns (content, plan)."""
    cfg = config.activate()
    d = datetime.date.fromisoformat(date)
    if cfg.ai.provider != 'none' and cfg.ai.mode == 'research':
        try:
            from .ai import research
            research.add_candidates(d, log=log)
        except Exception as e:  # noqa: BLE001
            log(f'AI research skipped: {e}')
    from . import ingest
    ingest.extract_text(limit=60, log=log)        # full text for the strongest candidates not yet extracted
    ingest.score.rescore_all(log)
    plan = select.plan(pages=pages, log=log)
    content = select.to_content(plan, date, log=log)
    if cfg.ai.provider != 'none' and cfg.ai.write_stories:
        try:
            from .ai import writer
            content = writer.rewrite(content, plan, d, log=log)
        except Exception as e:  # noqa: BLE001
            log(f'AI writing skipped ({type(e).__name__}: {e}); using the automatic versions')
    content = select.finalize_unwritten(content)      # never print a copyrighted article's own text
    from .puzzles import auto
    content['puzzles'] = auto.inputs(content, d, log=log)
    content['meta']['teaser_source'] = 'generated'
    word = auto.word_of_the_day(content, d)
    if word:
        content['almanac']['word'] = word
    if cfg.ai.provider != 'none' and cfg.ai.write_puzzles:
        try:
            from .ai import puzzles as aipz
            aipz.improve(content, d, log=log)
        except Exception as e:  # noqa: BLE001
            log(f'AI puzzle help skipped ({type(e).__name__}: {e})')
    return content, plan


def make(date, build=True, pages=None, deliver=True, log=print, force_ingest=False):
    """The whole nightly job for `date`. Returns a result dict (ok, errors, ...)."""
    cfg = config.activate()
    paths.ensure()
    d = paths.edition_dir(date)
    os.makedirs(d, exist_ok=True)
    log, fh = _log_to(os.path.join(d, 'build.log'), log)
    t0 = time.time()
    try:
        if os.path.exists(os.path.join(d, 'edition.py')):
            raise RuntimeError(f'{date} has a hand-written edition.py; build it with `python -m mc build {date}`')
        ingest_if_stale(log, force=force_ingest)
        for attempt, pg in enumerate([pages, cfg.format.pages_light if not pages else None]):
            if attempt and not pg:
                break
            for name in ('fit.json', 'puzzles.json'):     # stale fit/puzzles would point at other stories
                p = os.path.join(d, name)
                if os.path.exists(p):
                    os.remove(p)
            content, plan = make_content(date, pages=pg, log=log)
            save_content(d, content)
            log(f'wrote {d}/edition.json ({plan.pages} pages, generator {content["meta"]["generator"]})')
            if not build:
                return dict(ok=True, date=date, pages=plan.pages, built=False)
            from .build import build as do_build
            res = do_build(date, log=log, allow_py=False, strict=False)
            res['generator'] = content['meta']['generator']
            if not res['errors']:
                break
            log(f'blocking QA problems: {res["errors"]}')
        shippable = not res['errors'] and (cfg.schedule.ship_on_cosmetic_qa or not res['cosmetic'])
        res['ok'] = shippable
        if shippable:
            from .build import publish, record
            publish(date, res)
            from .ingest.text import plain
            record(date, [plain(t)[:60] for t in _topics(content)], allow_py=False)
            ids = content['meta'].get('items', [])
            con = store.connect()
            for i in ids:
                con.execute("UPDATE items SET status='used', used_in=? WHERE id=?", (date, i))
            con.commit()
            if deliver:
                from . import delivery
                res['delivery'] = delivery.after_build(date, res, log)
        log(f'done in {time.time() - t0:.0f} s: {"shippable" if shippable else "NOT shipped"}')
        return res
    except Exception as e:
        log(f'FAILED: {type(e).__name__}: {e}')
        raise
    finally:
        fh.close()


def _topics(content):
    out = [content['lead']['headline']]
    for u in content.get('units', []):
        if u[0] == 'roundup':
            out.append(u[1]['headline'])
        else:
            out += [s['headline'] for s in u[1:]]
    return out


def preview(date, log=print):
    """Print the top candidates and the plan the planner would make tonight."""
    config.activate()
    rows = select.candidates()
    log(f'{len(rows)} candidates')
    for it in rows[:30]:
        log(f'{it["score"]:.3f} {it["tier"][:4]:4} {it["words"] or 0:5}w {(it["category"] or "")[:24]:24} {it["source"][:20]:20} {it["title"][:70]}')
    try:
        p = select.plan(log=log)
        log(f'\nplan for {date}: {p.pages} pages')
        log(f'  lead:   {p.lead["title"][:80]}')
        if p.sidebar:
            log(f'  sidebar: {p.sidebar["title"][:80]}')
        if p.spread:
            log(f'  spread: {p.spread["title"][:80]}')
        for shape, its in p.units:
            log(f'  {shape:8} ' + ' | '.join(it['title'][:50] for it in its[:3]))
        log(f'  wonders: {len(p.wonders)}, reserve: {len(p.reserve)}')
    except select.PlanError as e:
        log(f'no plan: {e}')
