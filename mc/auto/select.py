"""Plan tomorrow's paper from the scored candidates, without AI.

The planner fills the page plan in order of importance: the Deep Dive (longest strong story), the lead,
an optional page-2 sidebar, the single-page units (features for long stories, splits for two medium
ones, roundups of short items when long-form runs out), Small Wonders and reserve briefs. It follows
the editorial rules in Settings > Content: at most N story pages per category, no two neighbouring pages
in the same category, health stories capped, favourite categories preferred, the lead and Deep Dive
rotating away from the last two papers' categories, and a per-source cap. On a thin day it tries the
light page count, then the minimum, before giving up.
"""
import re
from collections import Counter

from .. import config, profiles, rules as R
from ..ingest import score as scoring, store
from . import assemble


class Plan:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _slug(text, taken):
    words = [w for w in re.findall(r'[a-z]+', text.lower()) if len(w) > 3 and w not in
             ('this', 'that', 'with', 'from', 'what', 'when', 'have', 'into', 'your', 'their', 'than', 'about', 'after', 'they')]
    base = (words[0] if words else 'story')[:12]
    s, n = base, 2
    while s in taken:
        s = f'{base}{n}'
        n += 1
    taken.add(s)
    return s


def candidates(limit=700):
    rows = store.items("status IN ('candidate','pinned','backlog')", order='score DESC', limit=limit)
    rows.sort(key=lambda it: (it['status'] != 'pinned', -(it['score'] or 0)))
    return rows


def plan(pages=None, log=print, rows=None):
    cfg = config.activate()
    prof = profiles.get(cfg.format.profile)
    B = profiles.budgets(prof)
    rows = rows if rows is not None else candidates()
    options = [pages] if pages else sorted({cfg.format.pages, cfg.format.pages_light, cfg.format.pages_min}, reverse=True)
    last_err = None
    for N in options:
        for dd in ([cfg.format.deep_dive, False] if cfg.format.deep_dive else [False]):
            try:
                p = _try(N, dd, cfg, B, rows, log)
                if p:
                    return p
            except PlanError as e:
                last_err = e
                log(f'plan: {N} pages{" with Deep Dive" if dd else ""} not possible: {e}')
    raise PlanError(str(last_err) if last_err else 'not enough candidates for any page count')


class PlanError(Exception):
    pass


