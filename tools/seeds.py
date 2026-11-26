#!/usr/bin/env python3
"""seeds.py: does a level's way through depend on luck?  A buried guard
comes back at a random place on the top row, and the player can't know
where until it happens.  So: the solver (a player's reactions, the quick
search) plays on as long as no guard is buried, where every respawn seed
plays the same; each state where a guard is buried is a fork, where each
seed's respawn comes out differently.  From the best forks every seed then
goes on alone, adapting to where its guards came back, as a player does.
The score: the most seeds any fork leads to a win (all, if no burying is
needed).  Winnable under most: plannable (repeating a kill until a guard
lands somewhere useful counts, as in Championship Lode Runner).  Under a
few: a lucky roll decides, where a bad one kills (the owner on level 96).
Simulator only (it matches the game).

    python3 tools/seeds.py [LEVEL ...]

Writes build/seeds.txt (level, seeds won).  Public domain (Unlicense)."""
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim                      # noqa: E402
import solve                    # noqa: E402
import progress                 # noqa: E402

SEEDS = [0xACE1, 0x1D2B, 0x5A3C, 0xB7E9, 0x4F61]
REACT = 8


FORKS = 3                       # (the best forks followed)


def buried(g, h):
    return h.events.get('bury', 0) > g.events.get('bury', 0)


def one(n):
    progress.started(n)
    rows = solve.level_rows(n)
    s = solve.Solver(rows, react=REACT)
    joys, g = s.solve(fork=buried)
    if joys is not None:                # (won burying no one: luck never enters)
        return n, len(SEEDS), 'no burying'
    best = 0
    for sc, h, path in sorted(s.forks, key=lambda t: -t[0])[:FORKS]:
        won = 0
        for seed in SEEDS:
            k = replay_fork(rows, path, seed)
            if k is not None and solve.Solver(rows, react=REACT).solve(start=k)[0] is not None:
                won += 1
        best = max(best, won)
        if best == len(SEEDS):
            break
    return n, best, '%d forks' % len(s.forks)


def replay_fork(rows, path, seed):
    """the fork's game as it would be under another respawn seed: the same
    inputs from the start with that seed"""
    g = sim.Game(rows, seed=seed)
    for j in path:
        g.step(j)
        if g.dead:
            return None
    return g


if __name__ == '__main__':
    levels = [int(a) for a in sys.argv[1:]] or list(range(1, 151))
    won = {}
    pg = progress.Progress(len(levels))
    with Pool(20, initializer=progress.init, initargs=(pg.running,)) as p:
        for n, k, note in p.imap_unordered(one, levels):
            won[n] = k
            pg.print('level %3d: won under %d of %d respawn seeds (%s)' % (n, k, len(SEEDS), note))
            pg.finished(n)
    pg.close()
    with open(os.path.join(solve.ROOT, 'build', 'seeds.txt'), 'w') as f:
        for n in sorted(won):
            f.write('%d %d\n' % (n, won[n]))
