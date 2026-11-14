"""Turn article HTML into clean, structured text: paragraphs, subheads, block quotes, lists and images.

Pages fetched from the web go through trafilatura (which finds the article among menus, ads and
comments); full-text feed content (content:encoded) is already the article body and is parsed
directly. The result is plain text in a list of blocks; nothing from the page survives as markup.
"""
import re

from lxml import etree, html as lhtml

from .text import clean_lead, plain, is_boilerplate, word_count

STOP_HEADS = re.compile(r'(?i)^(media contacts?|contacts?|press contacts?|for more information|more information|learn more|'
                        r'related (stories|articles|links|content)|share( this)?|details|about (the|this|us)|resources|'
                        r'references|further reading|footnotes?|keep exploring|discover more|explore more|editor.?s note)')
THIRD_PARTY = re.compile(r'(?i)(\b(esa|eso|jaxa|csa|getty|shutterstock|ap photo|reuters|afp|istock|alamy|dreamstime|unsplash|'
                         r'wikimedia|flickr)\b|©|\(c\))')
PUBLIC = re.compile(r'(?i)\b(nasa|noaa|usgs|nsf|nist|usda|fws|u\.s\. fish|national park service|nps|national archives|jpl)\b')
CREDIT_LABEL = re.compile(r'(?i)(credit|courtesy|photo|image|illustration)s?\s*(:|by\b)')
TAIL_JUNK = re.compile(r'(?i)(this article (is|was) republished|originally published|appeared first on|is a (professor|lecturer|'
                       r'researcher|postdoc|phd)|disclosure statement|receives funding|does not work for, consult)')


TERMINAL = ('.', '!', '?', '\u201d', '"', '\u2019', "'", ')', '\u2026')


def _clean_blocks(blocks):
    out = []
    seen_long = False
    for b in blocks:
        if b['type'] in ('p', 'quote'):
            b = dict(b, text=clean_lead(b['text']) if not out else b['text'])
            t = b['text'].rstrip()
            if t and not t.endswith(TERMINAL):
                continue                       # captions, cut-off fragments, button labels
            if not seen_long and len(t.split()) < 12:
                continue                       # captions and credits before the article starts
            if len(t.split()) >= 25:
                seen_long = True
        if b['type'] == 'h' and STOP_HEADS.match(b['text']):
            break
        if b['type'] in ('p', 'quote'):
            t = b['text']
            if is_boilerplate(t) or TAIL_JUNK.search(t[:300]) or re.match(r'(?i)^(read more|related|see also)\b', t):
                continue
            if re.match(r'(?i)^(credit|image|photo|caption)\b', t) and len(t) < 200:
                continue
        if b['type'] == 'h' and (len(b['text']) > 120 or not b['text']):
            continue
        out.append(b)
    while out and out[-1]['type'] == 'h':     # never end on a subhead
        out.pop()
    return out


