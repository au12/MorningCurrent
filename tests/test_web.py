"""The web app: sign-in, every admin page, settings round trips, the setup wizard and the push API."""
import importlib
import io
import re

import pytest
from fastapi.testclient import TestClient

from conftest import write_config


@pytest.fixture
def client(data, monkeypatch):
    monkeypatch.setenv('ADMIN_PASSWORD', 'secret-pw')
    monkeypatch.setenv('PUSH_TOKEN', 'tok-123')
    write_config('schedule:\n  build_enabled: false\n')
    import mc.web.app as app_module
    app_module = importlib.reload(app_module)
    with TestClient(app_module.app) as c:
        yield c


def login(c):
    r = c.post('/login', data={'password': 'secret-pw', 'next': '/admin'}, follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == '/admin'


def pdf_bytes(pages=4):
    from pypdf import PdfWriter
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(612, 792)
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


def test_public_pages_and_sign_in(client):
    assert client.get('/healthz').json()['ok']
    assert client.get('/favicon.ico').status_code == 200
    assert client.get('/manifest.webmanifest').json()['start_url'] == '/read'
    r = client.get('/admin', follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'].startswith('/login')
    r = client.post('/login', data={'password': 'nope', 'next': '/admin'}, follow_redirects=False)
    assert r.headers['location'] == '/login'
    login(client)
    assert client.get('/admin', follow_redirects=False).headers['location'] == '/admin/setup'   # setup not finished


@pytest.mark.parametrize('path', ['/admin/setup?step=%d' % i for i in range(1, 8)] + [
    '/admin/settings/general', '/admin/settings/layout', '/admin/settings/content', '/admin/settings/schedule',
    '/admin/settings/ai', '/admin/categories', '/admin/sources', '/admin/desk', '/admin/desk?status=&q=x&plan=1',
    '/admin/editions', '/admin/yaml', '/admin/config.yaml', '/admin/sources.opml'])
def test_admin_pages_render(client, path):
    login(client)
    r = client.get(path)
    assert r.status_code == 200, r.text[:500]


def form_fields(html, action):
    """The fields a browser would submit for the form posting to `action`."""
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.on, self.out, self.sel, self.ta, self.opt = False, [], None, None, None

        def handle_starttag(self, tag, a):
            a = dict(a)
            if tag == 'form':
                self.on = a.get('action') == action and a.get('method') == 'post'
            if not self.on:
                return
            if tag == 'input' and a.get('name') and a.get('type', 'text') not in ('file', 'button', 'submit'):
                if a.get('type') in ('checkbox', 'radio'):
                    if 'checked' in a:
                        self.out.append((a['name'], a.get('value', 'on')))
                else:
                    self.out.append((a['name'], a.get('value', '')))
            elif tag == 'select':
                self.sel = [a.get('name'), None, None]
            elif tag == 'option' and self.sel:
                self.opt = [a.get('value'), 'selected' in a, '']
            elif tag == 'textarea':
                self.ta = [a.get('name'), '']

        def handle_data(self, d):
            if self.opt is not None:
                self.opt[2] += d
            if self.ta is not None:
                self.ta[1] += d

        def handle_endtag(self, tag):
            if tag == 'option' and self.opt is not None:
                v = self.opt[0] if self.opt[0] is not None else self.opt[2]
                if self.sel[1] is None:
                    self.sel[1] = v
                if self.opt[1]:
                    self.sel[2] = v
                self.opt = None
            elif tag == 'select' and self.sel:
                self.out.append((self.sel[0], self.sel[2] if self.sel[2] is not None else self.sel[1]))
                self.sel = None
            elif tag == 'textarea' and self.ta:
                self.out.append((self.ta[0], self.ta[1][1:] if self.ta[1].startswith('\n') else self.ta[1]))
                self.ta = None
            elif tag == 'form':
                self.on = False
    p = P()
    p.feed(html)
    import html as h
    d = {}
    for k, v in p.out:
        d.setdefault(k, []).append(h.unescape(v))
    return d


@pytest.mark.parametrize('page,action', [(f'/admin/settings/{t}', f'/admin/settings/{t}') for t in
                                         ('general', 'layout', 'content', 'schedule', 'ai')]
                         + [('/admin/categories', '/admin/categories'), ('/admin/sources', '/admin/sources')])
def test_settings_round_trip_changes_nothing(client, page, action):
    from mc import config
    login(client)
    before = config.dump(config.load(use_cache=False), full=True)
    r = client.post(action, data=form_fields(client.get(page).text, action))
    assert r.status_code == 200 and 'Not saved' not in r.text
    assert config.dump(config.load(use_cache=False), full=True) == before


def test_settings_change_is_saved(client):
    from mc import config
    login(client)
    f = form_fields(client.get('/admin/settings/general').text, '/admin/settings/general')
    f['paper.title'] = ['The Tuesday Test']
    client.post('/admin/settings/general', data=f)
    assert config.load(use_cache=False).paper.title == 'The Tuesday Test'
    f = form_fields(client.get('/admin/settings/layout').text, '/admin/settings/layout')
    f['format.pages'] = ['10']
    r = client.post('/admin/settings/layout', data=f)
    assert 'Not saved' in r.text and config.load(use_cache=False).format.pages == 16


def test_setup_wizard(client):
    from mc import config
    login(client)
    for step in range(1, 7):
        f = form_fields(client.get(f'/admin/setup?step={step}').text, '/admin/setup')
        if step == 1:
            f.update(title=['The Hillside Herald'], place=['Hillside'], lat=['44.5'], lon=['-72.6'], tz=['America/New_York'])
        r = client.post('/admin/setup', data=f, follow_redirects=False)
        assert r.headers['location'] == f'/admin/setup?step={step + 1}', (step, r.headers['location'])
    cfg = config.load(use_cache=False)
    assert cfg.paper.title == 'The Hillside Herald' and cfg.location.lat == 44.5 and not cfg.setup_complete


def test_push_api_and_reader(client):
    assert client.post('/api/editions', files={'file': ('x.pdf', pdf_bytes())}).status_code == 401
    h = {'Authorization': 'Bearer tok-123'}
    r = client.post('/api/editions', headers=h, data={'date': '2026-11-14', 'title': 'Test'},
                    files={'file': ('b.pdf', pdf_bytes(4)), 'reading': ('r.pdf', pdf_bytes(2))})
    assert r.status_code == 200 and r.json()['pages'] == 4 and r.json()['reading']
    bad = client.post('/api/editions', headers=h, data={'date': '2026-11-15'}, files={'file': ('b.pdf', b'not a pdf')})
    assert bad.status_code == 415
    assert client.get('/api/editions', headers=h).json()[0]['date'] == '2026-11-14'
    assert client.get('/api/status', headers=h).status_code == 200
    r = client.get('/read', follow_redirects=False)
    assert r.headers['location'] == '/read/2026-11-14'
    page = client.get('/read/2026-11-14').text
    assert 'page-flip' in page and re.search(r'/read/2026-11-14\.pdf', page)
    assert client.get('/read/2026-11-14.pdf').content.startswith(b'%PDF')
    assert client.get('/archive').status_code == 200
    login(client)
    assert client.get('/admin/editions/2026-11-14').status_code == 200
    assert client.get('/admin').status_code in (200, 303)
