"""Dictionary helpers for the puzzles: definitions (WordNet), pronunciations (CMU Pronouncing Dictionary),
respellings ("pro-NUN-see-AY-shun"), antonym pairs and word-frequency checks.

WordNet and CMUdict are read through NLTK. Their data is downloaded once (`python3 -m mc.words download`,
done in the Docker image at build time). Without it, the puzzles fall back to simpler choices.
"""
import os
import re
import sys
from functools import lru_cache

NLTK_PACKAGES = ('wordnet', 'cmudict')


def data_dir():
    return os.environ.get('NLTK_DATA') or os.path.expanduser('~/nltk_data')


def download():
    import nltk
    os.environ.setdefault('NLTK_ALLOW_PROXIED_URLOPEN', '1')   # fixed nltk.org URLs; needed behind a corporate proxy
    try:
        import nltk.pathsec
        nltk.pathsec.ALLOW_PROXIED_FETCH = True
    except Exception:  # noqa: BLE001
        pass
    ok = True
    for p in NLTK_PACKAGES:
        ok &= bool(nltk.download(p, download_dir=data_dir(), quiet=True))
    return ok


@lru_cache(maxsize=1)
def wordnet():
    try:
        from nltk.corpus import wordnet as wn
        wn.ensure_loaded()
        return wn
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=1)
def cmu():
    try:
        from nltk.corpus import cmudict
        return cmudict.dict()
    except Exception:  # noqa: BLE001
        return {}


def zipf(w):
    from wordfreq import zipf_frequency
    return zipf_frequency(w.lower(), 'en')


# ------------------------------------------------------------------ definitions
POS_LABEL = {'n': 'noun', 'v': 'verb', 'a': 'adjective', 's': 'adjective', 'r': 'adverb'}


def _good_synsets(word, pos=None):
    wn = wordnet()
    if not wn:
        return []
    out = []
    for idx, s in enumerate(wn.synsets(word, pos=pos)):
        if s.instance_hypernyms():
            continue                    # a named person, place or thing
        names = [l.name() for l in s.lemmas()]
        if word.lower() not in [n.lower() for n in names]:
            continue                    # only an inflected form maps here
        if any(n == word.lower() for n in names) or not any(n[0].isupper() for n in names if n.lower() == word.lower()):
            count = sum(l.count() for l in s.lemmas() if l.name().lower() == word.lower())
            out.append((-count, idx, s))
    return [s for _, _, s in sorted(out, key=lambda t: (t[0], t[1]))]


def _gloss_ok(gloss, word):
    stem = word.lower()[:max(4, len(word) - 2)]
    return stem not in gloss.lower()


def definition(word, pos=None, max_words=12):
    """(part of speech, short gloss) for the word's most common ordinary sense, or None."""
    for s in _good_synsets(word, pos):
        g = s.definition().split(';')[0].strip()
        g = re.sub(r'\s*\([^)]*\)', '', g).strip()
        if not g or not _gloss_ok(g, word):
            continue
        w = g.split()
        if len(w) > max_words:
            g = ' '.join(w[:max_words]).rstrip(',;:') + '…'
        return POS_LABEL.get(s.pos(), 'noun'), g[:1].upper() + g[1:]
    return None


def lemma_of(word):
    wn = wordnet()
    if not wn:
        return None
    for pos in ('n', 'v', 'a', 'r'):
        m = wn.morphy(word.lower(), pos)
        if m and m != word.lower():
            return m, pos
    return None


def _short_gloss(word, pos=None, max_words=9):
    """The gloss of the word's most common usable sense, trimmed for a crossword clue."""
    for s in _good_synsets(word, pos)[:3]:
        g = re.sub(r'\s*\([^)]*\)', '', s.definition().split(';')[0]).strip()
        if not g or not _gloss_ok(g, word):
            continue
        if len(g.split()) > max_words:
            short = None
            for sep in (',', ' especially ', ' usually ', ' typically ', ' with ', ' that ', ' which ', ' in ', ' of '):
                cut = g.split(sep)[0].strip()
                if 3 <= len(cut.split()) <= max_words:
                    short = cut
                    break
            g = short or ' '.join(g.split()[:max_words]).rstrip(',;:') + '\u2026'
        return g[:1].upper() + g[1:]
    return None


def clue(word):
    """A plain dictionary clue for a crossword answer (None if WordNet doesn't know it well enough)."""
    w = word.lower()
    g = _short_gloss(w)
    if g:
        return g
    base = lemma_of(w)
    if base:
        b, pos = base
        g = _short_gloss(b, pos)
        if g and _gloss_ok(g, w):
            for cond, tag in ((pos == 'n' and w.endswith('s'), 'plural'), (pos == 'v' and w.endswith('ed'), 'past tense'),
                              (pos == 'v' and w.endswith('ing'), '-ing form'), (pos == 'v' and w.endswith('s'), 'present tense'),
                              (pos == 'a' and w.endswith('er'), 'comparative'), (pos == 'a' and w.endswith('est'), 'superlative')):
                if cond:
                    return f'{g} ({tag})'
    return None


