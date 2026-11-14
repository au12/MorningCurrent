"""Rewrite-only mode: the code picks and fetches tonight's stories; the model writes each one to the
house style from the fetched text; the verifier checks every quote and number against that text.

A story that fails verification goes back once with the problems listed; whatever still fails is cut
sentence by sentence. If too little survives, or the budget runs out, the story keeps its automatic
version (for open-licensed sources) or becomes a short summary with a QR code (for copyrighted ones),
so AI trouble never stops the paper.
"""
from .. import config, profiles
from ..ingest import store
from ..ingest.text import esc, plain, word_count
from ..auto import assemble
from . import prompts, verify
from .providers import AIError, Budget, BudgetExceeded, get


def _source_text(item_id, limit=14000):
    rows = store.items('id=?', (item_id,)) if item_id else []
    if not rows:
        return None, None
    it = rows[0]
    text = it.get('text') or ''
    if word_count(text) < 120:
        return it, None
    return it, text[:limit]


def to_story(data, base, role, category, source_name):
    """Model JSON -> the paper's story dict (escaped; ids, sources and categories kept from the plan)."""
    blocks = []
    for b in data.get('blocks', []):
        t = b.get('type')
        if t == 'p' and b.get('text', '').strip():
            blocks.append(['p', esc(plain(b['text']))])
        elif t == 'h4' and b.get('text', '').strip():
            blocks.append(['h4', esc(plain(b['text']))])
        elif t == 'quote' and b.get('text', '').strip() and b.get('speaker', '').strip():
            blocks.append(['quote', esc(plain(b['text']).strip('"“” ')), esc(plain(b['speaker']))])
        elif t == 'facts' and b.get('items'):
            items = [[esc(plain(x['value'])), esc(plain(x['label']))] for x in b['items'][:4] if x.get('value') and x.get('label')]
            if len(items) >= 2:
                blocks.append(['facts', esc(plain(b.get('title') or 'By the numbers')), items])
        elif t == 'bars' and b.get('items'):
            rows = [[esc(plain(x['label']))[:28], float(x['number'])] for x in b['items'][:7]
                    if x.get('label') and isinstance(x.get('number'), (int, float))]
            if len(rows) >= 2:
                blocks.append(['chart', dict(kind='bars', title=esc(plain(b.get('title') or '')), rows=rows,
                                             note=f'Source: {esc(source_name)}.')])
        elif t == 'list' and b.get('items'):
            blocks.append(['list', [esc(plain(x.get('label') or x.get('value') or '')) for x in b['items'][:8]]])
    while blocks and blocks[0][0] != 'p':      # a story opens with a paragraph
        blocks.append(blocks.pop(0)) if blocks[0][0] in ('facts', 'chart') else blocks.pop(0)
    if not blocks:
        raise AIError('empty story')
    if role == 'lead':
        blocks[0][0] = 'dropcap'
    topic = esc(plain(data.get('kicker_topic') or ''))
    st = dict(base)
    for k in ('trim', 'sents', 'verbatim', 'excerpt_note', 'license_note', 'needs_ai'):
        st.pop(k, None)
    st.update(kicker=f'{esc(category)} &middot; {topic}' if topic else base.get('kicker', esc(category)),
              headline=esc(plain(data.get('headline') or '')) or base['headline'], deck=esc(plain(data.get('deck') or '')),
              blocks=blocks, ai=True)
    if role == 'lead' and data.get('cont_head'):
        st['cont_head'] = esc(plain(data['cont_head']))
    if base.get('teaser') and data.get('teaser_title'):
        st['teaser'] = [esc(plain(data['teaser_title'])), esc(plain(data.get('teaser_hook') or ''))]
    st['src'] = [base['src'][0], 'Read the source', base['src'][2] if len(base['src']) > 2 else '']
    return assemble.add_trim(st)


