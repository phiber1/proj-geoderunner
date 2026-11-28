#!/usr/bin/env python3
"""audit.py: the difficulty curve, level by level, and where it spikes.

For each level: how hard it presses the hero (build/pressure.txt, from
tools/pressure.py), the longest stretch with no breather (build/breath.txt,
tools/breath.py), geodes the guards pick up in the first 10 s of the way
found with a player's reactions (build/solutions-react8), the geode count,
and whether a tall ladder runs up the middle (a guard "express lane": the
owner on 96 and old 51).  Each measure is scored against the level's
neighbors; a level is flagged as a SPIKE when several measures agree it's
much harder than they are (one noisy measure isn't enough), a DIP when
they agree it's much easier (fine as a rest level, now and then).  Word
levels (on the tens) and the owner's levels (53, 149, 150) are shown but
not flagged.

    python3 tools/audit.py              (writes build/audit.json and prints the flags)

Public domain (Unlicense)."""
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim                      # noqa: E402
import solve                    # noqa: E402

KEEP = {53, 149, 150}
EARLY = 600                     # (frames: the opening 10 s)
WINDOW = 6                      # (neighbors either side compared with)
TALL = 9                        # (a ladder this many rows or more ...)
MIDDLE = range(8, 24)           # (... in these columns: an express lane)


def table(name, cols):
    path = os.path.join(solve.ROOT, 'build', name)
    out = {}
    if os.path.exists(path):
        for line in open(path):
            f = line.split()
            out[int(f[0])] = [float(x) for x in f[1:cols + 1]]
    return out


def early(n, rows):
    path = os.path.join(solve.ROOT, 'build', 'solutions-react8', '%d.txt' % n)
    if not os.path.exists(path):
        return None
    g = sim.Game(rows)
    t = 0
    for line in open(path):
        k, j = map(int, line.split())
        for i in range(k):
            if t >= EARLY or g.dead or g.done:
                return g.events.get('carry', 0)
            g.step(j)
            t += 1
    return g.events.get('carry', 0)


def express(rows):
    for c in MIDDLE:
        run = 0
        for r in range(15):
            run = run + 1 if rows[r][c] == 'H' else 0
            if run >= TALL:
                return 1
    return 0


def main():
    press, breath = table('pressure.txt', 1), table('breath.txt', 1)
    lv = {}
    for n in range(1, 151):
        rows = solve.level_rows(n)
        lv[n] = dict(pressure=press.get(n, [None])[0], breath=breath.get(n, [None])[0],
                     early=early(n, rows), geodes=sum(r.count('T') for r in rows), express=express(rows),
                     word=n % 10 == 0, keep=n in KEEP)
    measures = ['pressure', 'breath', 'early', 'geodes', 'express']
    for n in lv:
        near = [m for m in range(n - WINDOW, n + WINDOW + 1) if m != n and m in lv and not lv[m]['word']]
        hard = easy = 0
        z = {}
        for k in measures:
            v = lv[n][k]
            others = [lv[m][k] for m in near if lv[m][k] is not None]
            if v is None or len(others) < 3:
                continue
            mu, sd = statistics.mean(others), statistics.pstdev(others) or 1.0
            z[k] = (v - mu) / sd
            hard += z[k] > 1.0
            easy += z[k] < -1.0
        lv[n]['z'] = z
        lv[n]['flag'] = ('' if lv[n]['word'] or lv[n]['keep'] else
                         'SPIKE' if hard >= 3 else 'DIP' if easy >= 3 else '')
    with open(os.path.join(solve.ROOT, 'build', 'audit.json'), 'w') as f:
        json.dump(lv, f, indent=1)
    for n in sorted(lv):
        d = lv[n]
        if d['flag']:
            print('level %3d %-5s pressure %s, breather gap %s s, early pickups %s, geodes %d%s' % (
                n, d['flag'], d['pressure'], d['breath'], d['early'], d['geodes'],
                ', express ladder' if d['express'] else ''))
    print('spikes %d, dips %d' % (sum(d['flag'] == 'SPIKE' for d in lv.values()),
                                  sum(d['flag'] == 'DIP' for d in lv.values())))


if __name__ == '__main__':
    main()
