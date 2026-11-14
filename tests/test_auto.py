"""The automatic writer: license rules, the planner and AI verification (no network, no browser)."""
import pytest

from mc import config, profiles
from mc.ai import providers, verify, writer
from mc.auto import assemble, select
from mc.ingest import store
from mc.ingest.text import plain

from synth import article, row

CATS = ['Space', 'Nature & Wildlife', 'Engineering & Energy', 'Food & Farming', 'Art & Design', 'Physics & Chemistry',
        'Places & Maps', 'Music & Sound', 'Robotics', 'Human Origins & Archaeology']


def corpus(n=70, **kw):
    out = []
    for i in range(n):
        words = [2600, 1400, 1100, 900, 700, 500, 300][i % 7]
        out.append(row(i, CATS[i % len(CATS)], f'Source {i % 14}', words=words, **kw))
    return out


def test_open_license_story_is_trimmable(data):
    it = row(1, 'Space', 'NASA', words=1200)
    st = assemble.story(it, 'x', 'feature', 600)
    assert st['trim'] and st['sents'] and 'Excerpted' in st['license_note']
    assert not st.get('verbatim')
    assert sum(len(plain(b[1]).split()) for b in st['blocks'] if b[0] == 'p') <= 600 * 1.5 + 40 + 120


def test_no_derivatives_story_is_never_reworded(data):
    it = row(2, 'Space', 'The Conversation', words=1200, tier='verbatim', license='cc-by-nd')
    st = assemble.story(it, 'x', 'feature', 600)
    assert st['verbatim'] and st['excerpt_note']
    assert all(not isinstance(x, list) for x in st['trim'])            # whole paragraphs only, from the end
    assert not any(b[0] == 'quote' for b in st['blocks'])                # no added pull quote
    source = '\n\n'.join(article(2, 1200)['paras'])
    for b in st['blocks']:
        if b[0] in ('p', 'dropcap'):
            assert plain(b[1]) in source


def test_planner_fills_every_page(data):
    cfg = config.activate()
    rows = corpus()
    p = select.plan(rows=rows, log=lambda m: None)
    assert p.pages == cfg.format.pages
    assert len(p.units) == config.units_needed(p.pages, cfg.format.sections, p.deep_dive)
    B = profiles.budgets(profiles.get(cfg.format.profile))
    assert p.lead['words'] >= min(200, 0.55 * B['lead'])
    picked = [p.lead] + ([p.spread] if p.spread else []) + [it for _, its in p.units for it in its]
    assert len({it['id'] for it in picked}) == len(picked)
    per_source = {}
    for it in picked + p.wonders + p.reserve + ([p.sidebar] if p.sidebar else []):
        per_source[it['source']] = per_source.get(it['source'], 0) + 1
    assert max(per_source.values()) <= 3
    cats = {}
    for _, its in p.units:
        for it in its:
            cats[it['category']] = cats.get(it['category'], 0) + 1
    assert max(cats.values()) <= cfg.editorial.max_same_category + 1     # a split counts each story


def test_planner_needs_full_text_without_ai(data):
    rows = corpus(tier='excerpt', license='copyrighted')
    with pytest.raises(select.PlanError):
        select.plan(rows=rows, log=lambda m: None)


def test_verifier():
    src = 'The bridge is 412 meters long and took 3 years to build. "It sings in the wind," said engineer Maria Lopez.'
    good = dict(headline='A 412-meter bridge', deck='', blocks=[['p', 'The span runs 412 meters.'],
                                                             ['quote', 'It sings in the wind', 'Maria Lopez']])
    assert verify.check_story(good, src) == []
    bad = dict(headline='A bridge', deck='', blocks=[['p', 'The span runs 512 meters. It opened in spring.'],
                                                  ['quote', 'It hums all night', 'Maria Lopez']])
    errs = verify.check_story(bad, src)
    assert any('512' in e for e in errs) and any('quote' in e for e in errs)
    removed = verify.strip_unverified(bad, src)
    assert removed == 2
    assert [plain(b[1]) for b in bad['blocks']] == ['It opened in spring.']


class FakeProvider:
    """Stands in for Claude: returns canned JSON and counts calls."""
    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    def complete(self, system, prompt, schema=None, max_tokens=4000, tools=None):
        self.calls += 1
        return providers.Result(data=self.replies.pop(0) if len(self.replies) > 1 else self.replies[0])


def _base(data_dir):
    a = article(5, 900)
    con = store.connect()
    con.execute('INSERT INTO items(url, link, source, title, summary, text, words, status, tier, license, category) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                ('https://example.org/a', 'https://example.org/a', 'Example News', a['title'], a['summary'], '\n\n'.join(a['paras']),
                 900, 'candidate', 'excerpt', 'copyrighted', 'Nature & Wildlife'))
    con.commit()
    it = store.items("url='https://example.org/a'")[0]
    st = assemble.story(dict(it, blocks=[dict(type='p', text=p) for p in a['paras']]), 'heron', 'feature', 600)
    return st, a


def _story_json(text, quote=None):
    blocks = [{'type': 'p', 'text': t} for t in text]
    if quote:
        blocks.insert(1, {'type': 'quote', 'text': quote[0], 'speaker': quote[1]})
    return {'headline': 'Volunteers learn from a patient heron colony', 'deck': 'A careful survey', 'kicker_topic': 'Field notes',
            'blocks': blocks}


def test_ai_writer_accepts_verified_copy(data):
    base, a = _base(data)
    p = FakeProvider([_story_json(['Volunteers have spent the year watching a heron colony.', 'They kept careful records.'] * 4)])
    st, how = writer.write_one(p, base, 'feature', 120, log=lambda m: None)
    assert how == 'verified' and st['ai'] and p.calls == 1
    assert st['src'][0] == base['src'][0]


def test_ai_writer_cuts_invented_numbers(data):
    base, a = _base(data)
    invented = _story_json(['The colony has exactly 98765 nests.'] + ['Volunteers kept careful records of the birds.'] * 6)
    p = FakeProvider([invented])
    st, how = writer.write_one(p, base, 'feature', 60, log=lambda m: None)
    assert p.calls == 2                                         # one revision request, then cutting
    assert how.startswith('verified after cutting')
    assert not any('98765' in plain(b[1]) for b in st['blocks'] if b[0] in ('p', 'dropcap'))


def test_budget_stops_spending():
    b = providers.Budget(0.05)
    b.add(0.04)
    b.check()
    b.add(0.02)
    with pytest.raises(providers.BudgetExceeded):
        b.check()
