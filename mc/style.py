"""The paper's look for the layout engine: the Typst library (mc/paper.typ) plus the active profile's geometry
and type scale as a Typst dictionary `P`. Also the @font-face rules the web UI uses for the same fonts."""
import os

from . import paths, rules as R

FONT_DIR = os.path.join(paths.BUNDLED, 'fonts')
TTF_DIR = os.path.join(FONT_DIR, 'ttf')
LIB = os.path.join(paths.PACKAGE, 'paper.typ')
_FACES = [  # (family, package, weights, italic weights) for the web UI
    ('Playfair', 'playfair-display', (400, 700, 800, 900), (400, 700)),
    ('SSerif', 'source-serif-4', (400, 600, 700), (400, 600)),
    ('Franklin', 'libre-franklin', (400, 500, 600, 700, 800), ()),
    ('Fraktur', 'unifrakturmaguntia', (400,), ()),
]


def font_faces(url_prefix='/fonts/'):
    out = ''
    for fam, pkg, ws, its in _FACES:
        for style, wl in (('normal', ws), ('italic', its)):
            for w in wl:
                fn = f'{pkg}-latin-{w}-{style}.woff2'
                if os.path.exists(os.path.join(FONT_DIR, fn)):
                    out += (f"@font-face{{font-family:'{fam}';src:url('{url_prefix}{fn}') format('woff2');font-weight:{w};"
                            f"font-style:{style}}}\n")
    return out


def _val(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, dict):
        return '(' + ', '.join(f'{k}: {_val(x)}' for k, x in v.items()) + ')'
    from .ty import q
    return q(v)


def params():
    M = R.MARGIN
    d = dict(title=R.TITLE, pw=R.PAGE_W, ph=R.PAGE_H, **{f'm-{k.replace("_", "-")}': v for k, v in M.items()},
             gap=R.COL_GAP, body=R.BODY_PT, leading=R.BODY_LEADING, T=R.TYPE, Z=R.SIZES, **R.PALETTE,
             **{'photo-max': 2.3, 'cal-day': 0.62})
    return '#let P = ' + _val(d) + '\n'


def source():
    """The Typst preamble every edition starts with."""
    with open(LIB) as f:
        return params() + f.read()
