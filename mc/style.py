"""CSS for the paper, generated from rules (geometry, type scale, palette)."""
import os
from . import rules as R, paths

FONT_DIR = os.path.join(paths.BUNDLED, 'fonts')
_FACES = [  # (family, package, weights, italic weights)
    ('Playfair', 'playfair-display', (400, 700, 800, 900), (400, 700)),
    ('SSerif', 'source-serif-4', (400, 600, 700), (400, 600)),
    ('Franklin', 'libre-franklin', (400, 500, 600, 700, 800), ()),
    ('Fraktur', 'unifrakturmaguntia', (400,), ()),
]
_RANGES = {
    'latin': 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,'
             'U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD',
    'latin-ext': 'U+0100-02AF,U+0304,U+0308,U+0329,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,'
                 'U+2C60-2C7F,U+A720-A7FF',
}


def font_faces(url_prefix=None):
    """@font-face rules for the bundled fonts. url_prefix=None uses file:// paths (for Chromium rendering);
    the web UI passes '/static/fonts/' to serve the same files."""
    out = ''
    for fam, pkg, ws, its in _FACES:
        for style, wl in (('normal', ws), ('italic', its)):
            for w in wl:
                for sub, rng in _RANGES.items():
                    fn = f'{pkg}-{sub}-{w}-{style}.woff2'
                    if not os.path.exists(os.path.join(FONT_DIR, fn)):
                        continue
                    src = (url_prefix + fn) if url_prefix is not None else 'file://' + os.path.join(FONT_DIR, fn)
                    out += (f"@font-face{{font-family:'{fam}';src:url('{src}') format('woff2');font-weight:{w};"
                            f"font-style:{style};unicode-range:{rng};}}\n")
    return out


def _fonts():
    return font_faces()


