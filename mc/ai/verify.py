"""Check AI-written copy against the text it was written from.

Every quote must appear word for word in the source (punctuation and curly quotes aside) and its
speaker's name must appear there too; every number must appear in the source. Small integers (0-12,
often written as words), and years that appear in the source, are allowed. The check is deliberately
strict: a failure sends the story back for revision, and an unfixable sentence is dropped.
"""
import re
import unicodedata

from ..ingest.text import plain, sentences


def _norm(s):
    s = unicodedata.normalize('NFKC', plain(s)).lower()
    s = s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    return re.sub(r'\s+', ' ', s)


def _alnum(s):
    return re.sub(r'[^a-z0-9]+', ' ', _norm(s)).strip()


_NUM = re.compile(r'(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?')


def numbers(text):
    out = []
    for m in _NUM.finditer(plain(text)):
        whole = m.group(1).replace(',', '')
        out.append(whole + ('.' + m.group(2) if m.group(2) else ''))
    return out


def _num_ok(n, source_nums):
    if n in source_nums:
        return True
    try:
        v = float(n)
    except ValueError:
        return False
    if v.is_integer() and 0 <= v <= 12:
        return True
    return any(abs(v - float(s)) < 1e-9 for s in source_nums)


def check_text(text, source):
    """Problems with one piece of copy (numbers only)."""
    src_nums = set(numbers(source))
    return [f'number {n} is not in the source' for n in numbers(text) if not _num_ok(n, src_nums)]


def check_quote(quote, speaker, source):
    errs = []
    if _alnum(quote) and _alnum(quote) not in _alnum(source):
        errs.append(f'quote not found word for word in the source: "{plain(quote)[:80]}"')
    names = [w for w in re.findall(r"[A-Z][a-zA-ZÀ-ɏ'’-]+", plain(speaker))
             if w.lower() not in ('the', 'a', 'an', 'of', 'and', 'dr', 'prof', 'professor', 'director', 'chief', 'lead', 'senior')]
    if names and not any(n.lower() in _norm(source) for n in names):
        errs.append(f'speaker "{plain(speaker)}" is not named in the source')
    return errs


def check_story(st, source):
    """All problems in a rendered story dict (blocks in the paper's format)."""
    errs = []
    for field in ('headline', 'deck'):
        errs += [f'{field}: {e}' for e in check_text(st.get(field, ''), source)]
    for b in st.get('blocks', []):
        kind = b[0]
        if kind in ('p', 'dropcap', 'h4'):
            errs += check_text(b[1], source)
        elif kind == 'quote':
            errs += check_quote(b[1], b[2] if len(b) > 2 else '', source)
        elif kind == 'facts':
            for big, label in b[2]:
                errs += check_text(f'{big} {label}', source)
        elif kind == 'chart':
            for label, v in b[1].get('rows', []):
                errs += check_text(f'{label} {v}', source)
    return errs


def strip_unverified(st, source):
    """Drop sentences, quotes, facts and charts that fail the check. Returns the number of removals."""
    removed = 0
    keep = []
    src_nums = set(numbers(source))
    for b in st['blocks']:
        kind = b[0]
        if kind in ('p', 'dropcap'):
            ok = [s for s in sentences(plain(b[1])) if all(_num_ok(n, src_nums) for n in numbers(s))]
            removed += len(sentences(plain(b[1]))) - len(ok)
            if ok:
                from ..ingest.text import esc
                keep.append([kind, esc(' '.join(ok))] + list(b[2:]))
        elif kind == 'quote':
            if check_quote(b[1], b[2] if len(b) > 2 else '', source):
                removed += 1
            else:
                keep.append(b)
        elif kind in ('facts', 'chart'):
            if (kind == 'facts' and any(check_text(f'{x} {y}', source) for x, y in b[2])) or \
               (kind == 'chart' and any(check_text(f'{x} {y}', source) for x, y in b[1].get('rows', []))):
                removed += 1
            else:
                keep.append(b)
        else:
            keep.append(b)
    st['blocks'] = keep
    for field in ('headline', 'deck'):
        if check_text(st.get(field, ''), source):
            removed += 1
            if field == 'deck':
                st['deck'] = ''
    return removed
