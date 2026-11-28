#!/usr/bin/env python3
"""solveall.py: tools/solve.py on every level (or those named), each
solution saved (build/solutions/N.txt) and replayed on the real game.

    python3 tools/solveall.py [--react FRAMES] [LEVEL ...]

--react: played with a player's reactions (he stands still FRAMES frames
before doing anything new), and only the quicker searches: what a person
can do.

Prints a line a level and a summary; shows its progress (and keeps
build/progress.txt: tools/progress.py watches it from another terminal).  Public domain (Unlicense)."""
import os
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import solve                    # noqa: E402
import progress                 # noqa: E402


REACT = 0


def one(n):
    progress.started(n)
    t = time.time()
    if REACT:
        joys, g = solve.solve_hard(solve.level_rows(n), tries=solve.TRIES[:2], react=REACT)
    else:
        joys, g = solve.solve_hard(solve.level_rows(n))
    if joys is None:
        return n, None, 0, time.time() - t, False
    pr = solve.pairs(joys)
    folder = os.path.join(solve.ROOT, 'build', 'solutions-react%d' % REACT if REACT else 'solutions')
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, '%d.txt' % n), 'w') as f:
        f.write(''.join('%d %d\n' % (k, j) for k, j in pr))
    return n, len(joys), len(pr), time.time() - t, solve.verify(n, pr)


if __name__ == '__main__':
    os.makedirs(os.path.join(solve.ROOT, 'build', 'solutions'), exist_ok=True)
    args = sys.argv[1:]
    if args[:1] == ['--react']:
        REACT = int(args[1])
        args = args[2:]
    levels = [int(a) for a in args] or list(range(1, 151))
    won, unsolved, failed = [], [], []
    pg = progress.Progress(len(levels))
    with Pool(progress.workers(), initializer=progress.init, initargs=(pg.running,)) as p:
        for n, loops, npr, secs, ok in p.imap_unordered(one, levels):
            if loops is None:
                unsolved.append(n)
                pg.print('level %3d: not solved (%.0f s)' % (n, secs))
            else:
                (won if ok else failed).append(n)
                pg.print('level %3d: %5d loops, %3d pairs, %4.0f s: %s' % (
                    n, loops, npr, secs, 'wins on the real game' if ok else 'FAILS on the real game'))
            pg.finished(n)
    pg.close()
    print('won: %d; not solved: %d %s; failed on the real game: %d %s' % (
        len(won), len(unsolved), sorted(unsolved), len(failed), sorted(failed)))
