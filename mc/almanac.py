"""Almanac data, computed with PyEphem for the paper's location (rules.LOCATION).

Everything printed about the sky comes from here: the front-page sky strip, today/tomorrow table,
principal phases, DST note, and an automatically generated sky calendar (phases, supermoons,
meteor-shower peaks with moonlight, close Moon-planet and planet-planet pairings, greatest
elongations). Editions may add their own rows (e.g. a mission date tied to a story).
"""
import datetime, math
from zoneinfo import ZoneInfo
import ephem
from . import rules as R

DEG = 180 / math.pi
PLANETS = {'Mercury': ephem.Mercury, 'Venus': ephem.Venus, 'Mars': ephem.Mars, 'Jupiter': ephem.Jupiter, 'Saturn': ephem.Saturn}
STARS = [('Aldebaran', 'orange <b>Aldebaran</b>'), ('Regulus', '<b>Regulus</b>, the heart of Leo'), ('Spica', 'blue-white <b>Spica</b>'),
         ('Antares', 'red <b>Antares</b>'), ('Alcyone', 'the <b>Pleiades</b> star cluster'), ('Pollux', '<b>Pollux</b> in Gemini')]
LOOKUPS = [  # (name, RA, Dec J2000, what to say) for the almanac's look-up box; the highest one at 21:00 is chosen
    ('the Andromeda Galaxy', '0:42:44', '41:16:09', 'the most distant thing most people can see without a telescope: a faint, fuzzy oval from a dark spot, 2.5 million light-years away.'),
    ('the Pleiades', '3:47:24', '24:07:00', 'a tight little dipper of stars, the Seven Sisters; binoculars show dozens more.'),
    ('the Orion Nebula', '5:35:17', '-5:23:28', 'a misty patch in Orion&rsquo;s sword where new stars are forming; binoculars show its glow.'),
    ('the Beehive Cluster', '8:40:24', '19:40:00', 'a soft glow in Cancer that binoculars split into dozens of stars.'),
    ('the Big Dipper', '11:03:43', '56:22:57', 'seven bright stars; follow the two at the end of the bowl to find Polaris, the North Star.'),
    ('Arcturus', '14:15:39', '19:10:57', 'the brightest star of spring evenings: arc to it from the Big Dipper&rsquo;s handle.'),
    ('Vega and the Summer Triangle', '18:36:56', '38:47:01', 'three bright stars (Vega, Deneb, Altair) that outline the summer sky; the Milky Way runs through them.'),
    ('the Double Cluster', '2:20:00', '57:08:00', 'two star clusters side by side in Perseus; lovely in binoculars.'),
]
COMPASS = ['north', 'north-northeast', 'northeast', 'east-northeast', 'east', 'east-southeast', 'southeast', 'south-southeast',
           'south', 'south-southwest', 'southwest', 'west-southwest', 'west', 'west-northwest', 'northwest', 'north-northwest']

def tz():
    return ZoneInfo(R.LOCATION['tz'])


def clock(h, m):
    """A printed clock time in the paper's style: 24-hour HH:MM (default) or AP-style 12-hour."""
    if R.CLOCK == '12h':
        if (h, m) == (12, 0):
            return 'noon'
        if (h, m) == (0, 0):
            return 'midnight'
        hh = h % 12 or 12
        return f'{hh}:{m:02d} {"a.m." if h < 12 else "p.m."}' if m else f'{hh} {"a.m." if h < 12 else "p.m."}'
    return f'{h:02d}:{m:02d}'


def edate(d, h=0, m=0):
    """Local wall-clock time -> ephem.Date (UTC)."""
    dt = datetime.datetime(d.year, d.month, d.day, h, m, tzinfo=tz()).astimezone(datetime.timezone.utc)
    return ephem.Date(dt.replace(tzinfo=None))

def local(e):
    return ephem.Date(e).datetime().replace(tzinfo=datetime.timezone.utc).astimezone(tz())

def hm(e):
    """Printed clock time of an ephem date (24-hour HH:MM unless the paper uses a 12-hour clock)."""
    t = local(e); return clock(t.hour, t.minute)

def observer(date=None):
    o = ephem.Observer(); o.lat, o.lon = R.LOCATION['lat'], R.LOCATION['lon']
    o.elevation = R.LOCATION['elevation']; o.pressure = 0; o.horizon = '-0:34'
    if date is not None: o.date = date
    return o

