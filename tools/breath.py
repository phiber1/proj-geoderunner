#!/usr/bin/env python3
"""breath.py: breathing room: where on a level the player can stop and
think.  Met sight unseen, a level is worked out from one safe spot to the
next (the guards kept circling while he looks ahead); without such spots
it's learned only by dying.  Along the level's solution (with a player's
reactions: build/solutions-react8), every CHECK frames, a search asks
whether the hero could just stay alive there for HOLD frames, committing
to nothing (circling, shuttling, leading the guards around).  The score:
the longest stretch with no such spot (seconds), and the share of the
route that has one.

    python3 tools/breath.py [LEVEL ...]

Writes build/breath.txt (level, longest stretch s, share %).  Public
domain (Unlicense)."""
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim                      # noqa: E402
import solve                    # noqa: E402
import progress                 # noqa: E402

CHECK = 120                     # (frames between the spots looked at: 2 s)
HOLD = 300                      # (frames he must be able to stay alive: 5 s)
REACT = 8
WIDTH = 4
MOVES = [('L', solve.L), ('R', solve.R), ('U', sim.J_UP), ('D', sim.J_DOWN), ('w', 0)]


def survive(s, g0):
    """can he stay alive HOLD frames from g0 (a beam search, nearest guard
    as far as can be)?"""
    end = g0.loops + HOLD
    beam = [(g0, None)]
    seen = set()
    while beam:
        nxt = []
        for g, last in beam:
            for name, joy in MOVES:
                h = g.clone()
                if joy and last is not None and joy != last:
                    for i in range(REACT):
                        h.step(0)
                        if h.dead:
                            break
                if h.dead:
                    continue
                s.play(h, joy)
                if h.dead:
                    continue
                if h.loops >= end or h.done:
                    return True
                key = (h.r, h.c, tuple((gd.r, gd.c) for gd in h.guards), h.loops // 30)
                if key in seen:
                    continue
                seen.add(key)
                nxt.append((h, joy if joy else last))
        nxt.sort(key=lambda t: solve.danger(t[0]))
        beam = nxt[:WIDTH]
    return False


def measure(n):
    progress.started(n)
    path = os.path.join(solve.ROOT, 'build', 'solutions-react%d' % REACT, '%d.txt' % n)
    if not os.path.exists(path):
        return n, None
    rows = solve.level_rows(n)
    s = solve.Solver(rows)
    g = sim.Game(rows)
    joys = [j for line in open(path) for k, j in [map(int, line.split())] for _ in range(k)]
    spots = []
    for i, j in enumerate(joys):
        if i % CHECK == 0 and i:
            spots.append(survive(s, g.clone()))
        g.step(j)
        if g.dead or g.done:
            break
    # the longest run of spots with no breather (each CHECK frames)
    run = best = 0
    for ok in spots:
        run = 0 if ok else run + 1
        best = max(best, run)
    share = 100.0 * sum(spots) / max(1, len(spots))
    return n, (best * CHECK / 60.0, share, ''.join('o' if ok else '-' for ok in spots))


if __name__ == '__main__':
    levels = [int(a) for a in sys.argv[1:]] or list(range(1, 151))
    out = {}
    pg = progress.Progress(len(levels))
    with Pool(progress.workers(), initializer=progress.init, initargs=(pg.running,)) as p:
        for n, m in p.imap_unordered(measure, levels):
            out[n] = m
            if m is None:
                pg.print('level %3d: (no solution with reactions)' % n)
            else:
                pg.print('level %3d: longest stretch without a breather %4.0f s, breathers on %3.0f%%  %s'
                         % (n, m[0], m[1], m[2]))
            pg.finished(n)
    pg.close()
    path = os.path.join(solve.ROOT, 'build', 'breath.txt')
    table = {}                          # (merged with what's there)
    if os.path.exists(path):
        for line in open(path):
            n, a, b = line.split()
            table[int(n)] = (float(a), float(b))
    table.update({n: m[:2] for n, m in out.items() if m})
    with open(path, 'w') as f:
        for n in sorted(table):
            f.write('%d %.0f %.0f\n' % (n, table[n][0], table[n][1]))
