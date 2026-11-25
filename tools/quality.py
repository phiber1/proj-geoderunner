#!/usr/bin/env python3
"""quality.py: how much of each level its solution uses (the solver's
saved solutions, build/solutions/N.txt, replayed in tools/sim.py): the
ladder and cable cells never touched, the share of stone, the holes dug
and the guards trapped.  A layout full of untouched ladders and cables
is clutter (ladders to nowhere).

    python3 tools/quality.py [LEVEL ...]

Public domain (Unlicense)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim                      # noqa: E402
import solve                    # noqa: E402


def measure(n):
    path = os.path.join(solve.ROOT, 'build', 'solutions', '%d.txt' % n)
    if not os.path.exists(path):
        return None
    rows = solve.level_rows(n)
    g = sim.Game(rows)
    seen = set()
    digs, last = 0, 0
    for line in open(path):
        k, j = map(int, line.split())
        for i in range(k):
            if j & sim.J_FIRE and not last & sim.J_FIRE:
                digs += 1
            last = j
            g.step(j)
            seen.add((g.r, g.c))
            if g.dead or g.done:
                break
    lad = [(r, c) for r in range(15) for c in range(32) if rows[r][c] == 'H']
    cab = [(r, c) for r in range(15) for c in range(32) if rows[r][c] == '-']
    solid = sum(row.count('B') + row.count('S') for row in rows)
    stone = sum(row.count('S') for row in rows)
    return dict(won=g.done, loops=g.loops, ladders=len(lad), lad_unused=sum(p not in seen for p in lad),
                cables=len(cab), cab_unused=sum(p not in seen for p in cab),
                stone=stone / max(1, solid), digs=digs, traps=g.events.get('trap', 0),
                cover=len(seen))


if __name__ == '__main__':
    levels = [int(a) for a in sys.argv[1:]] or range(1, 151)
    print('level  loops  ladders unused  cables unused  stone  digs  traps  cells')
    for n in levels:
        m = measure(n)
        if m is None:
            print('%5d  (no solution)' % n)
            continue
        print('%5d  %5d  %7d %5d%%  %6d %5d%%  %4.0f%%  %4d  %5d  %5d%s' % (
            n, m['loops'], m['ladders'], 100 * m['lad_unused'] // max(1, m['ladders']),
            m['cables'], 100 * m['cab_unused'] // max(1, m['cables']), 100 * m['stone'],
            m['digs'], m['traps'], m['cover'], '' if m['won'] else '  (not won here)'))
