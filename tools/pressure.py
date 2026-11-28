#!/usr/bin/env python3
"""pressure.py: how hard each level presses the hero: the share of the
moves the solver tries (with a player's reactions) that get him caught.
A level where many moves are deadly forgives few lapses in watching the
guards: the owner's verdicts follow it (levels 1-2 under 10%, 51, 100 and
150 over 30%).  Writes build/pressure.txt (level, pressure, solved).

    python3 tools/pressure.py [LEVEL ...]

Public domain (Unlicense)."""
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import solve                    # noqa: E402
import progress                 # noqa: E402

REACT = 8


def one(n):
    progress.started(n)
    s = solve.Solver(solve.level_rows(n), react=REACT)
    joys, g = s.solve()
    return n, 100.0 * s.deaths / max(1, s.states), joys is not None


if __name__ == '__main__':
    levels = [int(a) for a in sys.argv[1:]] or list(range(1, 151))
    out = {}
    pg = progress.Progress(len(levels))
    with Pool(progress.workers(), initializer=progress.init, initargs=(pg.running,)) as p:
        for n, pr, ok in p.imap_unordered(one, levels):
            out[n] = (pr, ok)
            pg.print('level %3d: pressure %4.1f%%%s' % (n, pr, '' if ok else '  (not solved)'))
            pg.finished(n)
    pg.close()
    path = os.path.join(solve.ROOT, 'build', 'pressure.txt')
    table = {}                          # (merged with what's there)
    if os.path.exists(path):
        for line in open(path):
            n, pr, ok = line.split()
            table[int(n)] = (float(pr), int(ok))
    table.update(out)
    with open(path, 'w') as f:
        for n in sorted(table):
            f.write('%d %.1f %d\n' % (n, table[n][0], table[n][1]))