def _from_fragment(frag):
    """Parse article-body HTML (feed content) into blocks."""
    try:
        root = lhtml.fragment_fromstring(frag, create_parent='div')
    except (etree.ParserError, ValueError):
        return [], []
    for bad in root.xpath('.//script|.//style|.//iframe|.//noscript|.//form|.//button|.//svg|.//nav|.//aside'):
        bad.drop_tree()
    blocks, images = [], []

    def walk(el):
        tag = el.tag if isinstance(el.tag, str) else ''
        tag = tag.lower()
        if tag in ('p',):
            t = plain(lhtml.tostring(el, encoding='unicode'))
            if t:
                blocks.append(dict(type='p', text=t))
            for img in el.xpath('.//img'):
                _img(img, None)
        elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            t = plain(el.text_content())
            if t:
                blocks.append(dict(type='h', text=t))
        elif tag == 'blockquote':
            t = plain(el.text_content())
            if t and not el.xpath('.//iframe') and 'twitter' not in (el.get('class') or ''):
                blocks.append(dict(type='quote', text=t))
        elif tag in ('ul', 'ol'):
            items = [plain(li.text_content()) for li in el.xpath('./li')]
            items = [i for i in items if i]
            if items:
                blocks.append(dict(type='list', items=items))
        elif tag == 'figure':
            cap = el.xpath('.//figcaption')
            caption = plain(cap[0].text_content()) if cap else ''
            for img in el.xpath('.//img')[:1]:
                _img(img, caption)
        elif tag == 'img':
            _img(el, None)
        else:
            if el.text and el.text.strip() and tag in ('div', 'section', 'article', 'span'):
                t = plain(el.text)
                if len(t) > 60:
                    blocks.append(dict(type='p', text=t))
            for ch in el:
                walk(ch)

    def _img(img, caption):
        src = img.get('src') or img.get('data-src') or ''
        if not src.startswith('http') or re.search(r'(pixel|tracker|counter|1x1|spacer|\.gif$)', src):
            return
        w = img.get('width')
        if w and w.isdigit() and int(w) < 300:
            return
        images.append(dict(src=src, caption=caption or plain(img.get('alt') or ''), credit=''))
    walk(root)
    return blocks, images


def _from_trafilatura_xml(xml):
    blocks, images = [], []
    try:
        root = etree.fromstring(xml.encode() if isinstance(xml, str) else xml)
    except etree.XMLSyntaxError:
        return blocks, images, {}
    meta = {k: root.get(k) for k in ('title', 'author', 'date', 'sitename', 'image', 'license') if root.get(k)}
    main = root.find('main')
    if main is None:
        return blocks, images, meta
    for el in main:
        tag = el.tag
        text = plain(etree.tostring(el, encoding='unicode', method='text') if tag != 'list' else '')
        if tag == 'head':
            if text:
                blocks.append(dict(type='h', text=text))
        elif tag == 'p':
            if text:
                blocks.append(dict(type='p', text=text))
        elif tag == 'quote':
            if text:
                blocks.append(dict(type='quote', text=text))
        elif tag == 'list':
            items = [plain(etree.tostring(i, encoding='unicode', method='text')) for i in el.findall('item')]
            items = [i for i in items if i]
            if items:
                blocks.append(dict(type='list', items=items))
        elif tag == 'graphic':
            src = el.get('src', '')
            if src.startswith('http'):
                images.append(dict(src=src, caption=plain(el.get('alt') or el.get('title') or ''), credit=''))
    return blocks, images, meta


def from_html(page_html, url=None, fragment=False):
    """Returns dict(blocks, images, words, text, meta)."""
    meta = {}
    if fragment:
        blocks, images = _from_fragment(page_html)
        if word_count(' '.join(b.get('text', '') for b in blocks)) > 400 and re.search(r'(?i)breadcrumb|<nav|class="[^"]*nav', page_html[:20000]):
            fragment = False                   # a whole page pasted into the feed: let trafilatura find the article
    if not fragment:
        import trafilatura
        xml = trafilatura.extract(page_html, url=url, output_format='xml', include_comments=False, include_tables=False,
                                  include_images=True, include_formatting=False, include_links=False,
                                  favor_precision=True, with_metadata=True, deduplicate=True)
        blocks, images, meta = _from_trafilatura_xml(xml) if xml else ([], [], {})
    blocks = _clean_blocks(blocks)
    paras = [b['text'] for b in blocks if b['type'] in ('p', 'quote')]
    text = '\n\n'.join(paras)
    return dict(blocks=blocks, images=images, words=word_count(text), text=text, meta=meta)


def credit_ok(credit_or_caption):
    """False when an image caption/credit points at someone other than a US public agency
    (another space agency, a photographer, a wire service or a stock library)."""
    t = credit_or_caption or ''
    if THIRD_PARTY.search(t):
        return False
    if CREDIT_LABEL.search(t) and not PUBLIC.search(t):
        return False
    return True
