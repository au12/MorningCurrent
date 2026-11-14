#!/usr/bin/env python3
"""Render the app icon (icon.png and the web UI's icons) from the SVG below.

Needs Playwright's Chromium (pip install playwright && playwright install chromium) and Pillow.
Run from the repository root: python3 scripts/make_icon.py
"""
import os
import tempfile

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, 'mc', 'data', 'fonts')
SVG = """<svg id="s" xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <defs>
    <clipPath id="paper"><rect x="76" y="64" width="360" height="384" rx="10"/></clipPath>
  </defs>
  <rect x="0" y="0" width="512" height="512" rx="112" fill="#1b1916"/>
  <!-- the page -->
  <rect x="76" y="64" width="360" height="384" rx="10" fill="#f6f1e7"/>
  <g clip-path="url(#paper)">
    <!-- sun rising over the current -->
    <circle cx="256" cy="372" r="74" fill="#c8452f"/>
    <rect x="76" y="372" width="360" height="90" fill="#f6f1e7"/>
    <g fill="none" stroke="#1b1916" stroke-width="13" stroke-linecap="round">
      <path d="M56 382 q 26 -18 52 0 t 52 0 t 52 0 t 52 0 t 52 0 t 52 0 t 52 0 t 52 0"/>
      <path d="M56 416 q 26 -18 52 0 t 52 0 t 52 0 t 52 0 t 52 0 t 52 0 t 52 0 t 52 0"/>
    </g>
  </g>
  <!-- masthead -->
  <text x="256" y="226" text-anchor="middle" font-family="F" font-size="196" fill="#1b1916">M</text>
  <rect x="106" y="252" width="300" height="6" fill="#1b1916"/>
  <rect x="106" y="264" width="300" height="2.5" fill="#1b1916"/>
</svg>"""

PAGE = """<!doctype html><html><head><style>
@font-face{font-family:F;src:url(file://%s/unifrakturmaguntia-latin-400-normal.woff2)}
html,body{margin:0;background:transparent}</style></head><body>%s</body></html>"""


def main():
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, 'icon.html')
        with open(page, 'w') as f:
            f.write(PAGE % (FONTS, SVG))
        big = os.path.join(tmp, 'icon-1024.png')
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={'width': 512, 'height': 512}, device_scale_factor=2)
            pg.goto('file://' + page)
            pg.wait_for_timeout(400)
            pg.locator('#s').screenshot(path=big, omit_background=True)
            b.close()
        im = Image.open(big).convert('RGBA')
        static = os.path.join(ROOT, 'mc', 'web', 'static')
        im.resize((512, 512), Image.LANCZOS).save(os.path.join(ROOT, 'icon.png'), optimize=True)
        for n in (512, 192, 180):
            im.resize((n, n), Image.LANCZOS).save(os.path.join(static, f'icon-{n}.png'), optimize=True)
        im.resize((48, 48), Image.LANCZOS).save(os.path.join(static, 'favicon.ico'), sizes=[(16, 16), (32, 32), (48, 48)])
    print('wrote icon.png and mc/web/static/icon-*.png, favicon.ico')


if __name__ == '__main__':
    main()
