#!/usr/bin/env python3
"""trapfit.py: moves a level's guard prison (a pit a guard can't leave)
off the guards' patrol path.  The old pit is filled; new pits are tried at
the dead ends of walkways, away from geodes, so the guards fall in only
when the hero leads them there.  Each is scored by tools/solve.py: how
often the search puts a guard away in it (good), and how often a guard
carrying a geode ends up in it (the geode, and the level, lost: bad).
The best that's solved, and wins on the real game, is printed as an
EDITS entry for tools/levelgen.py.

    python3 tools/trapfit.py LEVEL [REROLL]

Public domain (Unlicense)."""
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import solve                    # noqa: E402
import levelgen as L            # noqa: E402

NEAR = 4                        # (no geode this near the new pit's mouth, on its row)


def base(n, k):
    L.REROLL[n] = k
    L.EDITS.pop(n, None)
    return [list(r) for r in L.level(n)[0]]


def fill_old(g):
    """the old prison's pit cells (walled both sides) made brick again"""
    rows = [''.join(r) for r in g]
    pr = solve.prisons(rows)
    edits = []
    for (r, c) in sorted(pr, key=lambda p: -p[0]):
        wall = lambda x: L.at(g, r, x) in L.SOLID or (r, x) in pr
        if wall(c - 1) and wall(c + 1) and L.at(g, r + 1, c) in L.SOLID:
            edits.append((r, c, 'B'))
            g[r][c] = 'B'
    return edits


POCKET = 3


def pocket(rows, clean, r, x, dx):
    for i in range(POCKET + 1):
        if L.at(clean, r, x) in L.SOLID:
            return True
        if not L.standing(clean, (r, x)) or rows[r][x] in 'THX-':
            return False
        x += dx
    return False


def from_above(g, walk, r, x):
    for y in range(r - 1, -1, -1):
        if L.at(g, y, x) in L.SOLID:
            return False
        if (y, x) in walk or L.at(g, y, x) in 'H-':
            return True
    return True


def candidates(g):
    rows = [''.join(r) for r in g]
    start = [(r, c) for r in range(15) for c in range(32) if rows[r][c] == 'P'][0]
    clean = [list(r.replace('T', '.').replace('E', '.').replace('P', '.').replace('X', '.')) for r in rows]
    walk, _ = L.two_way(clean, start)
    geodes = [(r, c) for r in range(15) for c in range(32) if rows[r][c] == 'T']
    out = []
    for (r, c) in walk:
        if not L.standing(clean, (r, c)):
            continue
        for w in (1, 2, 3):
            cols = range(c, c + w)
            if c + w > 32 or any((r, x) not in walk or not L.standing(clean, (r, x)) for x in cols):
                continue
            # in a pocket: on one side the floor runs into a wall within
            # POCKET cells, nothing there (no ladder, cable, geode): no guard
            # passes over the mouth on his way anywhere
            if not (pocket(rows, clean, r, c - 1, -1) or pocket(rows, clean, r, c + w, 1)):
                continue
            if any(gr == r and min(abs(gc - x) for x in cols) <= NEAR for gr, gc in geodes):
                continue
            if any(rows[r][x] in 'PE' for x in cols):
                continue
            # nothing drops onto the mouth from above (a cable, a ledge):
            # the way in is along the pocket's floor, after the hero
            if any(from_above(g, walk, r, x) for x in cols):
                continue
            for d in (1, 2):                # (a pit one or two deep)
                dug = range(r + 1, r + 1 + d)
                if r + d > 14:
                    continue
                # (the bottom floor's stone may be dug for one: the hero is
                # never below it, so guards go in only after him)
                if any(L.at(g, y, x) != 'B' and not (y == 14 and L.at(g, y, x) == 'S')
                       for y in dug for x in cols):
                    continue
                # (its floor: brick laid there if it's open air)
                if r + 1 + d <= 14 and any(L.at(g, r + 1 + d, x) not in L.SOLID + '.' for x in cols):
                    continue
                if any(L.at(g, y, x) not in L.SOLID for y in dug for x in (c - 1, c + w)):
                    continue
                floor = [(r + 1 + d, x, 'B') for x in cols if r + 1 + d <= 14 and L.at(g, r + 1 + d, x) == '.']
                out.append([(y, x, '.') for y in dug for x in cols] + floor)
    return out


def score(args):
    n, rows, edits = args
    if L.fairness(rows):
        return None
    s = solve.Solver(rows)
    if not s.prison:
        return None
    j, g = s.solve()
    if j is None:
        return None
    st = max(1, s.states)
    return dict(edits=edits, locked=100.0 * s.locked / st, jailed=100.0 * s.jailed / st,
                chance=100.0 * s.chance / st,
                loops=len(j), joys=j, rows=rows)


if __name__ == '__main__':
    n = int(sys.argv[1])
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    g = base(n, k)
    fill = fill_old(g)
    print('old pit filled:', fill)
    cands = candidates(g)
    print('%d places for a new pit' % len(cands), flush=True)
    jobs = []
    for e in cands:
        h = [r[:] for r in g]
        for r, c, ch in e:
            h[r][c] = ch
        jobs.append((n, [''.join(r) for r in h], fill + e))
    with Pool(20) as p:
        got = [x for x in p.map(score, jobs) if x]
    got.sort(key=lambda d: (d['locked'] + d['chance']) * 4 - d['jailed'] * 0.1)
    for d in got[:8]:
        print('pit %s: guards put away %.1f%% (by chance %.2f%%), geodes locked %.2f%%, solved in %d loops'
              % ([(r, c) for r, c, ch in d['edits'] if ch == '.'], d['jailed'], d['chance'], d['locked'],
                 d['loops']), flush=True)
    for d in got[:5]:
        pr = solve.pairs(d['joys'])
        if solve.verify(n, pr, d['rows']):
            print('BEST (wins on the real game): EDITS[%d] = %r' % (n, d['edits']))
            print('\n'.join(d['rows']))
            with open(os.path.join(solve.ROOT, 'build', 'solutions', '%d.txt' % n), 'w') as f:
                f.write(''.join('%d %d\n' % tuple(x) for x in pr))
            break
    else:
        print('none won on the real game')
