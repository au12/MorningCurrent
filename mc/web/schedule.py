"""The clock: fetch feeds every few hours, make the paper at the build time, print it at the weekday and
weekend times, and tidy up old editions. Runs inside the web server process (APScheduler)."""
import datetime
import os
import shutil

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .. import config, delivery, paths, rules as R
from . import state

scheduler = None


def _tz():
    from zoneinfo import ZoneInfo
    return ZoneInfo(config.load().location.tz)


def edition_date_for_build(cfg=None):
    """A build in the evening makes tomorrow's paper; after midnight, today's."""
    cfg = cfg or config.load()
    h = int(cfg.schedule.build_time.split(':')[0])
    d = state.today()
    return (d + datetime.timedelta(days=1)) if h >= 12 else d


def run_build(date=None, trigger='schedule'):
    date = date or edition_date_for_build().isoformat()

    def done(job):
        m = state.read_meta(date)
        qa = m.get('qa') or {}
        ok = job.code == 0
        state.activity('build', f'Edition {date} ' + ('built' if ok else 'not shipped') +
                       (f': {m.get("lead", "")}' if ok else f' (see the build log)'), ok=ok, trigger=trigger)
    job, started = state.start('make', ['make', date], f'Make the {date} paper', on_done=done)
    if started:
        state.activity('build', f'Started the {date} edition ({trigger})')
    return job, started


def run_ingest(trigger='schedule'):
    def done(job):
        state.activity('ingest', 'Fetched feeds' if job.code == 0 else 'Feed fetch failed', ok=job.code == 0, trigger=trigger)
    return state.start('ingest', ['ingest'], 'Fetch feeds', on_done=done)


def print_edition(d, trigger):
    cfg = config.load()
    f = state.pdf(d)
    if not os.path.exists(f):
        state.activity('print', f'No edition for {d}', ok=False, trigger=trigger)
        return False, f'no edition for {d}'
    ok, out, job = delivery.print_pdf(f, f'{R.TITLE} {d}', cfg)
    m = state.read_meta(d)
    m.setdefault('prints', []).append({'at': state.now().isoformat(timespec='seconds'), 'trigger': trigger, 'ok': ok, 'job': job})
    state.write_meta(d, m)
    state.activity('print', f'Edition {d} → {cfg.printer.printer or "?"}: {out or "no output"}', ok=ok, trigger=trigger)
    return ok, out


def scheduled_print(kind):
    cfg = config.load()
    s = cfg.schedule
    t = state.today()
    if not s.print_enabled:
        return
    if s.pause_until:
        try:
            if t <= datetime.date.fromisoformat(s.pause_until):
                state.activity('schedule', f'Skipped {kind} print: paused through {s.pause_until}')
                return
        except ValueError:
            pass
    d = t.isoformat()
    if os.path.exists(state.pdf(d)):
        if any(p.get('ok') and p.get('trigger') == 'schedule' for p in state.read_meta(d).get('prints', [])):
            state.activity('schedule', f'Edition {d} already printed today; skipping')
            return
        print_edition(d, 'schedule')
        return
    if s.missing_policy == 'latest':
        for e in state.list_editions():
            if e['has_booklet'] and not any(p.get('ok') for p in e['prints']):
                state.activity('schedule', f"Today's edition missing; printing the newest unprinted ({e['date']})", ok=False)
                print_edition(e['date'], 'schedule')
                return
    state.activity('schedule', f"Today's edition ({d}) isn't ready; nothing printed", ok=False)


def cleanup():
    keep = config.load().schedule.keep_days
    if keep <= 0:
        return
    cutoff = state.today() - datetime.timedelta(days=keep)
    removed = 0
    for e in state.list_editions():
        try:
            if datetime.date.fromisoformat(e['date']) < cutoff:
                d = paths.edition_dir(e['date'])
                for name in ('booklet.pdf', 'reading.pdf'):
                    p = os.path.join(d, name)
                    if os.path.exists(p):
                        os.remove(p)
                shutil.rmtree(paths.out_dir(e['date']), ignore_errors=True)
                removed += 1
        except ValueError:
            continue
    if removed:
        state.activity('cleanup', f'Removed PDFs of {removed} edition(s) older than {keep} days (content and ledger kept)')


def apply():
    """(Re)create every job from the current settings."""
    global scheduler
    cfg = config.load()
    tz = _tz()
    if scheduler is None or not scheduler.running:
        scheduler = BackgroundScheduler(timezone=tz)
        scheduler.start()
    for j in list(scheduler.get_jobs()):
        j.remove()
    scheduler.add_job(cleanup, CronTrigger(hour=3, minute=17, timezone=tz), id='cleanup')
    if any(s.enabled for s in cfg.sources.feeds):
        scheduler.add_job(run_ingest, IntervalTrigger(hours=max(1, cfg.sources.refresh_hours), timezone=tz), id='ingest',
                          coalesce=True, max_instances=1, misfire_grace_time=3600)
    if cfg.schedule.build_enabled and cfg.setup_complete:
        h, m = (int(x) for x in cfg.schedule.build_time.split(':'))
        scheduler.add_job(run_build, CronTrigger(hour=h, minute=m, timezone=tz), id='build', coalesce=True, max_instances=1,
                          misfire_grace_time=3 * 3600)
    if cfg.schedule.print_enabled:
        for jid, days, on, hhmm in (('print-weekday', 'mon-fri', cfg.schedule.weekday_enabled, cfg.schedule.weekday_time),
                                    ('print-weekend', 'sat,sun', cfg.schedule.weekend_enabled, cfg.schedule.weekend_time)):
            if on:
                h, m = (int(x) for x in hhmm.split(':'))
                scheduler.add_job(scheduled_print, CronTrigger(day_of_week=days, hour=h, minute=m, timezone=tz), id=jid,
                                  args=[jid], coalesce=True, max_instances=1, misfire_grace_time=1800)


def next_runs():
    if scheduler is None:
        return []
    out = []
    for j in scheduler.get_jobs():
        if j.next_run_time and j.id != 'cleanup':
            out.append(dict(id=j.id, at=j.next_run_time))
    return sorted(out, key=lambda x: x['at'])


def shutdown():
    global scheduler
    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=False)
    scheduler = None
