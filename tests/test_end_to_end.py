"""Whole papers, laid out and printed to PDF with headless Chromium. Slow (about a minute each)."""
import datetime
import json
import os
import shutil
from pathlib import Path

import pytest

from conftest import ROOT, write_config
from synth import entry

pytestmark = pytest.mark.slow

FEEDS = [('Test Space Desk', 'Space', 'public-domain'), ('Test Nature Desk', 'Nature & Wildlife', 'public-domain'),
         ('Test Engineering Desk', 'Engineering & Energy', 'cc-by'), ('Test Food Desk', 'Food & Farming', 'cc-by'),
         ('Test Places Desk', 'Places & Maps', 'public-domain'), ('Test Art Desk', 'Art & Design', 'cc-by'),
         ('Test Music Desk', 'Music & Sound', 'public-domain'), ('Test Robot Desk', 'Robotics', 'cc-by')]


def test_paper_from_feeds_without_ai(data):
    """Feed entries -> screening -> planner -> automatic writer -> puzzles -> layout -> QA -> PDFs."""
    lines = ['editorial:', '  filler_wikipedia: false', 'sources:', '  feeds:']
    for i, (name, cat, lic) in enumerate(FEEDS):
        lines += [f'  - name: {name}', f'    url: https://example.org/feed{i}.xml', f'    category: {cat}', f'    license: {lic}',
                  '    fetch_full_text: false', '    max_per_edition: 4']
    cfg = write_config('\n'.join(lines) + '\n')
    from mc import ingest
    from mc.ingest import store
    from mc.pipeline import make
    n = 0
    for k, src in enumerate(cfg.sources.feeds):
        entries = [entry(k * 10 + j, words=[2400, 1300, 1000, 800, 650, 450, 300, 200][j], seed=k) for j in range(8)]
        n += ingest.add_entries(src, entries, log=lambda m: None)
    assert n == 64
    cands, rejected = ingest.screen(log=lambda m: None)
    assert cands > 40
    store.kv_set('last_ingest', {'at': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    date = '2026-11-16'
    res = make(date, deliver=False, log=lambda m: None)
    assert res['ok'], res
    assert not res['errors']
    d = Path(data) / 'editions' / date
    assert (d / 'booklet.pdf').exists() and (d / 'reading.pdf').exists()
    content = json.load(open(d / 'edition.json'))
    assert content['meta']['generator'] == 'auto'
    used = store.items("status='used'")
    assert used and all(it['used_in'] == date for it in used)


def test_archived_hand_written_edition_still_builds(data):
    """A hand-written edition (edition.py, No. 18 of the original household paper) builds and passes QA."""
    src = ROOT / 'tests' / 'fixtures' / '2026-11-14'
    shutil.copy(ROOT / 'tests' / 'fixtures' / 'config.yaml', Path(data) / 'config.yaml')
    from mc import config
    config._cache.update(mtime=None, path=None, cfg=None)
    config.activate()
    dst = Path(data) / 'editions' / '2026-11-14'
    dst.mkdir(parents=True)
    for name in ('edition.py', 'puzzles.json', 'fit.json'):
        if (src / name).exists():
            shutil.copy(src / name, dst / name)
    shutil.copy(ROOT / 'tests' / 'fixtures' / 'ledger.json', Path(data) / 'editions' / 'ledger.json')
    from mc.build import build
    res = build('2026-11-14', log=lambda m: None)
    assert res['ok'] and not res['errors'], res
    assert os.path.exists(Path(data) / 'out' / '2026-11-14' / 'booklet.pdf')
