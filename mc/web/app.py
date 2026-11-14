"""The Morning Current web app (FastAPI).

Public:  /read (latest edition in a page-turning viewer), /read/<date>, /archive, /healthz
Admin:   /admin (press room), /admin/setup (first-run wizard), /admin/settings/<tab>, /admin/sources,
         /admin/categories, /admin/desk (editor's desk), /admin/editions/<date>, /admin/yaml
API:     POST /api/editions (push a finished edition; compatible with Morning Press), GET /api/editions,
         GET /api/editions/<date>/data, GET /api/status, POST /api/build, POST /api/ingest
         (bearer token: PUSH_TOKEN)
"""
from __future__ import annotations

import datetime
import hmac
import io
import json
import mimetypes
import os
import re
import shlex
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .. import __version__, config, delivery, paths, profiles, secrets
from . import forms, migrate, schedule, state

HERE = Path(__file__).parent
MAX_UPLOAD = int(os.environ.get('MAX_UPLOAD_MB', '50')) * 1024 * 1024

paths.ensure()
try:
    migrate.run(lambda m: print('[migrate]', m))
except Exception as e:  # noqa: BLE001
    print('[migrate] skipped:', e)
config.activate()



@asynccontextmanager
async def lifespan(_app):
    admin_password()
    schedule.apply()
    state.activity('system', f'The Morning Current {__version__} started')
    yield
    schedule.shutdown()


app = FastAPI(title='The Morning Current', docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=secrets.ensure('session_secret', 32), session_cookie='mc_session',
                   max_age=60 * 60 * 24 * 30, same_site='lax', https_only=os.environ.get('COOKIE_SECURE', 'false').lower() == 'true')
templates = Jinja2Templates(directory=str(HERE / 'templates'))
mimetypes.add_type('text/javascript', '.mjs')
app.mount('/static', StaticFiles(directory=str(HERE / 'static')), name='static')
app.mount('/fonts', StaticFiles(directory=str(Path(paths.BUNDLED) / 'fonts')), name='fonts')


def cfg():
    return config.activate()


def admin_password():
    pw = secrets.get('admin_password')
    if not pw:
        pw = secrets.ensure('admin_password', 12)
        print(f'[auth] ADMIN_PASSWORD not set; generated one and stored it in {paths.secrets_file()}: {pw}', flush=True)
    return pw


# ------------------------------------------------------------------ helpers
def is_admin(request):
    return bool(request.session.get('admin'))


def guard(request):
    if not is_admin(request):
        return RedirectResponse('/login?next=' + request.url.path, status_code=303)
    return None


def flash(request, msg, ok=True):
    request.session['flash'] = {'msg': msg, 'ok': ok}


def check_date(d):
    if not state.DATE_RE.match(d or ''):
        raise HTTPException(400, 'date must be YYYY-MM-DD')
    try:
        datetime.date.fromisoformat(d)
    except ValueError:
        raise HTTPException(400, 'invalid date')
    return d


def render(request, name, **ctx):
    c = cfg()
    ctx.update(request=request, cfg=c, flash=request.session.pop('flash', None), admin=is_admin(request), version=__version__,
               now=state.now())
    return templates.TemplateResponse(request, name, ctx)


def require_token(request):
    tok = secrets.get('push_token')
    if not tok:
        raise HTTPException(503, 'push API disabled: set PUSH_TOKEN (or a push token in Settings > Schedule & delivery)')
    got = request.headers.get('authorization', '')
    if not hmac.compare_digest(got.encode(), f'Bearer {tok}'.encode()):
        raise HTTPException(401, 'bad or missing bearer token')


# ------------------------------------------------------------------ public
@app.get('/healthz')
def healthz():
    return {'ok': True, 'version': __version__}


@app.get('/favicon.ico')
def favicon():
    return FileResponse(HERE / 'static' / 'favicon.ico', headers={'Cache-Control': 'public, max-age=86400'})


