import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SECRET_ENV = ('ADMIN_PASSWORD', 'PUSH_TOKEN', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'SMTP_PASSWORD', 'REMOTE_TOKEN',
              'SESSION_SECRET', 'PRESS_URL', 'PRESS_TOKEN')


@pytest.fixture
def data(tmp_path, monkeypatch):
    """A fresh, empty data directory (settings at their defaults) for one test."""
    monkeypatch.setenv('MC_DATA', str(tmp_path))
    monkeypatch.delenv('MC_CONTAINER', raising=False)
    for k in SECRET_ENV:
        monkeypatch.delenv(k, raising=False)
    from mc import config
    config._cache.update(mtime=None, path=None, cfg=None)
    config.activate()
    yield tmp_path
    config._cache.update(mtime=None, path=None, cfg=None)


def write_config(text):
    from mc import config, paths
    with open(paths.config_file(), 'w') as f:
        f.write(text)
    config._cache.update(mtime=None, path=None, cfg=None)
    return config.activate()