def compass(az_deg):
    return COMPASS[int((az_deg % 360) / 22.5 + 0.5) % 16]

def phase_name(lit, waning):
    if lit < 3: return 'New moon'
    if lit > 97: return 'Full moon'
    if 47 <= lit <= 53: return 'Last quarter' if waning else 'First quarter'
    return ('Waning ' if waning else 'Waxing ') + ('crescent' if lit < 47 else 'gibbous')

def moon_at(d, h=21):
    m = ephem.Moon(); m.compute(edate(d, h))
    return round(m.phase), m.elong < 0

def day_table(d):
    """Sun and Moon for one local date."""
    o = observer(edate(d))
    sr, ss = o.next_rising(ephem.Sun()), o.next_setting(ephem.Sun())
    mr, ms = o.next_rising(ephem.Moon()), o.next_setting(ephem.Moon())
    lit, waning = moon_at(d)
    mins = round((ss - sr) * 1440)
    same = lambda e: hm(e) if local(e).date() == d else '&mdash;'
    return dict(date=d, day=d.strftime('%a'), sr=hm(sr), ss=hm(ss), dl=f'{mins // 60}h {mins % 60}m',
                mr=same(mr), ms=same(ms), mr_next=hm(mr), mr_next_day=local(mr).strftime('%a'), lit=lit, waning=waning)

def phases(d, n=4):
    out = []
    for name, f in (('New moon', ephem.next_new_moon), ('First quarter', ephem.next_first_quarter_moon),
                    ('Full moon', ephem.next_full_moon), ('Last quarter', ephem.next_last_quarter_moon)):
        e = f(edate(d)); t = local(e)
        if name == 'Full moon': name = f'Full &ldquo;{R.FULL_MOON_NAMES[t.month]}&rdquo; Moon'
        out.append((t, name, e))
    out.sort()
    return [(name, f'{t:%a %b} {t.day}, {hm(e)}', t, e) for t, name, e in out[:n]]

def dst_note(d):
    for k in range(-7, 8):
        a, b = d + datetime.timedelta(days=k), d + datetime.timedelta(days=k + 1)
        oa = datetime.datetime(a.year, a.month, a.day, 12, tzinfo=tz()).utcoffset()
        ob = datetime.datetime(b.year, b.month, b.day, 12, tzinfo=tz()).utcoffset()
        if oa != ob:
            fell = ob < oa; when = f'{b:%A}, {b:%b}. {b.day}'
            tense = 'ended' if k < 0 else 'ends'
            if fell: return f'<b>{"Fell" if k < 0 else "Falls"} back:</b> Daylight saving time {tense} at {clock(2, 0)} {when}.'
            return f'<b>{"Sprang" if k < 0 else "Springs"} forward:</b> Daylight saving time {"began" if k < 0 else "begins"} at {clock(2, 0)} {when}.'
    return ''

# ------------------------------------------------------------------ sky calendar
def _dark_view(d):
    """(label, ephem date) pairs for the morning and evening check times when the Sun is well down."""
    out = []
    for h, m in R.VIEW_TIMES:
        e = edate(d, h, m); o = observer(e); s = ephem.Sun(o)
        if s.alt * DEG < -6: out.append(('Before dawn' if h < 12 else 'Evening', e))
    return out

def _body(name, o):
    b = ephem.Moon() if name == 'Moon' else PLANETS[name](); b.compute(o); return b

