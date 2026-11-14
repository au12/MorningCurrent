"""Command line for The Morning Current. Run `python3 -m mc <command>`.

Making a paper
  make [date] [--no-build] [--pages N]   the whole nightly job: fetch feeds, pick and write stories
                                          (with AI if configured), puzzles, build, QA, publish, deliver
  ingest                                  fetch every enabled feed into the article database
  candidates [date]                       show tonight's scored candidates and the planned line-up
  build <date> [--lenient]                render, auto-fit, PDFs, booklet, QR check, contact sheets, QA
  publish <date>                          store the built PDFs with the edition (for printing and the reader)
  record <date> "topic; topic; ..."      add the edition to the ledger
  deliver <date>                          upload to a remote server (delivery.remote.url / $PRESS_URL, $PRESS_TOKEN)

Writing an edition by hand (see docs/layout.md)
  new <date> [--json]                     start editions/<date>/edition.py (or .json) from the template
  crossword <date>                        fill a crossword on a pattern unlike recent editions'; prints candidates
  ladder <from> <to>                      shortest word ladder between two words
  sky <date>                              print the computed sky calendar
  convert <date|all>                      turn edition.py files into edition.json

Running the server
  serve [--host H] [--port P]             web UI, public reader, scheduler and push API
  config [show|check|init|path]           show, validate or create config.yaml
  sources [list|test URL]                 list configured feeds or test one

The data directory is $MC_DATA, else the current directory if it holds config.yaml or editions/,
else ./data (see mc/paths.py).
"""
import datetime
import json
import os
import shutil
import sys


def _date(a, i=0):
    from . import config
    return a[i] if len(a) > i and not a[i].startswith('-') else config.today().isoformat()


def main(argv):
    if len(argv) < 2 or argv[1] in ('-h', '--help', 'help'):
        print(__doc__)
        return 0 if len(argv) >= 2 else 1
    cmd, a = argv[1], argv[2:]
    from . import config, paths
    if cmd == 'config' and a[:1] == ['init']:
        if os.path.exists(paths.config_file()):
            print('exists:', paths.config_file())
            return 1
        print('wrote', config.save(config.Config()))
        return 0
    try:
        cfg = config.activate()
    except Exception as e:  # noqa: BLE001
        print(f'config error in {paths.config_file()}: {e}')
        return 2
    paths.ensure()
    if cmd == 'new':
        d = paths.edition_dir(a[0])
        os.makedirs(d, exist_ok=True)
        if '--json' in a:
            dst = os.path.join(d, 'edition.json')
            src = os.path.join(paths.BUNDLED, 'template_edition.json')
        else:
            dst = os.path.join(d, 'edition.py')
            src = os.path.join(paths.PACKAGE, 'template_edition.py')
        if os.path.exists(dst):
            print('exists:', dst)
            return 1
        shutil.copy(src, dst)
        print('created', dst)
    elif cmd == 'crossword':
        from . import puzzles as P
        root = paths.editions_dir()
        recent = sorted(x for x in os.listdir(root) if x < a[0] and os.path.exists(os.path.join(root, x, 'puzzles.json')))[-5:]
        avoid = []
        for x in recent:
            pz = json.load(open(os.path.join(root, x, 'puzzles.json')))
            if 'crossword' in pz:
                avoid.append(P.mask(pz['crossword']['grid']))
        pat, grids = P.fill_crossword(avoid=avoid, extra_ban=a[1:])
        print('pattern', '/'.join(pat) if pat else None)
        for g in grids:
            _, ac, dn = P.entries(g)
            print(json.dumps(g))
            print('  across:', ' '.join(w for _, w in ac))
            print('  down:  ', ' '.join(w for _, w in dn))
    elif cmd == 'ladder':
        from . import puzzles as P
        print(P.find_ladder(a[0], a[1]))
    elif cmd == 'sky':
        from . import almanac as A
        d = datetime.date.fromisoformat(_date(a))
        for r in A.sky_rows(d):
            print('*' if r.get('star') else ' ', r['label'], '|', r['text'])
    elif cmd == 'build':
        from .build import build
        res = build(a[0], strict='--lenient' not in a)
        return 0 if res['ok'] else 2
    elif cmd == 'publish':
        from .build import publish
        print(json.dumps(publish(a[0]), indent=1)[:2000])
    elif cmd == 'record':
        from .build import record
        record(a[0], [t.strip() for t in a[1].split(';') if t.strip()])
        print('ledger updated')
    elif cmd == 'deliver':
        from .build import deliver
        deliver(a[0])
    elif cmd == 'convert':
        from .edition import load_legacy_module, save_content
        root = paths.editions_dir()
        dates = sorted(x for x in os.listdir(root) if os.path.exists(os.path.join(root, x, 'edition.py'))) if a[0] == 'all' else [a[0]]
        for d in dates:
            src = os.path.join(root, d, 'edition.py')
            save_content(os.path.join(root, d), load_legacy_module(src))
            print('converted', d)
    elif cmd == 'make':
        from .pipeline import make
        pages = int(a[a.index('--pages') + 1]) if '--pages' in a else None
        res = make(_date(a), build='--no-build' not in a, pages=pages, deliver='--no-deliver' not in a)
        return 0 if res.get('ok') else 2
    elif cmd == 'ingest':
        from .ingest import run
        print(json.dumps(run(log=print), indent=1, default=str))
    elif cmd == 'candidates':
        from .pipeline import preview
        preview(_date(a))
    elif cmd == 'serve':
        import uvicorn
        host = a[a.index('--host') + 1] if '--host' in a else '0.0.0.0'
        port = int(a[a.index('--port') + 1]) if '--port' in a else int(os.environ.get('PORT', 8080))
        uvicorn.run('mc.web.app:app', host=host, port=port, proxy_headers=True, forwarded_allow_ips='*')
    elif cmd == 'config':
        sub = a[0] if a else 'show'
        if sub == 'path':
            print(paths.config_file())
        elif sub == 'check':
            problems = config.layout_problems(cfg)
            print('ok' if not problems else '\n'.join(problems))
        else:
            print(config.dump(cfg))
    elif cmd == 'sources':
        from .ingest import fetch
        if a[:1] == ['test']:
            print(json.dumps(fetch.test_feed(a[1]), indent=1, default=str))
        else:
            for s in cfg.sources.feeds:
                print(f'{"on " if s.enabled else "off"} {s.use:9} {s.name:40} {s.url}')
    else:
        print(__doc__)
        return 1
    return 0


def cli():
    sys.exit(main(['morning-current'] + sys.argv[1:]))


if __name__ == '__main__':
    sys.exit(main(sys.argv))
