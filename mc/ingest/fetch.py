"""Polite HTTP: one client, an honest User-Agent, conditional GETs for feeds, a delay between requests to
the same host, robots.txt for article pages, size limits and timeouts."""
import datetime
import hashlib
import io
import os
import re
import threading
import time
import urllib.robotparser
from urllib.parse import urlsplit

import httpx

from .. import paths, config

MAX_BYTES = 6 * 1024 * 1024
_last_hit = {}
_robots = {}
_lock = threading.Lock()
_client = None


def _cfg():
    return config.load().sources


def client():
    global _client
    if _client is None:
        s = _cfg()
        _client = httpx.Client(headers={'User-Agent': s.user_agent, 'Accept-Language': 'en'}, follow_redirects=True,
                               timeout=httpx.Timeout(s.timeout, connect=min(10, s.timeout)), max_redirects=6)
    return _client


def _pace(url):
    host = urlsplit(url).netloc
    delay = _cfg().per_host_delay
    with _lock:
        wait = _last_hit.get(host, 0) + delay - time.monotonic()
        _last_hit[host] = max(time.monotonic(), _last_hit.get(host, 0) + delay)
    if wait > 0:
        time.sleep(wait)


def robots_ok(url):
    if not _cfg().respect_robots:
        return True
    u = urlsplit(url)
    base = f'{u.scheme}://{u.netloc}'
    rp = _robots.get(base)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            _pace(base)
            r = client().get(base + '/robots.txt', timeout=10)
            if r.status_code >= 400:
                rp.parse([])            # no robots.txt: everything allowed
            else:
                rp.parse(r.text.splitlines())
        except httpx.HTTPError:
            rp.parse([])
        _robots[base] = rp
    return rp.can_fetch(_cfg().user_agent, url)


def get(url, etag=None, last_modified=None, accept=None):
    """GET with pacing and a size cap. Returns (status, bytes, headers, final_url)."""
    headers = {}
    if etag:
        headers['If-None-Match'] = etag
    if last_modified:
        headers['If-Modified-Since'] = last_modified
    if accept:
        headers['Accept'] = accept
    _pace(url)
    with client().stream('GET', url, headers=headers) as r:
        if r.status_code == 304:
            return 304, b'', r.headers, str(r.url)
        buf = io.BytesIO()
        for chunk in r.iter_bytes():
            buf.write(chunk)
            if buf.tell() > MAX_BYTES:
                break
        return r.status_code, buf.getvalue(), r.headers, str(r.url)


def fetch_feed(url, etag=None, last_modified=None):
    """Returns dict(status, entries, etag, last_modified, error)."""
    import feedparser
    try:
        status, body, headers, final = get(url, etag, last_modified,
                                           accept='application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.5')
    except httpx.HTTPError as e:
        return dict(status=0, entries=[], error=f'{type(e).__name__}: {e}')
    if status == 304:
        return dict(status=304, entries=[], etag=etag, last_modified=last_modified, error=None)
    if status >= 400:
        return dict(status=status, entries=[], error=f'HTTP {status}')
    body = re.sub(rb'"(xmlns:\w+=)', rb'" \1', body)      # a common publisher typo that breaks strict XML
    d = feedparser.parse(body)
    if d.bozo and not d.entries:
        return dict(status=status, entries=[], error=f'not a feed ({type(d.bozo_exception).__name__})')
    return dict(status=status, entries=d.entries, feed=d.feed, etag=headers.get('etag'),
                last_modified=headers.get('last-modified'), error=None, final_url=final)


def fetch_page(url):
    """An article page's HTML, or None when robots.txt forbids it or the fetch fails."""
    if not robots_ok(url):
        return None
    try:
        status, body, headers, final = get(url, accept='text/html,application/xhtml+xml')
    except httpx.HTTPError:
        return None
    if status >= 400 or not body:
        return None
    ctype = headers.get('content-type', '')
    if 'html' not in ctype and not body.lstrip()[:200].lower().startswith((b'<!doctype', b'<html')):
        return None
    enc = 'utf-8'
    if 'charset=' in ctype:
        enc = ctype.split('charset=')[-1].split(';')[0].strip() or 'utf-8'
    try:
        return body.decode(enc, errors='replace')
    except LookupError:
        return body.decode('utf-8', errors='replace')


def download_image(url, max_px=1400):
    """Download an image into the cache as a grayscale JPEG. Returns the local path or None."""
    from PIL import Image
    d = paths.cache_dir('img')
    os.makedirs(d, exist_ok=True)
    out = os.path.join(d, hashlib.sha1(url.encode()).hexdigest()[:20] + '.jpg')
    if os.path.exists(out):
        return out
    try:
        status, body, headers, _ = get(url, accept='image/*')
        if status >= 400 or not body:
            return None
        im = Image.open(io.BytesIO(body))
        im.load()
        if min(im.size) < 300:
            return None
        im = im.convert('L')
        im.thumbnail((max_px, max_px))
        im.save(out, 'JPEG', quality=82, optimize=True)
        return out
    except Exception:  # noqa: BLE001 - any bad image is simply skipped
        return None


def test_feed(url):
    t0 = time.time()
    r = fetch_feed(url)
    out = dict(url=url, ok=not r.get('error'), error=r.get('error'), status=r.get('status'),
               items=len(r.get('entries', [])), seconds=round(time.time() - t0, 1))
    if r.get('entries'):
        out['title'] = (r.get('feed') or {}).get('title', '')
        out['sample'] = [dict(title=e.get('title', ''), link=e.get('link', ''), published=e.get('published', ''),
                              full_text=bool(e.get('content'))) for e in r['entries'][:5]]
    return out


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