def _try(N, dd, cfg, B, rows, log):
    ed = cfg.editorial
    sources = {s.name: s for s in cfg.sources.feeds}
    sections = list(cfg.format.sections)
    k = config.units_needed(N, sections, dd)
    if k < 0:
        raise PlanError(f'{len(sections)} sections do not fit {N} pages')
    if dd and config.layout_problems(config.update(cfg, {'format': {'pages': N, 'pages_light': N, 'pages_min': N, 'deep_dive': True}})):
        raise PlanError('spread does not fit')
    used, per_source, cat_pages = set(), Counter(), Counter()
    fav = set(ed.favorite_names())
    health = {c.name for c in ed.categories if c.family == 'health'}
    caps = {c.name: (c.cap if c.cap is not None else ed.max_same_category) for c in ed.categories}
    lead_recent, spread_recent, _ = scoring.recent_categories()

    def src_cap(it):
        s = sources.get(it['source'])
        return s.max_per_edition if s else 3

    def avail(it):
        return it['id'] not in used and per_source[it['source']] < src_cap(it) and it['status'] != 'killed'

    ai_writes = cfg.ai.provider != 'none' and cfg.ai.write_stories

    def story_ok(it, min_words=150):
        if not it.get('blocks') or (it['words'] or 0) < min_words:
            return False
        return it['tier'] in ('full', 'verbatim') or (ai_writes and it['tier'] == 'excerpt' and (it['words'] or 0) >= 250)

    def brief_ok(it):
        from ..ingest.text import clean_lead
        return len(clean_lead(it.get('summary') or '').split()) >= 14 or (it.get('words') or 0) >= 60

    def take(it, pages=1):
        used.add(it['id'])
        per_source[it['source']] += 1
        if pages:
            cat_pages[it['category']] += pages

    def cat_ok(it, pages=1):
        c = it['category']
        if cat_pages[c] + pages > caps.get(c, ed.max_same_category):
            return False
        if c in health and sum(cat_pages[h] for h in health) >= ed.health_max_features:
            return False
        return True

    def best(pred, prefer=None):
        pool = [it for it in rows if avail(it) and pred(it)]
        if not pool:
            return None
        if prefer:
            pool.sort(key=lambda it: -(it['score'] or 0) * prefer(it))
        return pool[0]

    # 1. Deep Dive
    spread = None
    if dd:
        spread = best(lambda it: story_ok(it, int(0.72 * B['spread'])),
                      prefer=lambda it: 0.85 if it['category'] in spread_recent else 1.0)
        if not spread:
            raise PlanError('no article long enough for the Deep Dive')
        take(spread)
    # 2. lead
    lead = best(lambda it: story_ok(it, int(0.55 * B['lead'])) and cat_ok(it),
                prefer=lambda it: (0.85 if it['category'] in lead_recent else 1.0) * (0.8 if spread and it['category'] == spread['category'] else 1.0)
                * (1.1 if it['tier'] == 'full' else 1.0))
    if not lead:
        lead = best(lambda it: story_ok(it, 200) and cat_ok(it))
    if not lead:
        raise PlanError('no full-text article for the lead (add open-licensed sources or turn on AI)')
    take(lead)
    sidebar = None
    if cfg.format.sidebar and (lead['words'] or 0) < 0.92 * B['lead']:
        sidebar = best(lambda it: (story_ok(it, 70) or brief_ok(it)) and it['category'] != lead['category'],
                       prefer=lambda it: 1.0 if (it['words'] or 0) < 2 * B['sidebar'] else 0.9)
        if sidebar:
            take(sidebar, 0)
    # 3. single-page units
    units = []
    n_feat = n_split = 0
    while len(units) < k:
        prefer = lambda it: (1.18 if it['category'] in fav and sum(cat_pages[f] for f in fav) < ed.favorites_target else 1.0)
        feat = best(lambda it: story_ok(it, int(0.68 * B['feature'])) and cat_ok(it), prefer) if 'feature' in R.ALLOWED_SHAPES else None
        pair = []
        if 'split' in R.ALLOWED_SHAPES:
            a = best(lambda it: story_ok(it, int(0.5 * B['split'])) and cat_ok(it), prefer)
            if a:
                used.add(a['id'])
                b = best(lambda it: story_ok(it, int(0.5 * B['split'])) and cat_ok(it) and it['category'] != a['category'], prefer)
                used.discard(a['id'])
                if b:
                    pair = [a, b]
        if feat and (n_feat <= n_split or not pair):
            take(feat)
            units.append(('feature', [feat]))
            n_feat += 1
        elif pair:
            for it in pair:
                take(it)
            units.append(('split', pair))
            n_split += 1
        elif 'roundup' in R.ALLOWED_SHAPES:
            items = _roundup_items(rows, avail, brief_ok, take, ed)
            if len(items) < 4:
                raise PlanError(f'only {len(units)} of {k} story pages could be filled')
            units.append(('roundup', items))
        else:
            raise PlanError(f'only {len(units)} of {k} story pages could be filled')
    units = _order(units, lead['category'])
    # 4. Small Wonders and reserve
    wonders = []
    if 'wonders' in sections:
        lo, hi = ed.wonders_count
        seen_cats = Counter()
        for it in rows:
            if len(wonders) >= hi:
                break
            if avail(it) and brief_ok(it) and seen_cats[it['category']] < 2:
                take(it, 0)
                wonders.append(it)
                seen_cats[it['category']] += 1
    reserve = []
    story_cats = [lead['category']] + [it['category'] for _, its in units for it in its]
    for it in rows:
        if len(reserve) >= ed.reserve_count:
            break
        if avail(it) and brief_ok(it) and it['category'] in story_cats:
            take(it, 0)
            reserve.append(it)
    for it in rows:
        if len(reserve) >= ed.reserve_count:
            break
        if avail(it) and brief_ok(it):
            take(it, 0)
            reserve.append(it)
    log(f'plan: {N} pp, lead {lead["category"]}, {"spread " + spread["category"] if spread else "no spread"}, '
        f'{n_feat} features, {n_split} splits, {sum(1 for u in units if u[0] == "roundup")} roundups, '
        f'{len(wonders)} wonders, {len(reserve)} reserve')
    return Plan(pages=N, deep_dive=bool(spread), lead=lead, sidebar=sidebar, spread=spread, units=units, wonders=wonders,
                reserve=reserve, budgets=B, sources=sources)