def calendar(d, days=None):
    """Programmatic sky calendar: list of dict(date, label, text, score)."""
    days = days or R.ALMANAC_DAYS
    rows = []; end = d + datetime.timedelta(days=days)
    # principal phases and supermoons
    for name, when, t, e in phases(d, 6):
        if t.date() > end: continue
        if name.startswith('Full'):
            m = ephem.Moon(); m.compute(e); km = m.earth_distance * ephem.meters_per_au / 1000
            sup = km < 361000
            rows.append(dict(date=t.date(), text=f'{name}{", a supermoon," if sup else ""} at {hm(e)}.', score=2 + (2 if sup else 0)))
        elif name == 'New moon':
            rows.append(dict(date=t.date(), text=f'New moon at {hm(e)}: the darkest nights of the month.', score=1))
    for name, when, t, e in phases(d, 6):
        if 'quarter' in name and t.date() <= end:
            rows.append(dict(date=t.date(), text=f'{name} Moon at {hm(e)}.', score=0.4))
    # bright stars the Moon passes
    for k in range(days + 1):
        day = d + datetime.timedelta(days=k)
        for when, e in _dark_view(day):
            o = observer(e); m = ephem.Moon(o)
            if m.alt * DEG < 8: continue
            for star, label in STARS:
                s = ephem.star(star); s.compute(o); sep = ephem.separation(m, s) * DEG
                if sep < 4 and s.alt * DEG > 8:
                    rows.append(dict(date=day, text=f'{when}, the Moon passes about {sep:.0f}&deg; from {label}, in the {compass(m.az*DEG)}.', score=1.0, key=('star', star)))
    seen = set(); rows[:] = [r for r in rows if r.get('key') is None or (r['key'] not in seen and not seen.add(r['key']))]
    # daylight trend and earliest sunset
    t0, t1 = day_table(d), day_table(end)
    o = observer(); sets = []
    for k in range(0, 60):
        day = d + datetime.timedelta(days=k); o.date = edate(day); ss = o.next_setting(ephem.Sun()); sets.append((local(ss).hour * 60 + local(ss).minute, day, ss))
    lo = min(x[0] for x in sets); plateau = [x for x in sets if x[0] == lo]
    if plateau[0][1] <= end and plateau[0][1] != d:
        a_, b_ = plateau[0][1], plateau[-1][1]
        span = f'from {a_:%b}. {a_.day} to {b_:%b}. {b_.day}' if b_ != a_ else f'on {a_:%b}. {a_.day}'
        rows.append(dict(date=a_, text=f'Sunsets bottom out at {hm(plateau[0][2])}, the earliest of the year, {span}; the shortest day comes later, at the solstice.', score=0.9))
    else:
        rows.append(dict(date=end, text=f'Daylight shrinks from {t0["dl"]} today to {t1["dl"]} by {end:%b}. {end.day}.' if t1['dl'] < t0['dl'] else
                         f'Daylight grows from {t0["dl"]} today to {t1["dl"]} by {end:%b}. {end.day}.', score=0.6))
    # meteor showers
    for name, mo, dy, zhr in R.METEOR_SHOWERS:
        for yr in (d.year, d.year + 1):
            p = datetime.date(yr, mo, dy)
            if d <= p <= end:
                lit, _ = moon_at(p, 2)
                o = observer(edate(p, 18)); ms = o.next_setting(ephem.Moon()); mr = o.next_rising(ephem.Moon())
                if lit < 25: tip = f'with the Moon only {lit}% lit'
                elif local(ms).date() == p + datetime.timedelta(days=1) and local(ms).hour < 5: tip = f'best after moonset, about {hm(ms)}'
                elif local(mr).hour >= 23 or local(mr).hour < 4: tip = f'best before moonrise, about {hm(mr)}'
                else: tip = f'though a {lit}%-lit Moon washes out fainter ones'
                rate = f'up to about {zhr} an hour in a dark sky' if zhr >= 15 else f'about {zhr} an hour, but bright fireballs are possible'
                nxt = p + datetime.timedelta(days=1)
                rows.append(dict(date=p, label=f'{p:%b} {p.day}&ndash;{nxt.day}' if nxt.month == p.month else None,
                                 text=f'<b>{name}</b> peak overnight, {rate}; {tip}.', score=(zhr / 20) * (1.5 if lit < 40 else .6)))
    # close pairings (Moon-planet, planet-planet), visible at a dark check time
    names = list(PLANETS)
    pairs = [('Moon', p) for p in names] + [(a, b) for i, a in enumerate(names) for b in names[i + 1:]]
    best = {}
    for k in range(days + 1):
        day = d + datetime.timedelta(days=k)
        for when, e in _dark_view(day):
            o = observer(e)
            for a, b in pairs:
                A, B = _body(a, o), _body(b, o)
                if A.alt * DEG < 8 or B.alt * DEG < 8: continue
                sep = ephem.separation(A, B) * DEG
                lim = R.CONJUNCTION_MAX_DEG if a == 'Moon' else 2.0
                if sep <= lim and sep < best.get((a, b), (99,))[0]:
                    best[(a, b)] = (sep, day, when, B.az * DEG, B.alt * DEG)
    for (a, b), (sep, day, when, az, alt) in best.items():
        what = f'the Moon sits about {sep:.0f}&deg; from <b>{b}</b>' if a == 'Moon' else f'<b>{a}</b> and <b>{b}</b> pass {sep:.1f}&deg; apart'
        finger = ' &mdash; about a finger&rsquo;s width at arm&rsquo;s length' if sep < 2 else ''
        rows.append(dict(date=day, text=f'{when}, {what}, {alt:.0f}&deg; up in the {compass(az)}{finger}.',
                         score=(3 if a != 'Moon' else 1.5) + (2 - min(sep, 2))))
    # greatest elongation of Mercury and Venus
    for pn in ('Mercury', 'Venus'):
        el = []
        for k in range(-1, days + 2):
            day = d + datetime.timedelta(days=k); P = PLANETS[pn](); P.compute(edate(day, 12)); el.append((abs(P.elong), P.elong, day))
        for i in range(1, len(el) - 1):
            if el[i][0] > el[i - 1][0] and el[i][0] >= el[i + 1][0] and d <= el[i][2] <= end:
                day, morning = el[i][2], el[i][1] < 0
                o = observer(edate(day)); sun = o.next_rising(ephem.Sun()) if morning else o.next_setting(ephem.Sun())
                o.date = ephem.Date(sun - 45 * ephem.minute if morning else sun + 45 * ephem.minute)
                P = PLANETS[pn](); P.compute(o)
                rows.append(dict(date=day, text=f'<b>{pn}</b> at its farthest from the Sun this {"morning" if morning else "evening"} season: '
                                 f'about {P.alt*DEG:.0f}&deg; up in the {compass(P.az*DEG)} at {hm(o.date)}.', score=2.5 if pn == 'Mercury' else 1.5))
    return rows

