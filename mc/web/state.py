"""Shared server state: the activity log, edition metadata and background jobs."""
import datetime
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid

from .. import config, paths

_lock = threading.RLock()
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def now():
    from zoneinfo import ZoneInfo
    return datetime.datetime.now(ZoneInfo(config.load().location.tz))


def today():
    return now().date()


# ------------------------------------------------------------------ activity log
def activity(kind, msg, ok=True, **extra):
    entry = {'at': now().isoformat(timespec='seconds'), 'kind': kind, 'ok': ok, 'msg': msg, **extra}
    with _lock:
        p = paths.activity_file()
        lines = open(p).read().splitlines() if os.path.exists(p) else []
        lines.append(json.dumps(entry))
        with open(p, 'w') as f:
            f.write('\n'.join(lines[-800:]) + '\n')
    print(f'[{kind}] {msg}', flush=True)


def read_activity(n=50):
    p = paths.activity_file()
    if not os.path.exists(p):
        return []
    out = []
    for line in open(p).read().splitlines()[-n:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return list(reversed(out))


# ------------------------------------------------------------------ editions
def meta_path(d):
    return os.path.join(paths.edition_dir(d), 'meta.json')


def read_meta(d):
    p = meta_path(d)
    if os.path.exists(p):
        try:
            return json.load(open(p))
        except json.JSONDecodeError:
            return {}
    return {}


def write_meta(d, m):
    with _lock:
        os.makedirs(paths.edition_dir(d), exist_ok=True)
        tmp = meta_path(d) + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(m, f, indent=1)
        os.replace(tmp, meta_path(d))


def pdf(d, kind='booklet'):
    return os.path.join(paths.edition_dir(d), f'{kind}.pdf')


def list_editions():
    root = paths.editions_dir()
    out = []
    if not os.path.isdir(root):
        return out
    for d in sorted(os.listdir(root), reverse=True):
        if not DATE_RE.match(d):
            continue
        has_b, has_r = os.path.exists(pdf(d)), os.path.exists(pdf(d, 'reading'))
        has_c = any(os.path.exists(os.path.join(root, d, f)) for f in ('edition.json', 'edition.py'))
        if not (has_b or has_r or has_c):
            continue
        m = read_meta(d)
        qa = m.get('qa') or {}
        out.append(dict(date=d, title=m.get('title', ''), pages=m.get('reading_pages') or m.get('pages'), sheet_sides=m.get('pages'),
                        lead=m.get('lead', ''),
                        uploaded_at=m.get('uploaded_at'), prints=m.get('prints', []), has_booklet=has_b, has_reading=has_r,
                        has_content=has_c, source=m.get('source', ''), errors=len(qa.get('errors', [])),
                        cosmetic=len(qa.get('cosmetic', [])), warnings=len(qa.get('warnings', [])),
                        size_kb=round(os.path.getsize(pdf(d)) / 1024) if has_b else 0))
    return out


# ------------------------------------------------------------------ background jobs
_jobs = {}


class Job:
    def __init__(self, kind, args, label):
        self.id = uuid.uuid4().hex[:10]
        self.kind, self.args, self.label = kind, args, label
        self.status, self.started, self.finished, self.code = 'queued', None, None, None
        os.makedirs(paths.jobs_dir(), exist_ok=True)
        self.log = os.path.join(paths.jobs_dir(), f'{self.id}.log')

    def as_dict(self):
        tail = ''
        if os.path.exists(self.log):
            with open(self.log, errors='replace') as f:
                tail = ''.join(f.readlines()[-60:])
        return dict(id=self.id, kind=self.kind, label=self.label, status=self.status, started=self.started,
                    finished=self.finished, code=self.code, log=tail)


def running(kind=None):
    return [j for j in _jobs.values() if j.status in ('queued', 'running') and (kind is None or j.kind == kind)]


def start(kind, args, label, on_done=None):
    """Run `python -m mc <args>` in the background. One job of each kind at a time; builds and
    ingests never overlap (a build fetches feeds itself)."""
    clash = running(kind) or (running('make') if kind == 'ingest' else []) or (running('ingest') if kind == 'make' else [])
    if clash:
        return clash[0], False
    j = Job(kind, args, label)
    _jobs[j.id] = j

    def run():
        j.status, j.started = 'running', now().isoformat(timespec='seconds')
        env = dict(os.environ, MC_DATA=paths.data_dir(), PYTHONUNBUFFERED='1')
        with open(j.log, 'w') as f:
            p = subprocess.Popen([sys.executable, '-m', 'mc'] + args, stdout=f, stderr=subprocess.STDOUT, env=env,
                                 cwd=paths.REPO)
            j.code = p.wait()
        j.status = 'done' if j.code == 0 else 'failed'
        j.finished = now().isoformat(timespec='seconds')
        if on_done:
            try:
                on_done(j)
            except Exception as e:  # noqa: BLE001
                activity('job', f'{label}: follow-up failed: {e}', ok=False)
    threading.Thread(target=run, daemon=True).start()
    return j, True


def get_job(jid):
    return _jobs.get(jid)


def recent_jobs(n=8):
    return sorted(_jobs.values(), key=lambda j: j.started or '', reverse=True)[:n]
