#!/usr/bin/env python3
"""Make the TTF fonts the layout engine (Typst) uses from the bundled WOFF2 web fonts.

Typst reads TTF/OTF, and the web-font subsets carry confusing internal names, so each file is decompressed
and renamed: family "<Family>" for the Latin subset and "<Family> Ext" for Latin Extended (used as a fallback),
with the weight and italic flags set from the file name. Run from the repository root (needs fonttools + brotli):
    python3 scripts/make_fonts.py
"""
import glob
import os
import re

from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'mc', 'data', 'fonts')
DST = os.path.join(SRC, 'ttf')
FAMILIES = {'libre-franklin': 'MC Franklin', 'playfair-display': 'MC Playfair', 'source-serif-4': 'MC Serif',
            'unifrakturmaguntia': 'MC Fraktur'}
WEIGHT_NAMES = {400: 'Regular', 500: 'Medium', 600: 'SemiBold', 700: 'Bold', 800: 'ExtraBold', 900: 'Black'}


def main():
    os.makedirs(DST, exist_ok=True)
    for f in sorted(glob.glob(os.path.join(SRC, '*.woff2'))):
        m = re.match(r'(.+)-(latin|latin-ext)-(\d+)-(normal|italic)\.woff2$', os.path.basename(f))
        pkg, sub, w, style = m.group(1), m.group(2), int(m.group(3)), m.group(4)
        fam = FAMILIES[pkg] + (' Ext' if sub == 'latin-ext' else '')
        italic = style == 'italic'
        sname = WEIGHT_NAMES[w] + (' Italic' if italic else '')
        if sname == 'Regular Italic':
            sname = 'Italic'
        t = TTFont(f)
        t.flavor = None
        name = t['name']
        name.names = [n for n in name.names if n.nameID not in (1, 2, 3, 4, 6, 16, 17, 21, 22)]
        ps = (fam + '-' + sname).replace(' ', '')
        for nid, val in ((1, fam), (2, sname), (3, ps), (4, f'{fam} {sname}'), (6, ps), (16, fam), (17, sname)):
            name.setName(val, nid, 3, 1, 0x409)
        os2 = t['OS/2']
        os2.usWeightClass = w
        sel = os2.fsSelection & ~0b1100001          # clear italic, bold, regular
        sel |= 1 if italic else 0
        sel |= 0b100000 if (w >= 700 and not italic) else 0
        sel |= 0b1000000 if (w == 400 and not italic) else 0
        os2.fsSelection = sel
        t['head'].macStyle = (1 if w >= 700 else 0) | (2 if italic else 0)
        if 'fvar' in t:
            del t['fvar']
        t.save(os.path.join(DST, f'{pkg}-{sub}-{w}-{style}.ttf'))
    print('wrote', len(os.listdir(DST)), 'fonts to', DST)


if __name__ == '__main__':
    main()