def css():
    M, T, P, Z = R.MARGIN, R.TYPE, R.PALETTE, R.SIZES
    side = lambda a, b: f'left:{a}in;right:{b}in'
    return _fonts() + f'''
@page {{ size:{R.PAGE_W}in {R.PAGE_H}in; margin:0 }}
* {{ box-sizing:border-box }}
html,body {{ margin:0; padding:0; background:#fff; color:{P['ink']} }}
body {{ font-family:'SSerif','DejaVu Serif',Georgia,serif; font-size:{R.BODY_PT}pt; line-height:{R.BODY_LEADING}; -webkit-print-color-adjust:exact;
  print-color-adjust:exact; font-kerning:normal; font-variant-numeric:oldstyle-nums; hyphens:auto }}
.page {{ width:{R.PAGE_W}in; height:{R.PAGE_H}in; position:relative; overflow:hidden; break-after:page }}
.inner {{ position:absolute; top:{M['top']}in; bottom:{M['bottom']}in; display:flex; flex-direction:column }}
.recto .inner, .recto .rhead {{ {side(M['inner'], M['outer'])} }}
.verso .inner, .verso .rhead {{ {side(M['outer'], M['inner'])} }}
.front .inner {{ top:{M['top_front']}in }}
.rhead {{ position:absolute; top:{M['rhead']}in; font:6.6pt 'Franklin'; letter-spacing:.14em; text-transform:uppercase; display:flex;
  justify-content:space-between; border-bottom:.6pt solid {P['ink']}; padding-bottom:3pt }}
.rhead .sec {{ font-weight:800 }}
.folio {{ position:absolute; bottom:{M['folio']}in; font:700 7pt 'Franklin' }}
.recto .folio {{ right:{M['outer']}in }} .verso .folio {{ left:{M['outer']}in }}
.cols {{ column-count:2; column-gap:{R.COL_GAP}in; column-rule:.4pt solid {P['rule']}; column-fill:auto; flex:1 1 auto; min-height:0 }}
.split {{ flex:1 1 auto; min-height:0; display:grid; grid-template-columns:1fr 1fr; grid-template-rows:minmax(0,1fr) }}
.split > .cols {{ column-count:1; column-rule:0; height:100% }}
.split > .cols:first-child {{ padding-right:{R.COL_GAP/2:.3f}in }}
.split > .cols + .cols {{ padding-left:{R.COL_GAP/2:.3f}in; border-left:.4pt solid {P['rule']} }}
p {{ margin:0; text-align:justify; text-indent:1.1em; orphans:2; widows:2 }}
h4 + p, .dropcap, .noind, .src + p, .shead + p, .bhead + p {{ text-indent:0 }}
.dropcap::first-letter {{ font-family:'Playfair'; font-weight:800; float:left; font-size:34pt; line-height:.82; padding:2.5pt 3pt 0 0 }}
h1,h2,h3 {{ font-family:'Playfair'; font-weight:800; margin:0; line-height:1.02; letter-spacing:-.005em }}
h1 {{ font-size:{T['h1']}pt }} h2 {{ font-size:{T['h2']}pt }} h3 {{ font-size:{T['h3']}pt }}
h4 {{ font:800 {T['h4']}pt 'Franklin'; letter-spacing:.1em; text-transform:uppercase; margin:7pt 0 2pt; break-after:avoid }}
.kicker {{ font:800 {T['kicker']}pt 'Franklin'; letter-spacing:.18em; text-transform:uppercase; margin:0 0 3pt }}
.kicker span {{ border-bottom:1.4pt solid {P['ink']}; padding-bottom:1pt }}
.deck {{ font-family:'SSerif'; font-style:italic; font-size:{T['deck']}pt; line-height:1.28; margin:4pt 0 7pt; color:{P['dark']} }}
.headblock {{ flex:0 0 auto; margin-bottom:2pt }}
.shead {{ break-inside:avoid; break-after:avoid; margin-bottom:3pt }}
.shead h3 {{ font-size:{T['h3_split']}pt; line-height:1.04 }}
.shead .deck {{ font-size:{T['deck_split']}pt; line-height:1.26; margin:3pt 0 4pt }}
.side {{ margin-top:9pt }} .side .bhead h3 {{ margin-bottom:4pt }}
.bhead {{ break-inside:avoid; break-after:avoid }}
.rule {{ border-top:.6pt solid {P['ink']}; margin:6pt 0 }} .thick {{ border-top:2pt solid {P['ink']} }}
.spreadrule {{ border-top:3pt double {P['ink']}; margin:0 0 6pt; flex:0 0 auto }}
.src {{ display:flex; gap:6pt; align-items:center; break-inside:avoid; border-top:.6pt solid {P['ink']}; margin-top:5pt; padding-top:4pt;
  font:{T['src']}pt/1.3 'Franklin' }}
.src svg {{ flex:0 0 auto }} .src .dom {{ font-weight:600; letter-spacing:.02em }}
.pull {{ font:italic {T['pull']}pt/1.2 'Playfair'; text-align:center; margin:8pt 0; padding:6pt 2pt; border-top:1.4pt solid {P['ink']};
  border-bottom:.6pt solid {P['ink']}; break-inside:avoid }}
.pull .who {{ display:block; font:normal 6.6pt 'Franklin'; letter-spacing:.12em; text-transform:uppercase; margin-top:4pt }}
.box {{ border:.8pt solid {P['ink']}; padding:7pt 8pt; break-inside:avoid }} .box.shade {{ background:{P['shade']} }}
.boxhead {{ font:800 7.2pt 'Franklin'; letter-spacing:.16em; text-transform:uppercase; border-bottom:1.4pt solid {P['ink']};
  padding-bottom:2pt; margin-bottom:5pt }}
.fill {{ break-inside:avoid; margin-top:9pt }}
.facts {{ display:grid; grid-template-columns:repeat(4,1fr) }} .facts.two {{ grid-template-columns:repeat(2,1fr) }}
.facts div {{ padding:3pt 6pt 4pt 0; border-top:.4pt solid #999; font-size:7.6pt; line-height:1.25 }}
.facts b {{ display:block; font:900 13pt/1.05 'Playfair' }}
.chart {{ break-inside:avoid; margin:6pt 0 7pt; border-top:1.4pt solid {P['ink']}; padding-top:4pt }}
.chart .ct {{ font:800 {T['chart_title']}pt 'Franklin'; letter-spacing:.1em; text-transform:uppercase; margin-bottom:3pt }}
.chart .cs {{ font:{T['chart_note']}pt 'Franklin'; color:{P['mid']}; margin-top:2pt }}
.cont {{ font:700 6.8pt 'Franklin'; letter-spacing:.06em; text-transform:uppercase; text-align:right; margin-top:4pt }}
.mast {{ text-align:center; flex:0 0 auto }}
.title {{ font-family:'Fraktur'; font-size:{T['title']}pt; line-height:1; white-space:nowrap }}
.dateline {{ display:flex; justify-content:space-between; font:600 6.9pt 'Franklin'; letter-spacing:.1em; text-transform:uppercase;
  border-top:2pt solid {P['ink']}; border-bottom:.6pt solid {P['ink']}; padding:3pt 0; margin:4pt 0 0 }}
.skystrip {{ display:flex; justify-content:center; align-items:center; gap:5pt; font:600 {T['skystrip']}pt 'Franklin'; letter-spacing:.03em;
  text-transform:uppercase; border-bottom:.6pt solid {P['ink']}; padding:3pt 0; margin:0 0 8pt; white-space:nowrap }}
.skystrip .sep {{ color:#777; font-weight:400 }} .skystrip svg {{ flex:0 0 auto; width:12px; height:12px }}
.inside {{ flex:0 0 auto; margin-top:8pt; display:grid; grid-template-columns:repeat({Z['index_cols']},1fr); border-top:2pt solid {P['ink']};
  border-bottom:.6pt solid {P['ink']} }}
.inside div {{ padding:5pt 6pt; border-left:.4pt solid #999; font-size:7.8pt; line-height:1.22 }}
.inside div:nth-child({Z['index_cols']}n+1) {{ border-left:0; padding-left:0 }}
.inside .pg {{ font:800 6.5pt 'Franklin'; letter-spacing:.12em; text-transform:uppercase; display:block; margin-bottom:2pt }}
.inside .t {{ font:700 9.3pt/1.1 'Playfair'; display:block; margin-bottom:2pt }}
.odd {{ break-inside:avoid; margin-bottom:7pt }} .odd p {{ text-indent:0 }}
.odd h5 {{ font:800 {T['odd_head']}pt/1.08 'Playfair'; margin:0 }}
.qhead {{ display:flex; gap:6pt; align-items:center; margin-bottom:2pt }} .qhead h5 {{ flex:1 }}
.mini {{ break-inside:avoid; padding:4pt 0 5pt; border-top:.4pt solid #999 }}
.mini h5 {{ font:800 {T['brief_head']}pt 'Franklin'; letter-spacing:.06em; text-transform:uppercase; margin:0 0 1.5pt }}
.mini p {{ text-indent:0; font-size:{T['brief']}pt; line-height:1.3 }}
.note {{ font:6.8pt 'Franklin'; margin-top:3pt; text-indent:0 }}
table {{ border-collapse:collapse }}
.alm-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:9pt; flex:0 0 auto }}
.sun td {{ padding:2pt 4pt 2pt 0; font-size:8.6pt }} .sun td.v {{ font-family:'Franklin'; font-weight:700; text-align:right }}
.phi svg {{ vertical-align:-2px; margin-right:4pt }}
.cal {{ width:100% }} .cal tr {{ break-inside:avoid }}
.cal td {{ vertical-align:top; padding:3.2pt 4pt 3.2pt 0; border-bottom:.4pt solid {P['light']}; font-size:8.6pt; line-height:1.28 }}
.cal td.d {{ font:800 7pt 'Franklin'; letter-spacing:.04em; white-space:nowrap; text-transform:uppercase; width:.62in; padding-top:4pt }}
.crypt {{ font:600 12.2pt/2.25 'Franklin'; letter-spacing:.16em; text-align:left; word-spacing:.25em }}
.crypt span.w {{ display:inline-block; margin-right:.5em }}
.ptitle {{ font:900 {T['ptitle']}pt 'Playfair'; margin:0 0 1pt }}
.pinstr {{ font-size:8.5pt; font-style:italic; margin:0 0 6pt; text-indent:0; text-align:left }}
.scramble {{ font:700 10.5pt/2.1 'Franklin'; letter-spacing:.12em }}
.blank {{ display:inline-block; border-bottom:.6pt solid {P['ink']}; width:1.3in; height:11pt; margin-left:6pt }}
.ladder td {{ width:{Z['ladder_cell']}in; height:{Z['ladder_cell']*1.07:.3f}in; border:.6pt solid {P['ink']}; text-align:center; font:700 12pt 'Franklin' }}
.sdk {{ margin:4pt auto 0 }}
.sdk td {{ width:{Z['sudoku_cell']}in; height:{Z['sudoku_cell']}in; border:.5pt solid #777; text-align:center; vertical-align:middle; font:600 {Z['sudoku_cell']*32:.1f}pt 'Franklin' }}
.sdk tr:nth-child(3n+1) td {{ border-top:2pt solid {P['ink']} }} .sdk tr:last-child td {{ border-bottom:2pt solid {P['ink']} }}
.sdk td:nth-child(3n+1) {{ border-left:2pt solid {P['ink']} }} .sdk td:last-child {{ border-right:2pt solid {P['ink']} }}
.teasers {{ display:grid; grid-template-columns:repeat({Z['teaser_cols']},1fr); gap:10pt; font-size:8.5pt; line-height:1.3 }}
.xw {{ table-layout:fixed }}
.xw td {{ width:{R.CROSSWORD['cell_in']}in; min-width:{R.CROSSWORD['cell_in']}in; max-width:{R.CROSSWORD['cell_in']}in; height:{R.CROSSWORD['cell_in']}in;
  border:.8pt solid {P['ink']}; position:relative; vertical-align:top; padding:0 }}
.xw td.b {{ background:{P['ink']} }}
.xw td .num {{ position:absolute; top:1pt; left:1.5pt; font:600 6.3pt 'Franklin' }}
.xw td .let {{ display:block; text-align:center; font:700 7.5pt 'Franklin'; line-height:.2in; padding-top:1pt }}
.clues {{ column-count:2; column-gap:.22in; font-size:8.1pt; line-height:1.28; column-rule:0 }}
.clues h6 {{ font:800 7.4pt 'Franklin'; letter-spacing:.14em; margin:0 0 2pt; text-transform:uppercase; border-bottom:1.2pt solid {P['ink']} }}
.clues div {{ padding-left:1.5em; text-indent:-1.5em; margin-bottom:1pt }}
.clues b {{ font:700 8pt 'Franklin'; display:inline-block; width:1.5em; text-indent:0 }}
.notes div {{ border-bottom:.5pt solid #999; height:.27in; break-inside:avoid }}
.notesbox .boxhead {{ break-after:avoid }}
.upside {{ transform:rotate(180deg) }}
.ans {{ font-size:8pt; line-height:1.28; display:grid; grid-template-columns:auto auto 1fr; gap:12pt; align-items:start }}
.ans p {{ text-indent:0; text-align:left }}
.ans .xw td {{ width:.19in; min-width:.19in; max-width:.19in; height:.19in }} .ans .xw td .let {{ font-size:7pt; line-height:.17in; padding-top:0 }}
.ans .sdk {{ margin:0 }} .ans .sdk td {{ width:.19in; height:.19in; font-size:7.4pt; font-weight:500 }} .ans .sdk td.g {{ font-weight:800 }}
.ans h5 {{ font:800 6.8pt 'Franklin'; letter-spacing:.12em; text-transform:uppercase; margin:0 0 3pt }}
.srclist {{ font-size:7.2pt; line-height:1.32 }}
.srclist div {{ margin-bottom:2.5pt; padding-left:1.2em; text-indent:-1.2em; text-align:left }}
.srclist .u {{ font:6.4pt 'Franklin'; color:{P['mid']}; white-space:nowrap }}
.enote {{ font:italic 7.6pt/1.3 'SSerif'; color:{P['mid']}; margin-top:3pt; text-indent:0 }}
.blist {{ margin:2pt 0 4pt 1.1em; padding:0 }} .blist li {{ margin:0 0 1.5pt }}
.photo {{ margin:3pt 0 6pt; break-inside:avoid }}
.photo img {{ display:block; width:100%; max-height:2.3in; object-fit:cover; filter:grayscale(1) contrast(1.05) }}
.photo figcaption {{ font:{T['src']}pt/1.3 'Franklin'; color:{P['mid']}; margin-top:2pt }}
.photo figcaption span {{ color:{P['grey']}; text-transform:uppercase; letter-spacing:.06em; font-size:{T['src']*0.9:.1f}pt }}
.srcl {{ font:{T['src']}pt/1.25 'Franklin'; color:{P['mid']}; margin-top:1pt }}
.logic {{ flex:1 1 auto; min-height:0; display:grid; grid-template-columns:1fr 1fr; gap:12pt 16pt; align-content:start }}
.logic .lp.wide {{ grid-column:1 / -1 }}
.lp .ptitle {{ font-size:{T['ptitle']*0.82:.1f}pt }}
.lgrid {{ border-collapse:collapse; margin:3pt 0 4pt; table-layout:fixed }}
.lgrid td {{ width:{Z['logic_cell']}in; height:{Z['logic_cell']}in; border:.6pt solid #888; text-align:center; vertical-align:middle;
  font:600 {Z['logic_cell']*26:.1f}pt 'Franklin'; position:relative; padding:0 }}
.lgrid td .cage {{ position:absolute; top:1pt; left:1.5pt; font:700 {max(5.5, Z['logic_cell']*14):.1f}pt 'Franklin'; line-height:1 }}
.lgrid.small td {{ width:{Z['logic_cell']*0.8:.2f}in; height:{Z['logic_cell']*0.8:.2f}in; font-size:{Z['logic_cell']*21:.1f}pt }}
.lgrid td.k {{ background:{P['ink']}; color:#fff; font-size:{max(5.5, Z['logic_cell']*13):.1f}pt; font-weight:700 }}
.lgrid td.k .dn {{ position:absolute; left:2pt; bottom:1pt }} .lgrid td.k .ac {{ position:absolute; right:2pt; top:1pt }}
.lgrid td.k.diag {{ background:linear-gradient(to top right, {P['ink']} 49%, #777 50%, {P['ink']} 51%) }}
.fut td {{ border:0; width:auto; height:auto }}
.fut td.c {{ width:{Z['logic_cell']}in; height:{Z['logic_cell']}in; border:.8pt solid {P['ink']} }}
.fut td.s {{ font:700 9pt 'Franklin'; color:{P['dark']}; padding:0 1pt }}
.ws td {{ width:{Z['logic_cell']*0.62:.2f}in; height:{Z['logic_cell']*0.62:.2f}in; border:0; font:600 {Z['logic_cell']*20:.1f}pt 'Franklin' }}
.wslist {{ font:600 7.6pt/1.5 'Franklin'; letter-spacing:.06em; columns:4; margin-top:2pt }}
.non td {{ width:{Z['logic_cell']*0.55:.2f}in; height:{Z['logic_cell']*0.55:.2f}in; border:.4pt solid #999 }}
.non td.h {{ border:0; font:600 6.4pt/1.05 'Franklin'; text-align:right; padding-right:2pt; vertical-align:middle; width:auto }}
.non td.v {{ border:0; font:600 6.4pt/1.05 'Franklin'; text-align:center; vertical-align:bottom; height:auto }}
.non tr td:nth-child(5n+2) {{ border-left:1pt solid {P['ink']} }} .non tr:nth-child(5n+2) td.c {{ border-top:1pt solid {P['ink']} }}
.ans .lgrid td {{ width:.16in; height:.16in; font-size:6.4pt; font-weight:500 }} .ans .lgrid td .cage {{ display:none }}
.ans .mini {{ border:0; padding:0 }}
.cols[data-space="1"] > p + p, .cols[data-space="1"] .side p + p {{ margin-top:0.5pt }}
.cols[data-space="1"] h4 {{ margin-top:7.9pt }} .cols[data-space="1"] .mini, .cols[data-space="1"] .odd {{ margin-top:0.9pt }}
.cols[data-space="2"] > p + p, .cols[data-space="2"] .side p + p {{ margin-top:1.0pt }}
.cols[data-space="2"] h4 {{ margin-top:8.8pt }} .cols[data-space="2"] .mini, .cols[data-space="2"] .odd {{ margin-top:1.8pt }}
.cols[data-space="3"] > p + p, .cols[data-space="3"] .side p + p {{ margin-top:1.5pt }}
.cols[data-space="3"] h4 {{ margin-top:9.7pt }} .cols[data-space="3"] .mini, .cols[data-space="3"] .odd {{ margin-top:2.7pt }}
.cols[data-space="4"] > p + p, .cols[data-space="4"] .side p + p {{ margin-top:2.0pt }}
.cols[data-space="4"] h4 {{ margin-top:10.6pt }} .cols[data-space="4"] .mini, .cols[data-space="4"] .odd {{ margin-top:3.6pt }}
.cols[data-space="5"] > p + p, .cols[data-space="5"] .side p + p {{ margin-top:2.5pt }}
.cols[data-space="5"] h4 {{ margin-top:11.5pt }} .cols[data-space="5"] .mini, .cols[data-space="5"] .odd {{ margin-top:4.5pt }}
.cols[data-space="6"] > p + p, .cols[data-space="6"] .side p + p {{ margin-top:3.0pt }}
.cols[data-space="6"] h4 {{ margin-top:12.4pt }} .cols[data-space="6"] .mini, .cols[data-space="6"] .odd {{ margin-top:5.4pt }}
'''
