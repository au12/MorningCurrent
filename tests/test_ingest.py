import datetime

from mc.ingest import classify, score, store, text as T, tone


def test_canonical_url_drops_tracking():
    assert T.canonical_url('http://www.example.com/story/?utm_source=rss&id=7&fbclid=x') == 'https://example.com/story?id=7'
    assert T.canonical_url('https://example.com/a/amp/') == T.canonical_url('https://example.com/a')


def test_same_story():
    assert T.same_story('NASA rover finds ancient lake bed on Mars', 'Ancient lake bed found on Mars by NASA rover')
    assert not T.same_story('NASA rover finds ancient lake bed on Mars', 'Sourdough starter grows twice as fast in warm kitchens')
    a = T.simhash('Volunteers restore a historic lighthouse on the coast of Maine')
    b = T.simhash('Volunteers restore historic lighthouse on Maine coast')
    c = T.simhash('A new battery chemistry stores energy in iron and air')
    assert T.hamming(a, b) < T.hamming(a, c)


def test_sentences_keep_abbreviations_together():
    s = T.sentences('Dr. Smith met Prof. Jones in the U.S. lab. They measured 3.5 grams. It worked!')
    assert s[0].startswith('Dr. Smith met Prof. Jones') and s[-1] == 'It worked!'
    assert any('3.5 grams' in x for x in s)


def test_clean_lead_strips_press_release_preamble():
    t = T.clean_lead('WASHINGTON (AP) — Engineers in Ohio have built a bridge from recycled plastic. The bridge opened Tuesday.')
    assert t.startswith('Engineers in Ohio')


def test_tone_filter(data):
    ok, _, why = tone.check('Gunman arrested after downtown robbery')
    assert not ok and why
    assert not tone.check('Politicians clash over spending bill')[0]
    assert tone.check('Scientists map the salt flats of the Dead Sea')[0]          # allowlisted phrase
    assert tone.check('Volunteers plant ten thousand trees along the river')[0]


def test_keyword_classifier(data):
    cat, conf, method = classify.classify('Webb telescope spots a galaxy forming stars',
                                          'Astronomers using the James Webb Space Telescope found a young galaxy.')
    assert cat == 'Space' and conf > 0 and method == 'keywords'
    cat, _, _ = classify.classify('A sourdough bakery reopens', 'The farm-to-table bakery uses heritage wheat grown nearby.',
                                  default='Food & Farming')
    assert cat == 'Food & Farming'


def test_scoring_prefers_fresh_trusted_items(data):
    now = datetime.datetime.now(datetime.timezone.utc)
    base = dict(title='Engineers build a quieter wind turbine', summary='A new blade shape cuts noise by half.', category='Engineering & Energy',
                tier='full', trust=1.0, words=900, status='candidate', source='Test', cat_score=0.8, tone=0.3, image=None, meta={})
    fresh = score.score(dict(base, published=now.isoformat()))
    stale = score.score(dict(base, published=(now - datetime.timedelta(days=12)).isoformat()))
    assert fresh > stale > 0


def test_store_roundtrip(data):
    con = store.connect()
    con.execute("INSERT INTO items(url, link, source, title, status, blocks, meta) VALUES (?,?,?,?,?,?,?)",
                ('https://example.com/x', 'https://example.com/x', 'Test', 'Hello', 'candidate', '[["p", "Hi."]]', '{"a": 1}'))
    con.commit()
    it = store.items("url='https://example.com/x'")[0]
    assert it['blocks'] == [['p', 'Hi.']] and it['meta'] == {'a': 1}
    store.update(it['id'], status='pinned', meta={'b': 2})
    it = store.items('id=?', (it['id'],))[0]
    assert it['status'] == 'pinned' and it['meta'] == {'b': 2}