def tonight(d):
    """What's up tonight (21:00) and before dawn (06:30): bright planets above 10 degrees."""
    out = []
    for label, h, m, day in (('Tonight', 21, 0, d), ('Predawn', 6, 30, d + datetime.timedelta(days=1))):
        o = observer(edate(day, h, m)); seen = []
        for pn in ('Venus', 'Jupiter', 'Mars', 'Saturn', 'Mercury'):
            P = PLANETS[pn](); P.compute(o)
            if P.alt * DEG > 10: seen.append(f'<b>{pn}</b> {P.alt*DEG:.0f}&deg; up in the {compass(P.az*DEG)}')
        if seen:
            out.append(dict(date=d, label=label, text=f'At {clock(h, m)}: ' + '; '.join(seen) + '.', score=9))
    return out

def sky_rows(d, extra=(), n=11):
    """Merged, ranked calendar rows. Top two (by score, excluding Tonight/Predawn) get a star."""
    base = tonight(d) + calendar(d)
    for row in extra:   # edition rows: (date, text[, score])
        base.append(dict(date=row[0], text=row[1], score=row[2] if len(row) > 2 else 2))
    head = [r for r in base if r.get('label') in ('Tonight', 'Predawn')]
    rest = sorted([r for r in base if r not in head], key=lambda r: -r['score'])[:n - len(head)]
    for r in sorted(rest, key=lambda r: -r['score'])[:2]: r['star'] = True
    rest.sort(key=lambda r: r['date'])
    for r in rest:
        if not r.get('label'): r['label'] = f'{r["date"]:%b} {r["date"].day}'
    return head + rest

def lookup(d):
    """('Look Up Tonight', text) for the highest catalogued sight at 21:00, rotating among those well up."""
    up = []
    for name, ra, dec, say in LOOKUPS:
        alt, az = object_at(d, name, ra, dec)
        if alt > 35: up.append((alt, az, name, say))
    if not up: return None
    up.sort(reverse=True); alt, az, name, say = up[d.toordinal() % min(2, len(up))]
    return ('Look Up Tonight', f'At {clock(21, 0)}, {name} stands about {alt:.0f}&deg; up in the {compass(az)}: {say}')

def object_at(d, name, ra, dec, h=21):
    """Alt/az of a fixed object (J2000 RA/Dec strings) at a local hour, e.g. for a 'look up' box."""
    b = ephem.readdb(f'{name},f|G,{ra},{dec},5,2000'); b.compute(observer(edate(d, h))); return b.alt * DEG, b.az * DEG