@app.get('/manifest.webmanifest')
def manifest():
    c = cfg()
    return JSONResponse({'name': c.paper.title, 'short_name': c.paper.title.replace('The ', '')[:24], 'start_url': '/read',
                         'display': 'standalone', 'background_color': '#e6e1d6', 'theme_color': '#1b1916',
                         'icons': [{'src': '/static/icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
                                   {'src': '/static/icon-512.png', 'sizes': '512x512', 'type': 'image/png'}]},
                        media_type='application/manifest+json')


@app.get('/')
def home(request: Request):
    c = cfg()
    if is_admin(request):
        return RedirectResponse('/admin' if c.setup_complete else '/admin/setup', status_code=303)
    if not c.setup_complete:
        return RedirectResponse('/login?next=/admin/setup', status_code=303)
    return RedirectResponse('/read', status_code=303)


def reading_editions():
    out = []
    for e in state.list_editions():
        if e['has_reading']:
            dt = datetime.date.fromisoformat(e['date'])
            m = state.read_meta(e['date'])
            out.append(dict(e, pretty=f'{dt:%A, %B} {dt.day}, {dt.year}', short=f'{dt:%a, %b} {dt.day}',
                            reading_pages=m.get('reading_pages')))
    return out


def reader_allowed(request):
    return cfg().web.public_reader or is_admin(request)


@app.get('/read')
def read_latest(request: Request):
    if not reader_allowed(request):
        return guard(request)
    eds = reading_editions()
    if not eds:
        return render(request, 'archive.html', editions=[])
    return RedirectResponse(f'/read/{eds[0]["date"]}', status_code=307)


@app.get('/read/{d}.pdf')
def read_pdf(request: Request, d: str):
    if not reader_allowed(request):
        raise HTTPException(401)
    check_date(d)
    f = state.pdf(d, 'reading')
    if not os.path.exists(f):
        raise HTTPException(404, 'no reading version for that date')
    return FileResponse(f, media_type='application/pdf', filename=f'{_slug(cfg().paper.title)}-{d}.pdf',
                        content_disposition_type='inline', headers={'Cache-Control': 'public, max-age=600'})


def _slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def edition_stories(d):
    """Stories and briefs of an edition with their pages (for the reader's story list and feedback)."""
    p = os.path.join(paths.edition_dir(d), 'edition.json')
    if not os.path.exists(p):
        return []
    try:
        from ..edition import Edition
        ed = Edition(d, allow_py=False)
    except Exception:  # noqa: BLE001
        return []
    from ..ingest.text import plain
    out = []
    for s in ed.stories():
        out.append(dict(id=s['id'], headline=plain(s['headline']), category=s.get('category'), page=str(ed.page_of.get(s['id'], '')).replace('&ndash;', '–'),
                        url=s['src'][0] if isinstance(s['src'], list) else s['src'], source=s.get('source') or ''))
    for r in ed.roundups():
        for i in ed.items_of(r):
            out.append(dict(id=f'{r["id"]}:{i.get("item_id", "")}', headline=plain(i['head']), category=i.get('category'),
                            page=str(ed.page_of.get(r['id'], '')), url=i['src'], source=i.get('source') or ''))
    for w in ed.printed_wonders():
        out.append(dict(id=f'w:{w.get("item_id", w["head"][:20])}', headline=plain(w['head']), category=w.get('category'),
                        page=str(ed.page_of.get('wonders', '')), url=w['src'], source=w.get('source') or ''))
    return out


@app.get('/read/{d}', response_class=HTMLResponse)
def read_edition(request: Request, d: str):
    if not reader_allowed(request):
        return guard(request)
    check_date(d)
    eds = reading_editions()
    idx = next((i for i, e in enumerate(eds) if e['date'] == d), None)
    if idx is None:
        raise HTTPException(404, 'no reading version for that date')
    from ..ingest import store
    votes = {v['story_id']: v['vote'] for v in store.votes() if v['edition'] == d}
    return render(request, 'reader.html', e=eds[idx], newer=eds[idx - 1] if idx > 0 else None,
                  older=eds[idx + 1] if idx + 1 < len(eds) else None, stories=edition_stories(d), votes=votes,
                  can_vote=is_admin(request) or cfg().web.public_feedback)


@app.post('/read/{d}/vote')
def vote(request: Request, d: str, story: str = Form(...), value: int = Form(...)):
    if not (is_admin(request) or cfg().web.public_feedback):
        raise HTTPException(401, 'sign in to vote')
    check_date(d)
    s = next((x for x in edition_stories(d) if x['id'] == story), None)
    if not s:
        raise HTTPException(404)
    from ..ingest import store
    store.vote(d, story, s['url'], s['source'], s['category'], 1 if value > 0 else -1, state.now().isoformat(timespec='seconds'))
    return {'ok': True}


@app.get('/archive', response_class=HTMLResponse)
def archive(request: Request):
    if not reader_allowed(request):
        return guard(request)
    return render(request, 'archive.html', editions=reading_editions())


# ------------------------------------------------------------------ auth
_failed = {}


@app.get('/login')
def login_page(request: Request, next: str = '/admin'):
    if is_admin(request):
        return RedirectResponse(next if next.startswith('/') else '/admin', status_code=303)
    return render(request, 'login.html', error=request.session.pop('login_error', None), next=next)


@app.post('/login')
def login(request: Request, password: str = Form(...), next: str = Form('/admin')):
    ip = request.client.host if request.client else '?'
    t = datetime.datetime.now()
    recent = [x for x in _failed.get(ip, []) if x > t - datetime.timedelta(minutes=15)]
    if len(recent) >= 8:
        request.session['login_error'] = 'Too many attempts. Try again in 15 minutes.'
        return RedirectResponse('/login', status_code=303)
    if hmac.compare_digest(password.encode(), admin_password().encode()):
        request.session.clear()
        request.session['admin'] = True
        _failed.pop(ip, None)
        return RedirectResponse(next if next.startswith('/') else '/admin', status_code=303)
    _failed[ip] = recent + [t]
    request.session['login_error'] = 'Wrong password.'
    return RedirectResponse('/login', status_code=303)


@app.post('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse('/login', status_code=303)


# ------------------------------------------------------------------ dashboard
@app.get('/admin')
def dashboard(request: Request):
    if (r := guard(request)):
        return r
    c = cfg()
    if not c.setup_complete:
        return RedirectResponse('/admin/setup', status_code=303)
    from ..ingest import store
    con = store.connect()
    counts = {r['status']: r['n'] for r in con.execute('SELECT status, COUNT(*) n FROM items GROUP BY status')}
    feeds = [dict(r) for r in con.execute('SELECT * FROM feeds ORDER BY name')]
    t = state.today().isoformat()
    build_date = schedule.edition_date_for_build(c).isoformat()
    eds = state.list_editions()
    last = eds[0] if eds else None
    last_meta = state.read_meta(last['date']) if last else {}
    return render(request, 'dashboard.html', editions=eds[:10], activity=state.read_activity(25), next_runs=schedule.next_runs(),
                  today=t, build_date=build_date, counts=counts, feeds=feeds, feed_errors=[f for f in feeds if f.get('last_error')],
                  last=last, last_meta=last_meta, last_ingest=store.kv_get('last_ingest') or {}, jobs=state.recent_jobs(),
                  running=[j.as_dict() for j in state.running()], push_enabled=bool(secrets.get('push_token')),
                  base_url=_base_url(request))


def _base_url(request):
    base = str(request.base_url).rstrip('/')
    proto = request.headers.get('x-forwarded-proto')
    return re.sub(r'^https?', proto, base) if proto else base


@app.post('/admin/build')
def build_now(request: Request, date: str = Form('')):
    if (r := guard(request)):
        return r
    d = check_date(date) if date else schedule.edition_date_for_build().isoformat()
    job, started = schedule.run_build(d, trigger='manual')
    flash(request, f'Making the {d} paper; it takes a few minutes.' if started else 'A build or feed fetch is already running.', started)
    return RedirectResponse(f'/admin?job={job.id}', status_code=303)


@app.post('/admin/ingest')
def ingest_now(request: Request):
    if (r := guard(request)):
        return r
    job, started = schedule.run_ingest(trigger='manual')
    flash(request, 'Fetching feeds.' if started else 'A build or feed fetch is already running.', started)
    return RedirectResponse(f'/admin?job={job.id}', status_code=303)


@app.get('/admin/jobs/{jid}')
def job_status(request: Request, jid: str):
    if not is_admin(request):
        raise HTTPException(401)
    j = state.get_job(jid)
    if not j:
        raise HTTPException(404)
    return j.as_dict()


# ------------------------------------------------------------------ editions
@app.get('/admin/editions')
def editions_page(request: Request):
    if (r := guard(request)):
        return r
    return render(request, 'editions.html', editions=state.list_editions(), today=state.today().isoformat())


@app.get('/admin/editions/{d}')
def edition_page(request: Request, d: str):
    if (r := guard(request)):
        return r
    check_date(d)
    m = state.read_meta(d)
    qa_path = os.path.join(paths.out_dir(d), 'qa.json')
    if not os.path.exists(qa_path):
        qa_path = os.path.join(paths.edition_dir(d), 'qa.json')
    qa = json.load(open(qa_path)) if os.path.exists(qa_path) else {}
    rows = sorted(x for x in os.listdir(paths.out_dir(d)) if re.match(r'c-row\d+\.png$', x)) if os.path.isdir(paths.out_dir(d)) else []
    log_p = os.path.join(paths.edition_dir(d), 'build.log')
    log = open(log_p, errors='replace').read()[-12000:] if os.path.exists(log_p) else ''
    content = os.path.join(paths.edition_dir(d), 'edition.json')
    gen = json.load(open(content)).get('meta', {}) if os.path.exists(content) else {}
    return render(request, 'edition.html', d=d, meta=m, qa=qa, rows=rows, log=log, gen=gen, stories=edition_stories(d),
                  has_booklet=os.path.exists(state.pdf(d)), has_reading=os.path.exists(state.pdf(d, 'reading')))


@app.get('/admin/editions/{d}/{name}')
def edition_file(request: Request, d: str, name: str):
    if (r := guard(request)):
        return r
    check_date(d)
    if name in ('booklet.pdf', 'reading.pdf'):
        f = state.pdf(d, name[:-4])
        if not os.path.exists(f):
            f = os.path.join(paths.out_dir(d), name)
        if not os.path.exists(f):
            raise HTTPException(404)
        return FileResponse(f, media_type='application/pdf', content_disposition_type='inline', filename=f'{d}-{name}')
    if re.match(r'^c-row\d+\.png$', name):
        f = os.path.join(paths.out_dir(d), name)
        if os.path.exists(f):
            return FileResponse(f, media_type='image/png')
    raise HTTPException(404)


@app.post('/admin/editions/{d}/print')
def print_now(request: Request, d: str):
    if (r := guard(request)):
        return r
    check_date(d)
    ok, out = schedule.print_edition(d, 'manual')
    flash(request, f'Sent {d} to the printer. {out}' if ok else f'Print failed: {out}', ok)
    return RedirectResponse(request.headers.get('referer') or '/admin', status_code=303)


@app.post('/admin/editions/{d}/delete')
def delete_edition(request: Request, d: str):
    if (r := guard(request)):
        return r
    check_date(d)
    for name in ('booklet.pdf', 'reading.pdf', 'meta.json', 'qa.json'):
        p = os.path.join(paths.edition_dir(d), name)
        if os.path.exists(p):
            os.remove(p)
    state.activity('delete', f'Deleted the PDFs of edition {d}')
    flash(request, f'Deleted the {d} PDFs (its content stays in the ledger).')
    return RedirectResponse('/admin/editions', status_code=303)


@app.post('/upload')
async def manual_upload(request: Request, file: UploadFile = File(...), date_: str = Form('', alias='date')):
    if (r := guard(request)):
        return r
    d = check_date(date_ or state.today().isoformat())
    try:
        store_edition(await file.read(MAX_UPLOAD + 1), d, source='admin upload')
        flash(request, f'Uploaded edition for {d}.')
    except HTTPException as e:
        flash(request, f'Upload failed: {e.detail}', False)
    return RedirectResponse('/admin/editions', status_code=303)


def store_edition(blob, d, title='', data=None, source='api', reading=None):
    from pypdf import PdfReader
    for b in (blob, reading):
        if b is not None:
            if not b.startswith(b'%PDF'):
                raise HTTPException(415, 'file is not a PDF')
            if len(b) > MAX_UPLOAD:
                raise HTTPException(413, 'file too large')
    os.makedirs(paths.edition_dir(d), exist_ok=True)
    tmp = state.pdf(d) + '.upload'
    with open(tmp, 'wb') as f:
        f.write(blob)
    try:
        pages = len(PdfReader(tmp).pages)
    except Exception as e:  # noqa: BLE001
        os.remove(tmp)
        raise HTTPException(422, f'PDF could not be read: {e}')
    os.replace(tmp, state.pdf(d))
    m = state.read_meta(d)
    replaced = bool(m)
    m.update(title=title or m.get('title', ''), pages=pages, uploaded_at=state.now().isoformat(timespec='seconds'), source=source)
    if data is not None:
        m['data'] = data
        with open(os.path.join(paths.edition_dir(d), 'puzzles.json'), 'w') as f:
            json.dump(data, f, indent=1)
    m.setdefault('prints', [])
    if reading is not None:
        with open(state.pdf(d, 'reading'), 'wb') as f:
            f.write(reading)
        m['reading_pages'] = len(PdfReader(state.pdf(d, 'reading')).pages)
    state.write_meta(d, m)
    state.activity('upload', f'{"Replaced" if replaced else "Received"} edition {d} ({pages} pages) via {source}')
    return {'date': d, 'pages': pages, 'replaced': replaced, 'reading': reading is not None}


# ------------------------------------------------------------------ settings
@app.get('/admin/settings')
def settings_root(request: Request):
    return RedirectResponse('/admin/settings/general', status_code=303)


@app.get('/admin/settings/{tab}')
def settings_page(request: Request, tab: str):
    if (r := guard(request)):
        return r
    t = forms.tabs()
    if tab not in t:
        raise HTTPException(404)
    c = cfg()
    title, fields = t[tab]
    from ..ai.prompts import DEFAULT_HOUSE_STYLE
    secret_rows = [(k, label, secrets.source(k)) for k, label in forms.SECRET_FIELDS.get(tab, [])]
    return render(request, 'settings.html', tab=tab, tabs=t, title=title,
                  fields=[dict(f, value=forms.display(c, f)) for f in fields], secret_rows=secret_rows,
                  house_style_default=DEFAULT_HOUSE_STYLE, problems=config.layout_problems(c))


@app.post('/admin/settings/{tab}')
async def settings_save(request: Request, tab: str):
    if (r := guard(request)):
        return r
    form = await request.form()
    if tab not in forms.tabs():
        raise HTTPException(404)
    try:
        new = config.update(cfg(), forms.parse(tab, form))
        for k, _ in forms.SECRET_FIELDS.get(tab, []):
            v = (form.get(f'secret.{k}') or '').strip()
            if v:
                secrets.set(k, v)
            if form.get(f'clear.{k}'):
                secrets.set(k, '')
        config.save(new)
        config.activate(new)
        schedule.apply()
        state.activity('settings', f'Saved {forms.tabs()[tab][0]} settings')
        flash(request, 'Saved.')
    except Exception as e:  # noqa: BLE001
        flash(request, f'Not saved: {e}', False)
    return RedirectResponse(f'/admin/settings/{tab}', status_code=303)


@app.post('/admin/ai/test')
def ai_test(request: Request):
    if not is_admin(request):
        raise HTTPException(401)
    from ..ai.providers import test_connection
    ok, msg = test_connection(cfg())
    return {'ok': ok, 'message': msg}


@app.post('/printer/test')
def printer_test(request: Request, cups_server: str = Form('')):
    if not is_admin(request):
        raise HTTPException(401)
    ok, queues, err = delivery.cups_queues(cups_server.strip())
    return {'ok': ok, 'queues': queues, 'error': err}


@app.get('/admin/yaml')
def yaml_page(request: Request):
    if (r := guard(request)):
        return r
    return render(request, 'yaml.html', text=config.dump(cfg()), full=config.dump(cfg(), full=True))


@app.post('/admin/yaml')
def yaml_save(request: Request, text: str = Form(...)):
    if (r := guard(request)):
        return r
    import yaml
    try:
        new = config.Config(**(yaml.safe_load(text) or {}))
        config.save(new)
        config.activate(new)
        schedule.apply()
        flash(request, 'Saved config.yaml.')
    except Exception as e:  # noqa: BLE001
        flash(request, f'Not saved: {e}', False)
    return RedirectResponse('/admin/yaml', status_code=303)


@app.get('/admin/config.yaml')
def config_download(request: Request):
    if (r := guard(request)):
        return r
    return PlainTextResponse(config.dump(cfg(), full=True), headers={'Content-Disposition': 'attachment; filename=config.yaml'})


# ------------------------------------------------------------------ categories
@app.get('/admin/categories')
def categories_page(request: Request):
    if (r := guard(request)):
        return r
    return render(request, 'categories.html', cats=cfg().editorial.categories)


@app.post('/admin/categories')
async def categories_save(request: Request):
    if (r := guard(request)):
        return r
    form = await request.form()
    cats = []
    i = 0
    while f'name.{i}' in form:
        name = form.get(f'name.{i}', '').strip()
        if name and not form.get(f'delete.{i}'):
            cap = form.get(f'cap.{i}', '').strip()
            cats.append(dict(name=name, family=form.get(f'family.{i}', 'culture'), weight=float(form.get(f'weight.{i}') or 1),
                             favorite=bool(form.get(f'favorite.{i}')), enabled=bool(form.get(f'enabled.{i}')),
                             cap=int(cap) if cap else None,
                             keywords=[k.strip() for k in re.split(r'[,\n]', form.get(f'keywords.{i}', '')) if k.strip()]))
        i += 1
    if form.get('new.name', '').strip():
        cats.append(dict(name=form['new.name'].strip(), family=form.get('new.family', 'culture'), weight=1.0, enabled=True,
                         keywords=[k.strip() for k in re.split(r'[,\n]', form.get('new.keywords', '')) if k.strip()]))
    # the ticked boxes are the whole truth about favourites; keep them in editorial.favorites only, so an
    # unedited category list still equals the defaults and is not written to config.yaml
    favs = [c['name'] for c in cats if c.get('favorite')]
    for c in cats:
        c['favorite'] = False
    try:
        new = config.update(cfg(), {'editorial': {'categories': cats, 'favorites': favs}})
        config.save(new)
        config.activate(new)
        flash(request, f'Saved {len(cats)} categories.')
    except Exception as e:  # noqa: BLE001
        flash(request, f'Not saved: {e}', False)
    return RedirectResponse('/admin/categories', status_code=303)


# ------------------------------------------------------------------ sources
@app.get('/admin/sources')
def sources_page(request: Request):
    if (r := guard(request)):
        return r
    from ..ingest import store
    status = {r['url']: dict(r) for r in store.connect().execute('SELECT * FROM feeds')}
    counts = {}
    for r in store.connect().execute("SELECT source, status, COUNT(*) n FROM items GROUP BY source, status"):
        counts.setdefault(r['source'], {})[r['status']] = r['n']
    c = cfg()
    present = {s.url for s in c.sources.feeds}
    packs = [dict(p, added=sum(1 for s in p['sources'] if s['url'] in present)) for p in config.source_packs()]
    return render(request, 'sources.html', feeds=c.sources.feeds, status=status, counts=counts, packs=packs,
                  licenses=config.LICENSES, tiers=config.TIERS, categories=c.editorial.category_names())


def _save_sources(feeds, request, msg):
    try:
        new = config.update(cfg(), {'sources': {'feeds': feeds}})
        config.save(new)
        config.activate(new)
        schedule.apply()
        flash(request, msg)
    except Exception as e:  # noqa: BLE001
        flash(request, f'Not saved: {e}', False)


@app.post('/admin/sources')
async def sources_save(request: Request):
    if (r := guard(request)):
        return r
    form = await request.form()
    feeds = []
    for i, s in enumerate(cfg().sources.feeds):
        if form.get(f'delete.{i}'):
            continue
        d = s.model_dump()
        if f'name.{i}' in form:
            d.update(name=form.get(f'name.{i}', s.name).strip(), url=form.get(f'url.{i}', s.url).strip(),
                     license=form.get(f'license.{i}', s.license), enabled=bool(form.get(f'enabled.{i}')),
                     images=bool(form.get(f'images.{i}')), category=form.get(f'category.{i}') or None,
                     trust=float(form.get(f'trust.{i}') or s.trust), max_per_edition=int(form.get(f'max.{i}') or s.max_per_edition),
                     attribution=form.get(f'attribution.{i}', s.attribution).strip(),
                     tier=form.get(f'tier.{i}') or None)
        feeds.append(d)
    if form.get('new.url', '').strip():
        feeds.append(dict(name=form.get('new.name', '').strip() or form['new.url'].strip(), url=form['new.url'].strip(),
                          license=form.get('new.license', 'copyrighted'), category=form.get('new.category') or None, enabled=True))
    _save_sources(feeds, request, f'Saved {len(feeds)} sources.')
    return RedirectResponse('/admin/sources', status_code=303)


@app.post('/admin/sources/pack/{pid}')
def sources_pack(request: Request, pid: str):
    if (r := guard(request)):
        return r
    pack = next((p for p in config.source_packs() if p['id'] == pid), None)
    if not pack:
        raise HTTPException(404)
    feeds = [s.model_dump() for s in cfg().sources.feeds]
    have = {f['url'] for f in feeds}
    add = [dict(s, pack=pid) for s in pack['sources'] if s['url'] not in have]
    _save_sources(feeds + add, request, f'Added {len(add)} sources from {pack["name"]}.')
    return RedirectResponse('/admin/sources', status_code=303)


@app.post('/admin/sources/test')
def sources_test(request: Request, url: str = Form(...)):
    if not is_admin(request):
        raise HTTPException(401)
    from ..ingest import fetch
    return fetch.test_feed(url.strip())


@app.get('/admin/sources.opml')
def sources_opml(request: Request):
    if (r := guard(request)):
        return r
    root = ET.Element('opml', version='2.0')
    head = ET.SubElement(root, 'head')
    ET.SubElement(head, 'title').text = f'{cfg().paper.title} sources'
    body = ET.SubElement(root, 'body')
    for s in cfg().sources.feeds:
        ET.SubElement(body, 'outline', type='rss', text=s.name, title=s.name, xmlUrl=s.url, htmlUrl=s.homepage,
                      license=s.license, category=s.category or '')
    return Response(ET.tostring(root, encoding='unicode', xml_declaration=True), media_type='text/x-opml',
                    headers={'Content-Disposition': 'attachment; filename=sources.opml'})


@app.post('/admin/sources.opml')
async def sources_opml_import(request: Request, file: UploadFile = File(...)):
    if (r := guard(request)):
        return r
    try:
        root = ET.fromstring(await file.read(2_000_000))
    except ET.ParseError as e:
        flash(request, f'Not an OPML file: {e}', False)
        return RedirectResponse('/admin/sources', status_code=303)
    feeds = [s.model_dump() for s in cfg().sources.feeds]
    have = {f['url'] for f in feeds}
    n = 0
    for o in root.iter('outline'):
        url = o.get('xmlUrl')
        if url and url not in have and url.startswith('http'):
            lic = o.get('license') if o.get('license') in config.LICENSES else 'copyrighted'
            feeds.append(dict(name=o.get('title') or o.get('text') or url, url=url, homepage=o.get('htmlUrl') or '', license=lic))
            have.add(url)
            n += 1
    _save_sources(feeds, request, f'Imported {n} feeds (as copyrighted: check each license before raising it).')
    return RedirectResponse('/admin/sources', status_code=303)


# ------------------------------------------------------------------ editor's desk
@app.get('/admin/desk')
def desk(request: Request, status: str = 'candidate', q: str = '', category: str = ''):
    if (r := guard(request)):
        return r
    from ..ingest import store
    where, args = [], []
    if status == 'candidate':
        where.append("status IN ('candidate','pinned','backlog')")
    elif status:
        where.append('status=?')
        args.append(status)
    if q:
        where.append('(title LIKE ? OR source LIKE ?)')
        args += [f'%{q}%', f'%{q}%']
    if category:
        where.append('category=?')
        args.append(category)
    rows = store.items(' AND '.join(where) or '1=1', tuple(args), order="status='pinned' DESC, score DESC", limit=250)
    plan = None
    if request.query_params.get('plan'):
        try:
            from ..auto import select
            p = select.plan(log=lambda m: None)
            plan = dict(pages=p.pages, lead=p.lead, sidebar=p.sidebar, spread=p.spread, units=p.units, wonders=p.wonders,
                        reserve=p.reserve)
        except Exception as e:  # noqa: BLE001
            plan = {'error': str(e)}
    return render(request, 'desk.html', rows=rows, status=status, q=q, category=category, plan=plan,
                  categories=cfg().editorial.category_names())


@app.post('/admin/desk/{item_id}')
def desk_action(request: Request, item_id: int, action: str = Form(...), category: str = Form('')):
    if (r := guard(request)):
        return r
    from ..ingest import store, score
    if action in ('pin', 'kill', 'backlog', 'candidate'):
        store.update(item_id, status={'pin': 'pinned', 'kill': 'killed', 'backlog': 'backlog', 'candidate': 'candidate'}[action])
    elif action == 'category' and category in cfg().editorial.category_names():
        store.update(item_id, category=category, cat_method='desk', cat_score=1.0)
    score.rescore_all()
    return RedirectResponse(request.headers.get('referer') or '/admin/desk', status_code=303)


# ------------------------------------------------------------------ first-run setup
@app.get('/admin/setup')
def setup_page(request: Request, step: int = 1):
    if (r := guard(request)):
        return r
    c = cfg()
    present = {s.url for s in c.sources.feeds}
    packs = [dict(p, on=any(s['url'] in present for s in p['sources'])) for p in config.source_packs()]
    return render(request, 'setup.html', step=max(1, min(step, 7)), packs=packs, profiles=profiles.choices(),
                  sections=[(k, config.SECTION_LABELS[k]) for k in config.SECTION_NAMES],
                  cats=c.editorial.category_names(False), favorites=c.editorial.favorite_names(),
                  timezones=sorted(__import__('zoneinfo').available_timezones()), ai_key=secrets.source('anthropic_api_key'))


@app.post('/admin/setup')
async def setup_save(request: Request):
    if (r := guard(request)):
        return r
    form = await request.form()
    step = int(form.get('step', 1))
    c = cfg()
    try:
        if step == 1:
            patch = {'paper': {'title': form['title'].strip() or 'The Morning Current', 'tagline': form.get('tagline', '').strip(),
                               'household': form.get('household', '').strip()},
                     'location': {'name': form['place'].strip(), 'lat': float(form['lat']), 'lon': float(form['lon']),
                                  'tz': form['tz'], 'elevation': float(form.get('elevation') or 0)},
                     'format': {'clock': form.get('clock', '24h'), 'units': form.get('units', 'imperial')}}
        elif step == 2:
            pages = int(form.get('pages', 16))
            patch = {'format': {'profile': form['profile'], 'pages': pages, 'pages_light': max(12, min(pages, 12)) if pages >= 12 else pages,
                                'pages_min': 12 if pages >= 12 else pages, 'sections': form.getlist('sections')}}
        elif step == 3:
            patch = {'editorial': {'favorites': form.getlist('favorites'), 'reader_profile': form.get('reader', '').strip()
                                   or c.editorial.reader_profile}}
        elif step == 4:
            chosen = set(form.getlist('packs'))
            feeds = [s.model_dump() for s in c.sources.feeds if s.pack not in {p['id'] for p in config.source_packs()} or s.pack in chosen]
            have = {f['url'] for f in feeds}
            for p in config.source_packs():
                if p['id'] in chosen:
                    feeds += [dict(s, pack=p['id']) for s in p['sources'] if s['url'] not in have]
            patch = {'sources': {'feeds': feeds}}
        elif step == 5:
            patch = {'schedule': {'build_time': form.get('build_time', '00:30'), 'print_enabled': bool(form.get('print_enabled')),
                                  'weekday_time': form.get('weekday_time', '06:30'), 'weekend_time': form.get('weekend_time', '08:00')},
                     'printer': {'cups_server': form.get('cups_server', '').strip(), 'printer': form.get('printer', '').strip()}}
        elif step == 6:
            provider = form.get('provider', 'none')
            patch = {'ai': {'provider': provider, 'model': form.get('model') or c.ai.model,
                            'max_cost_usd': float(form.get('budget') or c.ai.max_cost_usd)}}
            if form.get('api_key', '').strip():
                secrets.set('anthropic_api_key' if provider == 'claude' else 'openai_api_key', form['api_key'].strip())
            if provider == 'openai':
                patch['ai']['base_url'] = form.get('base_url', '').strip()
        else:
            patch = {'setup_complete': True}
        new = config.update(c, patch)
        config.save(new)
        config.activate(new)
    except Exception as e:  # noqa: BLE001
        flash(request, f'Please check that step: {e}', False)
        return RedirectResponse(f'/admin/setup?step={step}', status_code=303)
    if step >= 7:
        schedule.apply()
        job, _ = schedule.run_build(state.today().isoformat(), trigger='first run')
        flash(request, 'Setup done. Your first paper is being made now (a few minutes).')
        return RedirectResponse(f'/admin?job={job.id}', status_code=303)
    return RedirectResponse(f'/admin/setup?step={step + 1}', status_code=303)


# ------------------------------------------------------------------ push API (compatible with Morning Press)
@app.post('/api/editions')
async def api_push(request: Request, file: UploadFile = File(...), date_: str = Form('', alias='date'), title: str = Form(''),
                   data: str = Form(''), reading: UploadFile | None = File(None)):
    require_token(request)
    d = check_date(date_ or state.today().isoformat())
    payload = None
    if data:
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            raise HTTPException(400, 'data must be valid JSON')
    blob = await file.read(MAX_UPLOAD + 1)
    rblob = await reading.read(MAX_UPLOAD + 1) if reading is not None else None
    return store_edition(blob, d, title, payload, source='api', reading=rblob)


@app.get('/api/editions')
def api_list(request: Request):
    require_token(request)
    return state.list_editions()


@app.get('/api/editions/{d}/data')
def api_data(request: Request, d: str):
    require_token(request)
    check_date(d)
    p = os.path.join(paths.edition_dir(d), 'puzzles.json')
    return JSONResponse(json.load(open(p)) if os.path.exists(p) else state.read_meta(d).get('data') or {})


@app.get('/api/status')
def api_status(request: Request):
    require_token(request)
    c = cfg()
    t = state.today().isoformat()
    return {'print_enabled': c.schedule.print_enabled, 'pause_until': c.schedule.pause_until,
            'weekday': c.schedule.weekday_time if c.schedule.weekday_enabled else None,
            'weekend': c.schedule.weekend_time if c.schedule.weekend_enabled else None,
            'next_runs': [{'kind': r['id'], 'at': r['at'].isoformat()} for r in schedule.next_runs()],
            'today': t, 'today_received': os.path.exists(state.pdf(t)), 'running': [j.as_dict()['label'] for j in state.running()]}


@app.post('/api/build')
def api_build(request: Request, date: str = Form('')):
    require_token(request)
    job, started = schedule.run_build(check_date(date) if date else None, trigger='api')
    return {'started': started, 'job': job.id}


@app.post('/api/ingest')
def api_ingest(request: Request):
    require_token(request)
    job, started = schedule.run_ingest(trigger='api')
    return {'started': started, 'job': job.id}
