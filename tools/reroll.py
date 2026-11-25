#!/usr/bin/env python3
"""reroll.py: makes levels again from other random numbers until one is
solved (tools/solve.py) and the solution wins on the real game; prints the
REROLL entries for tools/levelgen.py.

    python3 tools/reroll.py LEVEL ...

Public domain (Unlicense)."""
import os
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import solve                    # noqa: E402
import levelgen                 # noqa: E402
import progress                 # noqa: E402

TRIES = 12                       # (rerolls tried a level, at most)
# a new layout must give way to the quicker searches: one only the widest
# can do (an hour's search) is too hard for the players we have in mind
SEARCHES = solve.TRIES[:2]
# levels the owner has beaten and wants kept as they are, whatever the
# solver makes of them (53: a row of holes on the bottom floor catches all
# four guards, up to three times: a skill the level teaches; 149: its long
# cables and the pit in the middle, where a guard carrying a geode mustn't
# be trapped; 150: one guard buried on purpose, so he's back at the top when
# the hero drops through the middle floor onto the other three)
KEEP = {53, 149, 150}


def one(n):
    progress.started(n)
    t = time.time()
    k0 = levelgen.REROLL.get(n, 0)
    for k in range(k0 + 1, k0 + 1 + TRIES):
        levelgen.REROLL[n] = k
        rows, style = levelgen.level(n)
        joys, g = solve.solve_hard(rows, tries=SEARCHES)
        if joys is None:
            continue
        pr = solve.pairs(joys)
        if solve.verify(n, pr, rows):
            with open(os.path.join(solve.ROOT, 'build', 'solutions', '%d.txt' % n), 'w') as f:
                f.write(''.join('%d %d\n' % (a, b) for a, b in pr))
            return n, k, style, len(joys), time.time() - t
    return n, None, None, 0, time.time() - t


if __name__ == '__main__':
    os.makedirs(os.path.join(solve.ROOT, 'build', 'solutions'), exist_ok=True)
    levels = [int(a) for a in sys.argv[1:]]
    for n in sorted(set(levels) & KEEP):
        print('level %3d: kept as it is (the owner has beaten it): not made again' % n)
    levels = [n for n in levels if n not in KEEP]
    if not levels:
        sys.exit(0)
    pg = progress.Progress(len(levels))
    with Pool(min(20, len(levels)), initializer=progress.init, initargs=(pg.running,)) as p:
        for n, k, style, loops, secs in p.imap_unordered(one, levels):
            if k is None:
                pg.print('level %3d: no reroll solved (%.0f s)' % (n, secs))
            else:
                pg.print('level %3d: REROLL %d (%s): solved in %d loops, wins on the real game (%.0f s)'
                         % (n, k, style, loops, secs))
            pg.finished(n)
    pg.close()
