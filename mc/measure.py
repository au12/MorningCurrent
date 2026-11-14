"""Render the edition HTML in headless Chromium, report how every column fits, and print PDFs.

One browser stays open for a whole build, so the fit loop can re-measure quickly. For each page the
report gives, per column region (`.cols[data-slot]`): hidden lines (text pushed past the last
column), overflow and how far down each column's content reaches (fill %), plus whether the page's
inner box overflows.
"""
import json
import os

from . import rules as R

SHRINK_JS = r"""
() => {
  // Shrink one-line elements (masthead title, sky strip) until they fit their box.
  document.querySelectorAll('[data-shrink]').forEach(el => {
    let size = parseFloat(getComputedStyle(el).fontSize), guard = 0;
    while (el.scrollWidth > el.clientWidth + 1 && size > 6 && guard++ < 80) {
      size -= 0.5; el.style.fontSize = size + 'px';
    }
  });
}
"""

MEASURE_JS = r"""
(linePx) => {
  const out = [];
  document.querySelectorAll('.page').forEach(pg => {
    const n = pg.dataset.n; const inner = pg.querySelector('.inner');
    let info = { n };
    pg.querySelectorAll('.cols').forEach((c, i) => {
      const over = c.scrollWidth > c.clientWidth + 2;
      const kids = c.querySelectorAll(':scope > *');
      const cr = c.getBoundingClientRect();
      let hid = 0; const walker = document.createTreeWalker(c, NodeFilter.SHOW_TEXT); const rg = document.createRange(); let nd;
      while ((nd = walker.nextNode())) { rg.selectNodeContents(nd); for (const r of rg.getClientRects()) { if (r.left >= cr.right - 1) hid += r.height; } }
      const nc = (getComputedStyle(c).columnCount | 0) || 1; const cw = cr.width / nc; const colFills = [];
      for (let k = 0; k < nc; k++) {
        let bot = cr.top; const L = cr.left + k * cw - 2, R = cr.left + (k + 1) * cw + 2;
        kids.forEach(el => { for (const r of el.getClientRects()) { if (r.width > 0 && r.left >= L && r.right <= R && r.bottom > bot) bot = r.bottom; } });
        colFills.push(Math.round(100 * (bot - cr.top) / cr.height));
      }
      info['cols' + i] = { slot: c.dataset.slot || '', hiddenLines: Math.round(hid / linePx), over,
                           overflowPx: c.scrollWidth - c.clientWidth, colFills, heightPx: Math.round(cr.height) };
    });
    // fixed blocks that must not spill out of their page
    info.innerOver = inner.scrollHeight > inner.clientHeight + 2 ? inner.scrollHeight - inner.clientHeight : 0;
    out.push(info);
  });
  return out;
}
"""


class Renderer:
    """with Renderer() as r: rep = r.measure(path); r.pdf(path, out)"""

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        args = ['--disable-dev-shm-usage', '--font-render-hinting=none']
        self._browser = self._pw.chromium.launch(args=args)
        self._page = self._browser.new_page()
        self._loaded = None
        return self

    def __exit__(self, *exc):
        try:
            self._browser.close()
        finally:
            self._pw.stop()

    def load(self, html_path):
        self._page.goto('file://' + os.path.abspath(html_path), wait_until='load')
        self._page.evaluate('document.fonts.ready.then(() => true)')
        self._page.evaluate(SHRINK_JS)
        self._loaded = html_path

    def measure(self, html_path, reload=True):
        if reload or self._loaded != html_path:
            self.load(html_path)
        return self._page.evaluate(MEASURE_JS, R.LINE_PX)

    def pdf(self, out_path):
        self._page.pdf(path=out_path, width=f'{R.PAGE_W}in', height=f'{R.PAGE_H}in', print_background=True,
                       prefer_css_page_size=True)
        return out_path

    def screenshot(self, out_path, full_page=True):
        self._page.screenshot(path=out_path, full_page=full_page)


def measure(html_path, pdf_path=None):
    """One-shot: render, measure and optionally write the PDF (opens and closes a browser)."""
    with Renderer() as r:
        rep = r.measure(html_path)
        if pdf_path:
            r.pdf(pdf_path)
    return rep


if __name__ == '__main__':   # python -m mc.measure page.html [out.pdf]
    import sys
    print(json.dumps(measure(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)))
