#!/usr/bin/env python3
"""reroll.py: makes levels again from other random numbers until one is
solved (tools/solve.py) and the solution wins on the real game; prints the
REROLL entries for tools/levelgen.py (by layout number: see its ORDER).

    python3 tools/reroll.py LEVEL ...

Public domain (Unlicense)."""
import os
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim                      # noqa: E402
import solve                    # noqa: E402
import levelgen                 # noqa: E402
import progress                 # noqa: E402

TRIES = 30                       # (rerolls tried a level, at most)
# a new layout must give way to the quicker searches: one only the widest
# can do (an hour's search) is too hard for the players we have in mind
SEARCHES = solve.TRIES[:2]
# ... and with a player's reactions (frames he stands still before doing
# anything new): a person must be able to do it, not only a machine
REACT = 8
# levels the owner has beaten and wants kept as they are, whatever the
# solver makes of them (53: a row of holes on the bottom floor catches all
# four guards, up to three times: a skill the level teaches; 149: its long
# cables and the pit in the middle, where a guard carrying a geode mustn't
# be trapped; 150: one guard buried on purpose, so he's back at the top when
# the hero drops through the middle floor onto the other three; 96: top
# first, then down, ending with all four guards buried in a row of holes;
# 113: drop the guards from the two cables in the middle to confuse them,
# then run back up and over them, right to left)
KEEP = {53, 96, 113, 149, 150}
# a new layout must also fit its slot (owner, on the first new 96: far
# harder than its neighbors): how hard it presses the hero
# (tools/pressure.py) no more than MAX_PRESSURE when given (--max-pressure P)
MAX_PRESSURE = None
# ... and not hand the guards the geodes at once (the owner on 96: both
# guards coming down were always carrying one by the bottom, the one by
# the vault another): at most MAX_EARLY geodes picked up by guards in the
# first EARLY frames of the way found (--max-early N)
MAX_EARLY = None
EARLY = 600


def early_carries(rows, joys):
    g = sim.Game(rows)
    for j in joys[:EARLY]:
        g.step(j)
        if g.dead or g.done:
            break
    return g.events.get('carry', 0)


def pressure(rows):
    s = solve.Solver(rows, react=REACT)
    s.solve()
    return 100.0 * s.deaths / max(1, s.states)


def one(n):
    progress.started(n)
    t = time.time()
    m = levelgen.ORDER.get(n, n)        # (the layout in slot n: rerolled by its number)
    k0 = levelgen.REROLL.get(m, 0)
    for k in range(k0 + 1, k0 + 1 + TRIES):
        levelgen.REROLL[m] = k
        rows, style = levelgen.level(n)
        if MAX_PRESSURE is not None and pressure(rows) > MAX_PRESSURE:
            continue
        joys, g = solve.solve_hard(rows, tries=SEARCHES, react=REACT)
        if joys is None:
            continue
        if MAX_EARLY is not None and early_carries(rows, joys) > MAX_EARLY:
            continue
        pr = solve.pairs(joys)
        if solve.verify(n, pr, rows):
            with open(os.path.join(solve.ROOT, 'build', 'solutions', '%d.txt' % n), 'w') as f:
                f.write(''.join('%d %d\n' % (a, b) for a, b in pr))
            return n, k, '%s; layout %d' % (style, m), len(joys), time.time() - t
    return n, None, None, 0, time.time() - t


if __name__ == '__main__':
    os.makedirs(os.path.join(solve.ROOT, 'build', 'solutions'), exist_ok=True)
    args = sys.argv[1:]
    while args[:1] in (['--max-pressure'], ['--max-early']):
        if args[0] == '--max-pressure':
            MAX_PRESSURE = float(args[1])
        else:
            MAX_EARLY = int(args[1])
        args = args[2:]
    levels = [int(a) for a in args]
    for n in sorted(set(levels) & KEEP):
        print('level %3d: kept as it is (the owner has beaten it): not made again' % n)
    levels = [n for n in levels if n not in KEEP]
    if not levels:
        sys.exit(0)
    pg = progress.Progress(len(levels))
    with Pool(min(progress.workers(), len(levels)), initializer=progress.init, initargs=(pg.running,)) as p:
        for n, k, style, loops, secs in p.imap_unordered(one, levels):
            if k is None:
                pg.print('level %3d: no reroll solved (%.0f s)' % (n, secs))
            else:
                pg.print('level %3d: REROLL %d (%s): solved in %d loops, wins on the real game (%.0f s)'
                         % (n, k, style, loops, secs))
            pg.finished(n)
    pg.close()