def _roundup_items(rows, avail, brief_ok, take, ed, n=7):
    fams = {c.name: c.family for c in ed.categories}
    pool = [it for it in rows if avail(it) and brief_ok(it)]
    if not pool:
        return []
    fam = Counter(fams.get(it['category'], 'culture') for it in pool[:30]).most_common(1)[0][0]
    pick = [it for it in pool if fams.get(it['category'], 'culture') == fam][:n]
    if len(pick) < 5:
        pick = pool[:n]
    for it in pick:
        take(it, 0)
    return pick


def _order(units, lead_cat):
    """Reorder units so neighbouring pages differ in category (greedy)."""
    def cats(u):
        return {it['category'] for it in u[1]} if u[0] != 'roundup' else set()
    out, rest, prev = [], list(units), {lead_cat}
    while rest:
        i = next((j for j, u in enumerate(rest) if not (cats(u) & prev)), 0)
        u = rest.pop(i)
        out.append(u)
        prev = cats(u)
    return out


ROUNDUP_TITLES = {'science': 'Science in Brief', 'tech': 'Tech & Engineering in Brief', 'health': 'Health in Brief',
                  'culture': 'Curiosities in Brief'}


def _mark(st, it):
    """Stories from copyrighted sources are only placeholders until the AI writer replaces them."""
    if it.get('tier') == 'excerpt':
        st['needs_ai'] = True
    return st


def finalize_unwritten(content):
    """Replace any copyrighted-source placeholder the AI didn't write with a short summary and QR code."""
    from ..ingest import store
    def fix(st):
        if not st or not st.get('needs_ai'):
            return st
        rows = store.items('id=?', (st.get('item_id'),))
        b = assemble.brief(rows[0], 120, credit=False) if rows else dict(text=st.get('deck', ''))
        st = dict(st, blocks=[['p', b['text']]], trim=[], sents={}, deck='')
        st.pop('needs_ai', None)
        st.pop('verbatim', None)
        return st
    content['lead'] = fix(content['lead'])
    content['sidebar'] = fix(content.get('sidebar'))
    for u in content['units']:
        for k in range(1, len(u)):
            if u[0] != 'roundup':
                u[k] = fix(u[k])
    return content


