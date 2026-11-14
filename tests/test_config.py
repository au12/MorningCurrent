import os

import pytest

from mc import config, paths, secrets


def test_defaults_are_valid_and_write_nothing(data):
    cfg = config.load()
    assert cfg.format.pages == 16 and cfg.ai.provider == 'none'
    assert config.dump(cfg).strip() == '{}'
    assert not config.layout_problems(cfg)


def test_save_writes_only_what_changed(data):
    cfg = config.update(config.load(), {'paper': {'title': 'The Daily Test'}, 'format': {'pages': 12}})
    config.save(cfg)
    text = open(paths.config_file()).read()
    assert 'The Daily Test' in text
    assert 'categories' not in text and 'blocklist' not in text
    again = config.load(use_cache=False)
    assert again.paper.title == 'The Daily Test' and again.format.pages == 12


def test_page_counts_are_checked(data):
    with pytest.raises(ValueError):
        config.update(config.load(), {'format': {'pages': 10}})
    with pytest.raises(ValueError):          # 8 pages cannot hold six sections and a centre spread
        config.update(config.load(), {'format': {'pages': 8, 'pages_light': 8, 'pages_min': 8}})
    small = config.update(config.load(), {'format': {'pages': 8, 'pages_light': 8, 'pages_min': 8, 'deep_dive': False,
                                                     'sections': ['almanac', 'sudoku', 'back']}})
    assert config.units_needed(8, small.format.sections, False) == 3


def test_unknown_names_are_rejected(data):
    with pytest.raises(ValueError):
        config.update(config.load(), {'format': {'sections': ['almanac', 'horoscopes']}})
    with pytest.raises(ValueError):
        config.update(config.load(), {'format': {'profile': 'napkin'}})
    with pytest.raises(ValueError):
        config.Source(name='x', url='ftp://example.com/feed')


def test_license_tiers():
    assert config.tier_for('public-domain') == 'full'
    assert config.tier_for('cc-by') == 'full'
    assert config.tier_for('cc-by-nd') == 'verbatim'
    assert config.tier_for('copyrighted') == 'excerpt'
    s = config.Source(name='x', url='https://example.com/feed', license='cc-by', tier='headline')
    assert s.use == 'headline'


def test_default_sources_come_from_default_packs(data):
    cfg = config.load()
    packs = {p['id']: p for p in config.source_packs()}
    assert cfg.sources.feeds
    assert all(packs[s.pack].get('default') for s in cfg.sources.feeds)
    assert all(s.license in config.LICENSES for p in packs.values() for s in map(lambda x: config.Source(**x), p['sources']))


def test_secrets_file_and_environment(data, monkeypatch):
    secrets.set('push_token', 'from-file')
    assert secrets.get('push_token') == 'from-file' and secrets.source('push_token') == 'file'
    assert os.stat(paths.secrets_file()).st_mode & 0o777 == 0o600
    monkeypatch.setenv('PUSH_TOKEN', 'from-env')
    assert secrets.get('push_token') == 'from-env' and secrets.source('push_token') == 'env'
    secrets.set('push_token', '')
    monkeypatch.delenv('PUSH_TOKEN')
    assert secrets.get('push_token') == '' and secrets.source('push_token') == ''


def test_config_never_holds_secrets(data):
    secrets.set('anthropic_api_key', 'sk-ant-test')
    full = config.dump(config.load(), full=True)
    assert 'sk-ant-test' not in full and 'api_key' not in full
