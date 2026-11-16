"""Turning the paper's content into Typst source.

Edition text is stored as light inline HTML (entities such as &ldquo; plus <i>, <b>, <br>, <sup>), because
that is what writers and feeds produce. The layout engine is Typst, so every piece of text goes through
`rich()`, which emits Typst *code* that builds the same content: text becomes string literals (nothing in
the text can be read as Typst markup), tags become emph/strong/linebreak/super/sub calls.
"""
import html as _html
import re
from html.parser import HTMLParser

_TAGS = {'i': 'emph', 'em': 'emph', 'cite': 'emph', 'b': 'strong', 'strong': 'strong', 'sup': 'super', 'sub': 'sub',
         'u': 'underline', 'small': 'smallcaps'}
_VOID = {'br', 'wbr', 'img', 'hr'}


def q(s):
    """A Typst string literal."""
    s = str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', ' ')
    return f'"{s}"'


class _Conv(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.stack = [], []

    def handle_starttag(self, tag, attrs):
        if tag == 'br':
            self.out.append('#linebreak()')
            return
        if tag in _VOID:
            return
        fn = _TAGS.get(tag)
        self.stack.append(fn)
        if fn:
            self.out.append(f'#{fn}[')

    def handle_startendtag(self, tag, attrs):
        if tag == 'br':
            self.out.append('#linebreak()')

    def handle_endtag(self, tag):
        if tag in _VOID or not self.stack:
            return
        fn = self.stack.pop()
        if fn:
            self.out.append(']')

    def handle_data(self, data):
        if data:
            self.out.append('#' + q(data))

    def close(self):
        super().close()
        while self.stack:
            if self.stack.pop():
                self.out.append(']')
        return ''.join(self.out)


def rich(html):
    """Inline HTML -> a Typst content expression `[...]`."""
    if html is None:
        return '[]'
    s = str(html)
    if '<' not in s and '&' not in s:
        return f'[#{q(s)}]' if s else '[]'
    c = _Conv()
    c.feed(s)
    return '[' + c.close() + ']'


def words(html):
    """Inline HTML -> a Typst array of one content value per word (keeps italics/bold), for drop caps."""
    s = str(html or '')
    toks = re.findall(r'<[^>]+>|[^<\s]+|\s+', s)
    out, open_tags, cur = [], [], ''
    for t in toks:
        if t.startswith('<'):
            m = re.match(r'<\s*(/?)\s*([a-zA-Z0-9]+)', t)
            if m:
                closing, tag = m.group(1) == '/', m.group(2).lower()
                if tag == 'br':
                    continue
                if closing:
                    if tag in open_tags:
                        open_tags.remove(tag)
                elif tag in _TAGS:
                    open_tags.append(tag)
            continue
        if t.isspace():
            if cur:
                out.append(cur)
                cur = ''
            continue
        piece = rich(t)
        for tag in reversed(open_tags):
            piece = f'{_TAGS[tag]}({piece})'
        cur = piece if not cur else f'({cur} + {piece})'
    if cur:
        out.append(cur)
    return '(' + ', '.join(out) + (',' if len(out) == 1 else '') + ')'


def plain(html):
    """Inline HTML -> plain text."""
    return _html.unescape(re.sub(r'<[^>]+>', '', str(html or '')))


def inch(x):
    return f'{float(x):.4f}in'


def pt(x):
    return f'{float(x):.3f}pt'


def length(css):
    """'0.54in' / '12pt' / 12 (px) -> a Typst length."""
    if isinstance(css, (int, float)):
        return pt(css * 0.75)
    s = str(css).strip()
    if s.endswith(('in', 'pt', 'mm', 'cm', 'em')):
        return s
    if s.endswith('px'):
        return pt(float(s[:-2]) * 0.75)
    return pt(float(s))


def array(items):
    items = list(items)
    return '(' + ', '.join(items) + (',' if len(items) == 1 else '') + ')'


def dictionary(d):
    return '(' + ', '.join(f'{k}: {v}' for k, v in d.items()) + ')' if d else '(:)'
