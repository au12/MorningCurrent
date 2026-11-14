"""Lay out the edition with Typst, report how every column fits, and write the PDF.

Typst compiles a whole paper in a fraction of a second, so the fit loop can re-measure as often as it likes.
The templates leave invisible markers (see `mk` in mc/paper.typ) at the start of every page, the top and
bottom of every column region and the start and end of every block in it. From their positions the report
gives, for each region: how much content runs past its bottom (hidden lines), how far down each column's
content reaches (fill %), and for each page whether anything runs past the bottom margin (innerOver).
The report has the same shape the browser-based measurer produced, so the fitter is unchanged.
"""
import json
import math
import os

from . import rules as R, style


class LayoutError(RuntimeError):
    pass


def _compile_args():
    return dict(font_paths=[style.TTF_DIR], root='/')


def report(markers):
    """Marker positions -> [{n, cols0: {slot, hiddenLines, over, overflowPx, colFills, heightPx}, ..., innerOver}]."""
    pitch = R.BODY_PT * R.BODY_LEADING
    gap = R.COL_GAP * 72
    bottom_pt = (R.PAGE_H - R.MARGIN['bottom']) * 72
    pages, region, ends, blocks = {}, {}, {}, {}
    for m in markers:
        parts = m['id'].split('|')
        kind = parts[0]
        if kind == 'pg':
            pages[int(parts[1])] = dict(pg=m['pg'], end=None)
        elif kind == 'pe':
            pages.setdefault(int(parts[1]), dict(pg=m['pg']))['end'] = m
        elif kind == 'rs':
            region[parts[1]] = dict(m, n=int(parts[2]), w=float(parts[3]))
        elif kind == 're':
            ends[parts[1]] = m
        elif kind in ('s', 'e'):
            blocks.setdefault(parts[1], {}).setdefault(int(parts[2]), {})[kind] = m
    out = {n: {'n': n} for n in pages}
    phys_to_n = {v['pg']: n for n, v in pages.items()}
    for n, v in pages.items():
        e = v.get('end')
        over = 0
        if e is not None:
            if e['pg'] != v['pg']:
                over = 9999
            else:
                over = max(0, e['y'] - bottom_pt)
        out[n]['innerOver'] = round(over * 96 / 72)
    counters = {}
    for slot, rs in region.items():
        if slot.startswith('_'):
            continue
        re_ = ends.get(slot)
        n = phys_to_n.get(rs['pg'])
        if n is None or re_ is None:
            continue
        top, bot, left = rs['y'], re_['y'], rs['x']
        ncol = rs['n']
        colw = (rs['w'] - gap) / 2 if ncol == 2 else rs['w']

        def col(p):
            if ncol == 1:
                return 0
            return 1 if p['x'] >= left + colw + gap / 2 - 0.5 else 0
        bl = blocks.get(slot, {})
        lowest = [None] * ncol
        full = [False] * ncol
        overflow = 0.0
        for i, se in bl.items():
            e = se.get('e')
            s = se.get('s')
            if e is None:
                continue
            if e['pg'] != rs['pg']:
                overflow = max(overflow, 9999)
                continue
            k = col(e)
            end_y = e['y']
            if s is not None and s['pg'] == rs['pg'] and col(s) == k and e['y'] < s['y']:
                end_y = s['y'] + pitch          # an end marker can land above its block's start when the block overflows
            lowest[k] = end_y if lowest[k] is None else max(lowest[k], end_y)
            if s is not None and s['pg'] == rs['pg'] and col(s) < k:
                for j in range(col(s), k):
                    full[j] = True
            overflow = max(overflow, end_y - bot)
        h = max(1.0, bot - top)
        fills = []
        for k in range(ncol):
            if full[k]:
                fills.append(100)
            elif lowest[k] is None:
                fills.append(0)
            else:
                fills.append(max(0, min(100, round(100 * (lowest[k] - top) / h))))
        hidden = math.ceil((overflow - 0.5) / pitch) if overflow > 0.5 else 0
        k = counters.get(n, 0)
        counters[n] = k + 1
        out[n][f'cols{k}'] = dict(slot=slot, hiddenLines=hidden, over=hidden > 0, overflowPx=round(max(0, overflow) * 96 / 72),
                                  colFills=fills, heightPx=round(h * 96 / 72))
    return [out[n] for n in sorted(out)]


class Renderer:
    """with Renderer() as r: rep = r.measure(path_to_typ); r.pdf(out_path)"""

    def __enter__(self):
        self._pdf = None
        return self

    def __exit__(self, *exc):
        return False

    def compile(self, path):
        import typst
        try:
            pdf = typst.compile(path, **_compile_args())
            markers = json.loads(typst.query(path, '<mk>', field='value', **_compile_args()))
        except Exception as e:  # noqa: BLE001
            diag = getattr(e, 'diagnostic', '') or str(e)
            lines = [ln[:300] for ln in str(diag).splitlines()[:8]]
            raise LayoutError('layout failed: ' + '\n'.join(lines)) from e
        self._pdf = pdf
        return markers

    def measure(self, path, reload=True):
        return report(self.compile(path))

    def pdf(self, out_path):
        with open(out_path, 'wb') as f:
            f.write(self._pdf)
        return out_path


def measure(path, pdf_path=None):
    """One-shot: lay out, measure and optionally write the PDF."""
    with Renderer() as r:
        rep = r.measure(path)
        if pdf_path:
            r.pdf(pdf_path)
    return rep


if __name__ == '__main__':   # python -m mc.measure edition.typ [out.pdf]
    import sys
    print(json.dumps(measure(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)))
