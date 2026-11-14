"""Where things live.

Everything an installation owns (settings, editions, the ledger, the article database, caches and
build outputs) sits under one *data directory*:

    <data>/config.yaml          settings (edited in the web UI or by hand)
    <data>/secrets.json         API keys and passwords entered in the web UI (never in config.yaml)
    <data>/editions/ledger.json every edition's date, number, URLs and topics
    <data>/editions/<date>/     one edition: content, puzzles, fit state, final PDFs, QA report
    <data>/out/<date>/          scratch build output (HTML, contact sheets, QR renders)
    <data>/mc.db                article database (feeds, candidates, feedback)
    <data>/cache/               downloaded images and robots.txt files
    <data>/activity.jsonl       activity log shown on the dashboard

The data directory is, in order: $MC_DATA; /data inside the Docker image; the current directory
if it already looks like a data directory (has config.yaml or editions/); otherwise ./data.
"""
import os

PACKAGE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(PACKAGE)
BUNDLED = os.path.join(PACKAGE, 'data')          # data shipped with the code (fonts, word lists, source packs)


def _looks_like_data(d):
    return os.path.exists(os.path.join(d, 'config.yaml')) or os.path.exists(os.path.join(d, 'editions', 'ledger.json'))


def data_dir():
    d = os.environ.get('MC_DATA')
    if d:
        return os.path.abspath(d)
    if os.environ.get('MC_CONTAINER') == '1':
        return '/data'
    cwd = os.getcwd()
    if _looks_like_data(cwd):
        return cwd
    return os.path.join(cwd, 'data')


def _p(*parts):
    path = os.path.join(data_dir(), *parts)
    return path


def config_file():
    return _p('config.yaml')


def secrets_file():
    return _p('secrets.json')


def editions_dir():
    return _p('editions')


def edition_dir(date):
    return _p('editions', date)


def ledger_file():
    return _p('editions', 'ledger.json')


def out_dir(date=None):
    return _p('out', date) if date else _p('out')


def db_file():
    return _p('mc.db')


def cache_dir(*parts):
    return _p('cache', *parts)


def activity_file():
    return _p('activity.jsonl')


def jobs_dir():
    return _p('jobs')


def ensure():
    """Create the data directory skeleton (safe to call repeatedly)."""
    for d in (data_dir(), editions_dir(), out_dir(), cache_dir(), jobs_dir()):
        os.makedirs(d, exist_ok=True)
    if not os.path.exists(ledger_file()):
        import json
        with open(ledger_file(), 'w') as f:
            json.dump({'editions': []}, f, indent=1)