def is_proper_only(word):
    wn = wordnet()
    if not wn:
        return False
    ss = wn.synsets(word)
    return bool(ss) and all(s.instance_hypernyms() or all(l.name()[0].isupper() for l in s.lemmas()) for s in ss)


# ------------------------------------------------------------------ pronunciation
_V = {'AA': 'ah', 'AE': 'a', 'AH': 'uh', 'AO': 'aw', 'AW': 'ow', 'AY': 'y', 'EH': 'eh', 'ER': 'ur', 'EY': 'ay', 'IH': 'ih',
      'IY': 'ee', 'OW': 'oh', 'OY': 'oy', 'UH': 'uu', 'UW': 'oo'}
_C = {'B': 'b', 'CH': 'ch', 'D': 'd', 'DH': 'th', 'F': 'f', 'G': 'g', 'HH': 'h', 'JH': 'j', 'K': 'k', 'L': 'l', 'M': 'm',
      'N': 'n', 'NG': 'ng', 'P': 'p', 'R': 'r', 'S': 's', 'SH': 'sh', 'T': 't', 'TH': 'th', 'V': 'v', 'W': 'w', 'Y': 'y',
      'Z': 'z', 'ZH': 'zh'}
_ONSETS = {('S', 'T', 'R'), ('S', 'P', 'R'), ('S', 'K', 'R'), ('S', 'P', 'L'), ('S', 'T'), ('S', 'P'), ('S', 'K'), ('S', 'M'),
           ('S', 'N'), ('S', 'L'), ('S', 'W'), ('P', 'R'), ('B', 'R'), ('T', 'R'), ('D', 'R'), ('K', 'R'), ('G', 'R'), ('F', 'R'),
           ('TH', 'R'), ('SH', 'R'), ('P', 'L'), ('B', 'L'), ('K', 'L'), ('G', 'L'), ('F', 'L'), ('S', 'K', 'W'), ('K', 'W'),
           ('T', 'W'), ('D', 'W'), ('G', 'W'), ('P', 'Y'), ('B', 'Y'), ('K', 'Y'), ('F', 'Y'), ('M', 'Y'), ('HH', 'Y'), ('V', 'Y')}


def respell(word):
    """A readable respelling with the stressed syllable in capitals, e.g. 'pro-NUN-see-AY-shun', or None."""
    prons = cmu().get(word.lower())
    if not prons:
        return None
    ph = prons[0]
    nuclei = [i for i, p in enumerate(ph) if p[-1].isdigit()]
    if not nuclei:
        return None
    sylls, start = [], 0
    for k, v in enumerate(nuclei):
        if k + 1 < len(nuclei):
            cons = ph[v + 1:nuclei[k + 1]]
            # maximal onset: give the next syllable the longest legal cluster
            split = len(cons)
            for j in range(len(cons) + 1):
                tail = tuple(cons[j:])
                if len(tail) <= 1 or tail in _ONSETS:
                    split = j
                    break
            if len(cons) == 1:
                split = 0
            end = v + 1 + split
        else:
            end = len(ph)
        sylls.append(ph[start:end])
        start = end
    out = []
    for syl in sylls:
        s, stress = '', False
        for p in syl:
            if p[-1].isdigit():
                base = p[:-1]
                stress = p[-1] == '1'
                v = _V.get(base, base.lower())
                if base == 'AY' and syl[-1] == p:
                    v = 'eye' if len(syl) == 1 else 'y'
                if base == 'AH' and p[-1] == '0':
                    v = 'uh'
                s += v
            else:
                s += _C.get(p, p.lower())
        out.append(s.upper() if stress and len(sylls) > 1 else s)
    return '-'.join(out)


# ------------------------------------------------------------------ word lists
@lru_cache(maxsize=1)
def antonym_pairs():
    """Pairs of common words of equal length that are WordNet antonyms (for themed word ladders)."""
    wn = wordnet()
    pairs = set()
    if wn:
        for pos in ('a', 'n', 'v'):
            for s in wn.all_synsets(pos):
                for l in s.lemmas():
                    a = l.name()
                    for ant in l.antonyms():
                        b = ant.name()
                        if a.isalpha() and b.isalpha() and len(a) == len(b) and 3 <= len(a) <= 5 and a.islower() and b.islower():
                            pairs.add(tuple(sorted((a, b))))
    return sorted(pairs)


if __name__ == '__main__':
    if sys.argv[1:] == ['download']:
        print('ok' if download() else 'download failed')
    else:
        for w in sys.argv[1:]:
            print(w, definition(w), respell(w), clue(w))
