import json
import os

from mc import config, secrets


def test_morning_press_data_is_upgraded(data):
    ed = data / 'editions'
    (ed / 'reading').mkdir(parents=True)
    (ed / '2026-11-10.pdf').write_bytes(b'%PDF-1.4 booklet')
    (ed / '2026-11-10.json').write_text(json.dumps({'title': 'No. 14', 'pages': 8, 'prints': []}))
    (ed / 'reading' / '2026-11-10.pdf').write_bytes(b'%PDF-1.4 reading')
    (data / 'settings.json').write_text(json.dumps({'enabled': True, 'cups_server': 'print.lan:631', 'printer': 'Brother',
                                                    'weekday_time': '06:15', 'weekend_time': '08:30'}))
    (data / '.admin_password').write_text('old-pw\n')
    from mc.web import migrate
    assert migrate.run(log=lambda m: None) == 3
    d = ed / '2026-11-10'
    assert (d / 'booklet.pdf').exists() and (d / 'reading.pdf').exists() and (d / 'meta.json').exists()
    assert not (ed / 'reading').exists()
    cfg = config.load(use_cache=False)
    assert cfg.printer.cups_server == 'print.lan:631' and cfg.printer.printer == 'Brother'
    assert cfg.schedule.print_enabled and cfg.schedule.weekday_time == '06:15'
    assert not cfg.schedule.build_enabled and cfg.setup_complete
    assert secrets.get('admin_password') == 'old-pw'
    assert os.path.exists(data / 'settings.json.migrated')
    assert migrate.run(log=lambda m: None) == 0                   # idempotent
