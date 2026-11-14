"""Prompts and output schemas for AI writing. The house style is editable in Settings > AI; the default
below is the original Morning Current's voice guide."""
from .. import config, rules as R

DEFAULT_HOUSE_STYLE = """\
Write for a smart general reader (grade 8 to 10). Open with the reader or a scene, then explain with
everyday comparisons. One idea per paragraph. Sentences average 20 words or fewer, with at most two
numbers in a sentence. Use short, conversational subheads. Headlines are Title Case, two lines at most
(under 70 characters). AP-ish style ("Nov. 5"). Say when the news happened. Include the caveats: small
or early studies, lab-only results, company-supplied figures and projections are labeled as such.
When sources disagree, say so. Nothing partisan, no crime, disaster or sensational framing; poignant is
fine, depressing is not."""

ACCURACY_RULES = """\
Accuracy rules (checked automatically; a story that breaks them is rejected):
- Use only facts found in the SOURCE TEXT. Do not add facts from memory.
- Every number you print must appear in the source text exactly as written there (you may drop commas).
  Do not convert units, round, add, subtract or otherwise compute new numbers.
- Quotes must be copied word for word from the source text, and attributed only to the speaker the
  source names for that quote. Use at most two quotes.
- Do not copy more than one sentence in a row from the source except inside a quote; write in your own words.
"""


def house_style(cfg=None):
    cfg = cfg or config.load()
    style = cfg.ai.house_style.strip() or DEFAULT_HOUSE_STYLE
    units = {'imperial': 'Use imperial units, with metric where natural, but only figures the source gives.',
             'metric': 'Use metric units, but only figures the source gives.',
             'both': 'Give metric and imperial units when the source gives both.'}[cfg.format.units]
    clock = 'All clock times are 24-hour HH:MM.' if cfg.format.clock == '24h' else 'Clock times use AP style (6:30 a.m.).'
    return (f'You are an editor writing for {cfg.paper.title}, a printed morning paper ({cfg.paper.tagline}).\n'
            f'The reader: {cfg.editorial.reader_profile}\n\n{style}\n{units} {clock}\n\n{ACCURACY_RULES}')


_ITEM = {'type': 'object', 'additionalProperties': False,
         'properties': {'label': {'type': 'string'}, 'value': {'type': 'string'}, 'number': {'type': 'number'}},
         'required': ['label', 'value', 'number']}

STORY_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'kicker_topic': {'type': 'string', 'description': 'One or two words for the kicker after the category, e.g. "Missions"'},
        'headline': {'type': 'string'},
        'deck': {'type': 'string', 'description': 'One or two sentences adding why it matters'},
        'cont_head': {'type': 'string', 'description': 'Lead only: sentence-case head for the page-2 continuation'},
        'teaser_title': {'type': 'string', 'description': 'Two to five words for the front-page index'},
        'teaser_hook': {'type': 'string', 'description': 'One short line for the front-page index'},
        'blocks': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'properties': {
                'type': {'type': 'string', 'enum': ['p', 'h4', 'quote', 'facts', 'bars', 'list']},
                'text': {'type': 'string', 'description': 'p: paragraph; h4: subhead; quote: the verbatim quote'},
                'speaker': {'type': 'string', 'description': 'quote: the speaker as the source names them'},
                'title': {'type': 'string', 'description': 'facts/bars: box or chart title'},
                'items': {'type': 'array', 'items': _ITEM, 'description': 'facts: up to 4 (value, label); bars: (label, number)'},
            },
            'required': ['type', 'text', 'speaker', 'title', 'items']}},
    },
    'required': ['kicker_topic', 'headline', 'deck', 'cont_head', 'teaser_title', 'teaser_hook', 'blocks'],
}

CANDIDATES_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {'stories': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False,
        'properties': {'url': {'type': 'string'}, 'title': {'type': 'string'}, 'category': {'type': 'string'},
                       'published': {'type': 'string'}, 'why': {'type': 'string'}},
        'required': ['url', 'title', 'category', 'published', 'why']}}},
    'required': ['stories'],
}

CLUES_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {'clues': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False,
        'properties': {'answer': {'type': 'string'}, 'clue': {'type': 'string'}, 'story_id': {'type': 'string'}},
        'required': ['answer', 'clue', 'story_id']}}},
    'required': ['clues'],
}

TEASERS_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {'teasers': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False,
        'properties': {'title': {'type': 'string'}, 'question': {'type': 'string'}, 'story_id': {'type': 'string'},
                       'expression': {'type': 'string', 'description': 'Arithmetic using only numbers from the question, e.g. 150/38.2'},
                       'decimals': {'type': 'integer'}, 'unit': {'type': 'string'}},
        'required': ['title', 'question', 'story_id', 'expression', 'decimals', 'unit']}}},
    'required': ['teasers'],
}


def story_prompt(role, words, category, item, text, sid):
    shape = {
        'lead': 'the front-page lead (it continues on page 2): a classic feature with 3 or 4 subheads, one pull quote '
                'if the source has a good one, and a facts box of up to four key figures',
        'feature': 'a one-page feature. Pick the form that suits it: classic feature, Q&A, how-it-works, numbered list or '
                   'profile. Up to three subheads; a facts box or a small bar chart only if the source has the numbers',
        'split': 'a one-column story sharing a page with another; no subheads, no boxes',
        'spread': 'the two-page Deep Dive: several subheads, one or two quotes, a facts box and, if the source has '
                  'comparable figures, a small bar chart',
        'sidebar': 'a short sidebar under the lead; two paragraphs, no subheads',
    }[role]
    return f"""Write {shape}. Target length: about {words} words of body text (paragraphs only).
Category: {category}. Story id: {sid}.

SOURCE: {item.get('source')} ({item.get('link')}), published {str(item.get('published', ''))[:10]}.
SOURCE TITLE: {item.get('title')}
SOURCE TEXT:
\"\"\"
{text}
\"\"\"

Return JSON. Blocks are in reading order; a 'quote' block's text must be copied exactly from the source text.
For 'facts', each item's value is the figure as printed (e.g. "596 m") and number is that figure's number;
for 'bars', label + number. Leave unused fields as empty strings or empty lists."""


def revise_prompt(errors):
    return ('Your story failed the automatic accuracy check:\n- ' + '\n- '.join(errors[:12]) +
            '\nRewrite it so every number and quote appears exactly in the source text, and return the full JSON again.')
