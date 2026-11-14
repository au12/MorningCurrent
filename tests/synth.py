"""Deterministic made-up articles and feed entries, so tests never touch the network."""
import datetime
import random

NOUNS = ['lighthouse', 'glacier', 'beetle', 'telescope', 'bridge', 'orchard', 'violin', 'river delta', 'coral reef', 'windmill',
         'canal', 'meadow', 'robot arm', 'sailboat', 'library', 'fossil bed', 'sourdough starter', 'bicycle', 'comet', 'volcano',
         'hedgehog', 'tide pool', 'clock tower', 'seed vault', 'kite', 'lantern', 'cave system', 'heron colony', 'solar oven',
         'bee hive', 'stone circle', 'rain garden', 'paper mill', 'radio dish', 'salt marsh', 'pipe organ', 'tram line', 'quarry pond',
         'mapmaker', 'woodland trail', 'pottery kiln', 'ice core', 'night sky park', 'tea garden', 'weather balloon', 'harbor seal',
         'printing press', 'mountain hut', 'rice terrace', 'jellyfish', 'map archive', 'wind tunnel', 'train station', 'bird song',
         'chess club', 'shipwreck', 'apple variety', 'lava tube', 'moss garden', 'fire lookout']
ADJS = ['quiet', 'ancient', 'tiny', 'restored', 'floating', 'curious', 'gentle', 'bright', 'patient', 'clever', 'hidden', 'humble']
PLACES = ['Ohio', 'Maine', 'Oregon', 'Vermont', 'Kyoto', 'Norway', 'Chile', 'Wales', 'Iceland', 'Kenya', 'Quebec', 'Tasmania']
VERBS = ['outlasts', 'welcomes', 'inspires', 'shelters', 'hosts', 'rewards', 'surprises', 'guides', 'delights', 'feeds',
         'charms', 'teaches', 'gathers', 'brightens', 'steadies', 'awakens', 'cheers']
VERBS2 = ['surveyed', 'sketched', 'measured', 'photographed', 'restored', 'catalogued', 'mapped', 'recorded', 'repaired']
OBJS = ['curious schoolchildren', 'migrating geese', 'weekend hikers', 'amateur astronomers', 'retired engineers', 'local bakers',
        'visiting painters', 'river otters', 'summer interns', 'patient beekeepers', 'night owls', 'village musicians',
        'sleepy foxes', 'map collectors', 'young sailors', 'stubborn gardeners', 'traveling scholars', 'quiet readers',
        'clever ravens', 'dairy farmers', 'tea growers', 'cyclists', 'model builders', 'potters', 'clockmakers',
        'woodcarvers', 'fishing crews', 'choir singers', 'shepherds', 'kite flyers', 'weavers']
PEOPLE = ['Maria Lopez', 'James Okafor', 'Anna Berg', 'Wei Chen', 'Sofia Rossi', 'Tom Hughes', 'Priya Nair', 'Lars Holm']

S = [
    'Researchers in {place} spent {n} months studying the {noun}, measuring how it changed through the seasons.',
    'The work began almost by accident, when a volunteer noticed something odd about the {noun} during a routine visit.',
    'Over {n} weeks the team logged temperatures, sounds and photographs, building a record nobody had kept before.',
    'Local residents had long suspected the {noun} was special, but nobody had the instruments to show it.',
    'The results surprised even the people who had argued for the project from the start.',
    'Funding came from a small regional grant and a great deal of borrowed equipment.',
    'Students from a nearby school joined the effort and now help maintain the {noun} every weekend.',
    'The {adj} {noun} turned out to be far more resilient than earlier surveys had suggested.',
    'Similar sites elsewhere could benefit from the same approach, the authors note, and several have already asked for advice.',
    'The findings were shared in an open report so that other groups can repeat the measurements.',
    'Visitors can see the {noun} on guided walks that run through the spring and summer.',
    'A second phase of the project will look at how the {noun} responds to unusually wet years.',
    'Careful records from the nineteenth century gave the team a baseline to compare against.',
    'The next step is a simple field guide that any interested neighbor can use.',
]
QUOTES = ['We expected a small change, and instead we found a story that runs back more than {n} years',
          'Everyone who works here has a favorite corner of the {noun}, and now we finally understand why it thrives',
          'It is the kind of result that makes you want to go back outside and keep looking']


def article(i, words=900, seed=0):
    rng = random.Random(seed * 1000 + i)
    noun = NOUNS[i % len(NOUNS)]
    adj = ADJS[(i * 7) % len(ADJS)]
    place = PLACES[(i * 5) % len(PLACES)]
    who = PEOPLE[i % len(PEOPLE)]
    verb = VERBS[(i * 3) % len(VERBS)]
    obj = OBJS[(i * 11) % len(OBJS)]
    title = f'{adj.capitalize()} {noun} {verb} {obj} in {place}'
    paras, total = [], 0
    while total < words:
        ss = [s.format(place=place, n=rng.randint(3, 40), noun=noun, adj=adj) for s in rng.sample(S, rng.randint(3, 5))]
        if len(paras) == 3:
            ss.append(f'“{rng.choice(QUOTES).format(n=rng.randint(50, 300), noun=noun)},” said {who}, who led the survey.')
        p = ' '.join(ss)
        paras.append(p)
        total += len(p.split())
    summary = (f'{who} {VERBS2[(i * 5) % len(VERBS2)]} the {noun} with {OBJS[(i * 7 + 3) % len(OBJS)]}, '
               f'and {PLACES[(i * 3 + 1) % len(PLACES)]} {OBJS[(i * 13 + 5) % len(OBJS)]} followed.')
    return dict(title=title, summary=summary, paras=paras, noun=noun)


def entry(i, words=900, seed=0, base='https://example.org'):
    a = article(i, words, seed)
    published = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2 + i)).timetuple()
    html = ''.join(f'<p>{p}</p>' for p in a['paras'])
    return {'title': a['title'], 'link': f'{base}/story/{seed}-{i}', 'summary': a['summary'], 'content': [{'value': html}],
            'published_parsed': published, 'author': ''}


def row(i, category, source, words=900, tier='full', license='public-domain', seed=0):
    """An item as the planner sees it (already extracted)."""
    a = article(i, words, seed)
    blocks = [dict(type='p', text=p) for p in a['paras']]
    return dict(id=i + 1, url=f'https://example.org/story/{seed}-{i}', link=f'https://example.org/story/{seed}-{i}', source=source,
                title=a['title'], summary=a['summary'], author='', published=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                text='\n\n'.join(a['paras']), blocks=blocks, words=sum(len(p.split()) for p in a['paras']), category=category,
                tier=tier, license=license, status='candidate', score=1.0 - i * 0.005, image=None, image_credit='', meta={})