def write_one(p, base, role, words, log=print):
    it, text = _source_text(base.get('item_id'))
    if not text:
        return None, 'no source text'
    sysmsg = prompts.house_style()
    prompt = prompts.story_prompt(role, words, base['category'], it, text, base['id'])
    errs = []
    for attempt in range(2):
        r = p.complete(sysmsg, prompt if not errs else prompt + '\n\n' + prompts.revise_prompt(errs),
                       schema=prompts.STORY_SCHEMA, max_tokens=4000 if role in ('lead', 'spread') else 2500)
        st = to_story(r.data or {}, base, role, base['category'], assemble.source_name(it))
        errs = verify.check_story(st, text)
        if not errs:
            return st, 'verified'
        log(f'  {base["id"]}: {len(errs)} problems ({errs[0]}); ' + ('revising' if attempt == 0 else 'cutting them'))
    removed = verify.strip_unverified(st, text)
    body = sum(word_count(plain(b[1])) for b in st['blocks'] if b[0] in ('p', 'dropcap'))
    if body < 0.4 * words:
        return None, f'too little left after removing {removed} unverified pieces'
    return assemble.add_trim(st), f'verified after cutting {removed}'


def _summary_story(base, it):
    """Last resort for a copyrighted source the model couldn't write: headline, summary, QR."""
    b = assemble.brief(it, 120, credit=False)
    st = dict(base, blocks=[['p', b['text']]], deck='', trim=[], sents={})
    st.pop('needs_ai', None)
    return st


def rewrite(content, plan, date, log=print):
    cfg = config.load()
    budget = Budget(cfg.ai.max_cost_usd)
    p = get(budget, cfg)
    if p is None:
        return content
    B = profiles.budgets(profiles.get(cfg.format.profile))
    jobs = [('lead', content['lead'], B['lead'] - (B['sidebar'] if content.get('sidebar') else 0))]
    if content.get('sidebar') and content['sidebar'].get('item_id'):
        jobs.append(('sidebar', content['sidebar'], B['sidebar']))
    for u in content['units']:
        if u[0] in ('feature', 'split', 'spread'):
            for st in u[1:]:
                jobs.append((u[0], st, B[u[0]]))
    done = 0
    for role, base, words in jobs:
        try:
            st, how = write_one(p, base, role, words, log)
        except BudgetExceeded as e:
            log(f'AI: {e}; the rest of the paper is written automatically')
            st, how = None, 'budget'
            break
        except AIError as e:
            st, how = None, str(e)
        if st:
            _replace(content, base, st)
            done += 1
            log(f'AI wrote {base["id"]} ({role}): {how}')
        else:
            log(f'AI kept the automatic {base["id"]} ({role}): {how}')
    # anything still waiting for AI (copyrighted sources) becomes a short summary
    for role, base, words in jobs:
        cur = _find(content, base['id'])
        if cur is not None and cur.get('needs_ai'):
            it, _ = _source_text(cur.get('item_id'))
            if it:
                _replace(content, cur, _summary_story(cur, it))
    content['meta']['ai'] = dict(budget.summary(), stories=done, provider=cfg.ai.provider, model=cfg.ai.model, mode=cfg.ai.mode)
    if done >= max(1, len(jobs) // 2):
        content['meta']['generator'] = 'ai'
    log(f'AI: {done}/{len(jobs)} stories, ${budget.spent:.2f} of ${budget.limit:.2f}')
    return content


def _find(content, sid):
    if content['lead']['id'] == sid:
        return content['lead']
    if content.get('sidebar') and content['sidebar']['id'] == sid:
        return content['sidebar']
    for u in content['units']:
        for st in u[1:]:
            if st.get('id') == sid:
                return st
    return None


def _replace(content, old, new):
    if content['lead'] is old or content['lead']['id'] == old['id']:
        content['lead'] = new
        return
    if content.get('sidebar') and content['sidebar']['id'] == old['id']:
        content['sidebar'] = new
        return
    for u in content['units']:
        for k in range(1, len(u)):
            if u[k].get('id') == old['id']:
                u[k] = new
                return
