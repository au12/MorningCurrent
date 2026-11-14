"""AI help with the puzzles: crossword clues in the paper's voice (some citing today's stories) and
two-minute teasers built from story figures. The model proposes; code checks. Teaser answers are
computed here from the expression the model gives, and every number in that expression must appear
in the story it cites."""
import ast
import operator
import re

from .. import config
from ..ingest.text import esc, plain
from ..puzzles import entries
from . import prompts, verify
from .providers import AIError, Budget, BudgetExceeded, get

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def safe_eval(expr):
    """Evaluate + - * / and parentheses over numbers; anything else raises ValueError."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -ev(n.operand)
        raise ValueError('unsupported expression')
    expr = expr.replace('×', '*').replace('÷', '/').replace('−', '-').replace(',', '')
    return ev(ast.parse(expr, mode='eval'))


def _stories(content):
    out = [content['lead']] + ([content['sidebar']] if content.get('sidebar') else [])
    for u in content['units']:
        if u[0] != 'roundup':
            out += u[1:]
    return out


def _text(st):
    return ' '.join(plain(b[1]) for b in st['blocks'] if b[0] in ('p', 'dropcap', 'quote') and isinstance(b[1], str))


def improve(content, date, log=print):
    cfg = config.load()
    p = get(Budget(min(0.3, cfg.ai.max_cost_usd * 0.2)), cfg)
    if p is None:
        return
    stories = _stories(content)
    menu = '\n'.join(f'- {s["id"]}: {plain(s["headline"])} ({plain(s.get("deck", ""))[:120]})' for s in stories)
    pz = content.get('puzzles', {})
    xw = pz.get('crossword')
    if xw:
        try:
            _, ac, dn = entries(xw['grid'])
            answers = sorted({w for _, w in ac + dn})
            r = p.complete(prompts.house_style(cfg),
                           f"Write crossword clues for these answers: {', '.join(answers)}.\n"
                           f"Clues are short (under 12 words), fair and friendly; never use the answer or its root in the clue. "
                           f"For three to five answers that fit today's stories, write the clue about the story and give its id "
                           f"(else story_id is empty). Today's stories:\n{menu}\nReturn JSON {{\"clues\": [{{answer, clue, story_id}}]}}.",
                           schema=prompts.CLUES_SCHEMA, max_tokens=2500)
            ids = {s['id'] for s in stories}
            got = 0
            for c in (r.data or {}).get('clues', []):
                a = (c.get('answer') or '').upper()
                clue = plain(c.get('clue') or '')
                if a not in xw['clues'] or not clue or re.search(re.escape(a[:max(3, len(a) - 2)]), clue.upper()):
                    continue
                ref = f' (page {{p:{c["story_id"]}}})' if c.get('story_id') in ids else ''
                xw['clues'][a] = esc(clue) + ref
                got += 1
            log(f'AI wrote {got} crossword clues')
        except (AIError, BudgetExceeded) as e:
            log(f'AI clues skipped: {e}')
    try:
        r = p.complete(prompts.house_style(cfg),
                       "Write three two-minute arithmetic teasers from figures in today's stories. Each question must state "
                       "every number it uses (taken exactly from the story) and end with the story's page reference placeholder. "
                       "Give the arithmetic as an expression over those numbers (+ - * / and parentheses only), how many "
                       f"decimals to show, and the unit of the answer.\nToday's stories:\n{menu}\n\nStory texts:\n"
                       + '\n\n'.join(f'[{s["id"]}] {_text(s)[:2500]}' for s in stories[:8])
                       + '\nReturn JSON {"teasers": [{title, question, story_id, expression, decimals, unit}]}.',
                       schema=prompts.TEASERS_SCHEMA, max_tokens=2000)
        by_id = {s['id']: s for s in stories}
        teasers = []
        for t in (r.data or {}).get('teasers', []):
            st = by_id.get(t.get('story_id'))
            if not st:
                continue
            q = plain(t.get('question') or '')
            nums_q = verify.numbers(q)
            nums_e = verify.numbers(t.get('expression') or '')
            src = _text(st)
            if not nums_e or any(n not in verify.numbers(src) for n in nums_e) or any(n not in nums_q for n in nums_e):
                continue
            try:
                v = safe_eval(t['expression'])
            except (ValueError, SyntaxError, ZeroDivisionError):
                continue
            d = max(0, min(3, int(t.get('decimals') or 0)))
            ans = f'{v:,.{d}f}' + (f' {plain(t.get("unit") or "")}' if t.get('unit') else '')
            q = re.sub(r'\s*\(?page[^)]*\)?\.?\s*$', '', q, flags=re.I)
            teasers.append([esc(plain(t.get('title') or 'Teaser')), esc(q) + f' (page {{p:{st["id"]}}})', esc(ans)])
        if len(teasers) >= 3:
            pz['teasers'] = teasers[:3]
            content['meta']['teaser_source'] = 'stories'
            log('AI wrote 3 story teasers (answers computed in code)')
    except (AIError, BudgetExceeded) as e:
        log(f'AI teasers skipped: {e}')
