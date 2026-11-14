"""Research mode: before planning, Claude searches the web for tonight's best candidates (guided by the
categories, favorites, reader profile and what recent papers already ran). Its picks join the article
database like feed items, marked as editor's picks; the code then fetches each page itself, screens it
like any other article and lets the planner and writer take it from there."""
import datetime
import json

from .. import config
from ..edition import ledger
from ..ingest import screen, extract_text, store, fetch
from ..ingest.text import canonical_url, domain, plain
from . import prompts
from .providers import AIError, Budget, get, parse_json


def add_candidates(date, log=print, n=18):
    cfg = config.load()
    if cfg.ai.provider != 'claude':
        raise AIError('research mode needs the Claude provider')
    p = get(Budget(cfg.ai.max_cost_usd * 0.4), cfg)
    recent = [t for e in ledger()['editions'][-14:] for t in e.get('titles', e.get('topics', []))][-120:]
    cats = cfg.editorial.category_names()
    favs = cfg.editorial.favorite_names()
    since = date - datetime.timedelta(days=cfg.editorial.recency_days)
    prompt = f"""Find {n} candidate stories for tomorrow's edition ({date:%A, %B %d, %Y}).

Wanted: recent events and discoveries (published since {since:%B %d, %Y}) that are important, may affect the
reader's life, or are uplifting, interesting or surprising. Spread them across many of these categories:
{', '.join(cats)}. The reader's favorites: {', '.join(favs) or 'none set'}. Science, nature and space are always welcome.
Not wanted: partisan or current-events news, crime, disasters, sensational or overtly negative stories.
Prefer original sources (journals' news pages, universities, agencies, trade press) and pages that are free to read.
Already covered recently (skip these topics): {'; '.join(recent[-60:])}

Use web search. Return JSON: {{"stories": [{{"url", "title", "category" (one of the categories above),
"published" (YYYY-MM-DD if known), "why" (one line)}}]}}. URLs must be the article pages themselves."""
    tools = [{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': cfg.ai.research_searches}]
    r = p.complete(prompts.house_style(cfg), prompt, tools=tools, max_tokens=4000)
    try:
        data = parse_json(r.text)
    except AIError:
        log('AI research: no usable list in the reply')
        return 0
    stories = data.get('stories', data) if isinstance(data, dict) else data
    con = store.connect()
    added = 0
    for s in stories if isinstance(stories, list) else []:
        url = (s.get('url') or '').strip()
        if not url.startswith('http'):
            continue
        cu = canonical_url(url)
        if con.execute('SELECT 1 FROM items WHERE url=?', (cu,)).fetchone():
            continue
        published = s.get('published') or ''
        try:
            published = datetime.datetime.fromisoformat(published[:10]).replace(tzinfo=datetime.timezone.utc).isoformat()
        except ValueError:
            published = fetch.now_iso()
        cat = s.get('category') if s.get('category') in cats else None
        con.execute("INSERT OR IGNORE INTO items(url, link, feed_url, source, title, summary, published, seen, category, license, tier, "
                    "trust, origin, meta) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cu, url, 'ai-research', domain(url), plain(s.get('title', ''))[:300], '', published, fetch.now_iso(), cat,
                     'copyrighted', 'excerpt', 1.1, 'ai', json.dumps({'why': plain(s.get('why', ''))[:300]})))
        added += 1
    con.commit()
    log(f'AI research: {added} new candidates (${p.budget.spent:.2f})')
    screen(log)
    extract_text(limit=added + 10, log=log)
    return added
