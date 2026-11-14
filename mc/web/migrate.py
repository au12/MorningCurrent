"""Bring a Morning Press data folder (the earlier print-server container) into the new layout, once:

  /data/editions/<date>.pdf          -> /data/editions/<date>/booklet.pdf
  /data/editions/reading/<date>.pdf  -> /data/editions/<date>/reading.pdf
  /data/editions/<date>.json         -> /data/editions/<date>/meta.json
  /data/settings.json                -> printer and print-schedule settings in config.yaml
  /data/.admin_password, .session_secret -> secrets.json (unless set in the environment)

A migrated server keeps doing what Morning Press did: it receives editions over the push API and prints
them on schedule. Its own nightly build stays off (Settings > Schedule & delivery turns it on), so it never
competes with whatever was pushing editions to it.
"""
import json
import os
import re
import shutil

from .. import config, paths, secrets

DATE = re.compile(r'^(\d{4}-\d{2}-\d{2})\.(pdf|json)$')


def run(log=print):
    root = paths.editions_dir()
    moved = 0
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            m = DATE.match(name)
            if not m:
                continue
            d, ext = m.groups()
            dst_dir = os.path.join(root, d)
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, 'booklet.pdf' if ext == 'pdf' else 'meta.json')
            if not os.path.exists(dst):
                shutil.move(os.path.join(root, name), dst)
                moved += 1
        rd = os.path.join(root, 'reading')
        if os.path.isdir(rd):
            for name in os.listdir(rd):
                m = DATE.match(name)
                if m and m.group(2) == 'pdf':
                    dst = os.path.join(root, m.group(1), 'reading.pdf')
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    if not os.path.exists(dst):
                        shutil.move(os.path.join(rd, name), dst)
                        moved += 1
            if not os.listdir(rd):
                os.rmdir(rd)
    old = os.path.join(paths.data_dir(), 'settings.json')
    if os.path.exists(old):
        try:
            s = json.load(open(old))
            cfg = config.load()
            patch = {'printer': {k: s[k] for k in ('cups_server', 'printer', 'copies', 'sides', 'media', 'extra_options') if k in s},
                     'schedule': {k: s[k] for k in ('weekday_enabled', 'weekday_time', 'weekend_enabled', 'weekend_time',
                                                    'pause_until', 'missing_policy', 'keep_days') if k in s}}
            patch['schedule']['print_enabled'] = bool(s.get('enabled'))
            patch['schedule']['build_enabled'] = False
            patch['setup_complete'] = True
            config.save(config.update(cfg, patch))
            os.rename(old, old + '.migrated')
            log('migrated Morning Press settings into config.yaml (nightly building is off until you turn it on)')
            from . import state
            state.activity('system', 'Upgraded from Morning Press: editions and print settings kept. Nightly building is off; '
                                     'turn it on in Settings > Schedule & delivery when this server should make the paper itself.')
        except Exception as e:  # noqa: BLE001
            log(f'could not migrate settings.json: {e}')
    for name, key in (('.admin_password', 'admin_password'), ('.session_secret', 'session_secret')):
        p = os.path.join(paths.data_dir(), name)
        if os.path.exists(p) and not secrets.get(key):
            secrets.set(key, open(p).read().strip())
    if moved:
        log(f'moved {moved} Morning Press file(s) into the new edition folders')
    return moved