def to_content(p, date, log=print):
    """Turn a Plan into edition content (the same JSON format hand-written editions use)."""
    cfg = config.load()
    B = p.budgets
    taken = set()
    src = lambda it: p.sources.get(it['source'])
    units = []
    lead = _mark(assemble.story(p.lead, _slug(p.lead['title'], taken), 'lead', B['lead'] - (B['sidebar'] if p.sidebar else 0),
                                src(p.lead)), p.lead)
    sidebar = None
    if p.sidebar:
        if p.sidebar['tier'] in ('full', 'verbatim') and p.sidebar.get('blocks'):
            sidebar = _mark(assemble.story(p.sidebar, _slug(p.sidebar['title'], taken), 'sidebar', B['sidebar'], src(p.sidebar)),
                            p.sidebar)
            sidebar['deck'] = ''
        else:
            b = assemble.brief(p.sidebar, 90, credit=False)
            sidebar = dict(id=_slug(p.sidebar['title'], taken), category=p.sidebar['category'], kicker=assemble.kicker(p.sidebar),
                           headline=b['head'], deck='', src=[p.sidebar['link'], 'Read the full story', b.get('credit') or ''],
                           blocks=[['p', b['text']]], item_id=p.sidebar['id'], source=p.sidebar['source'], auto=True)
    teasers_left = 2
    fams = {c.name: c.family for c in cfg.editorial.categories}
    for shape, its in p.units:
        if shape == 'feature':
            units.append(['feature', _mark(assemble.story(its[0], _slug(its[0]['title'], taken), 'feature', B['feature'],
                                                          src(its[0]), teaser=teasers_left > 0), its[0])])
            teasers_left -= 1
        elif shape == 'split':
            a = _mark(assemble.story(its[0], _slug(its[0]['title'], taken), 'split', B['split'], src(its[0]),
                                     teaser=teasers_left > 0), its[0])
            b = _mark(assemble.story(its[1], _slug(its[1]['title'], taken), 'split', B['split'], src(its[1])), its[1])
            teasers_left -= 1
            units.append(['split', a, b])
        else:
            fam = Counter(fams.get(it['category'], 'culture') for it in its).most_common(1)[0][0]
            cat = Counter(it['category'] for it in its).most_common(1)[0][0]
            title = ROUNDUP_TITLES.get(fam, 'In Brief')
            n_src = len({it['source'] for it in its})
            r = assemble.roundup(_slug('brief ' + title, taken), title, [assemble.brief(it) for it in its], cat,
                                 deck=f'{len(its)} short reads from {n_src} source{"s" if n_src != 1 else ""}; scan a code to read on.')
            units.append(['roundup', r])
    spread = None
    if p.spread:
        spread = _mark(assemble.story(p.spread, _slug(p.spread['title'], taken), 'spread', B['spread'], src(p.spread),
                                      teaser=True), p.spread)
        mid = len(units) // 2 if units else 0
        units.insert(min(len(units), _spread_index(p, len(units))), ['spread', spread])
    wonders = [assemble.brief(it, 70) for it in p.wonders]
    from .filler import wikipedia_briefs
    reserve = [assemble.brief(it, 55, credit=False) for it in p.reserve]
    import datetime as _dt
    extra = wikipedia_briefs(_dt.date.fromisoformat(date))
    wiki_wonders = [x for x in extra if x['head'].startswith('From the')]
    lo, hi = cfg.editorial.wonders_count
    if 'wonders' in cfg.format.sections and len(wonders) < lo:
        need = lo - len(wonders)
        wonders += [x for x in extra if x not in wonders][:need]
    reserve += [dict(x, category=x.get('category') or 'History & Everyday Things') for x in extra if x not in wonders]
    cats = list(dict.fromkeys(w.get('category') for w in wonders if w.get('category')))
    wd = ''
    if cats:
        names = [c.lower().replace('&', '&amp;') for c in cats[:4]]
        wd = (f'Short takes on {", ".join(names[:-1])} and {names[-1]}.' if len(names) > 1 else f'Short takes on {names[0]}.')
    content = dict(lead=lead, sidebar=sidebar, units=units, wonders_deck=wd, wonders=wonders, reserve=reserve,
                   almanac=dict(src=list(R.SKY_GUIDE)), puzzles={}, meta=dict(generator='auto', items=_item_ids(p)))
    for i, w in enumerate(content['reserve']):
        w.setdefault('category', None)
    return content


def _spread_index(p, n_units):
    """Units that precede the spread so it lands on the centre pair."""
    N = p.pages
    tail = list(config.load().format.sections)
    after = N - (N // 2 + 1)
    overflow = max(0, len(tail) - after)
    n_after_units = after - (len(tail) - overflow)
    return n_units - n_after_units


def _item_ids(p):
    ids = [p.lead['id']] + ([p.sidebar['id']] if p.sidebar else []) + ([p.spread['id']] if p.spread else [])
    ids += [it['id'] for _, its in p.units for it in its] + [it['id'] for it in p.wonders] + [it['id'] for it in p.reserve]
    return ids
