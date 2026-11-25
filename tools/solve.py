#!/usr/bin/env python3
"""solve.py: finds a way through a level by playing it in tools/sim.py.

A beam search over the hero's choices: each time he stands on a cell he
can walk left or right, climb up or down, dig left or right, or wait a
moment; each choice is played out (guards and all) to his next cell.  The
most promising states are kept: geodes collected, then the distance to
the nearest geode (or, at the end, to the exit) along the ways he can go
(digging included), then time.  A state where he's caught is dropped.

    python3 tools/solve.py LEVEL [LEVEL ...]

Prints whether each level was solved, in how many game loops, and saves
the solution's input (build/solutions/LEVEL.txt: pairs "loops joy").
Public domain (Unlicense)."""
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, HERE)
import sim                      # noqa: E402
import levelgen                 # noqa: E402

J = sim
L, R, F = J.J_LEFT, J.J_RIGHT, J.J_FIRE
# an action is a list of moves, each played to the hero's next decision
ACTIONS = [('L', [L]), ('R', [R]), ('U', [J.J_UP]), ('D', [J.J_DOWN]),
           ('dl', [F | L]), ('dr', [F | R]), ('w', [0]),
           # dig beside him, step in and drop through
           ('dropl', [F | L, L]), ('dropr', [F | R, R]),
           # a double dig: over one, dig the far hole, back, dig the near
           # one, drop into it, dig under the far one, drop through it
           ('ddl', [L, F | L, R, F | L, L, F | L, L]),
           ('ddr', [R, F | R, L, F | R, R, F | R, R]),
           # a long wait (for a guard to come, to climb out, to drop a geode)
           ('W', [0] * 10)]
WAIT = 6                         # (frames a wait lasts)
MAXRUN = 40                      # (frames an action may take, at most)
PER_CELL = 3                     # (beam states with the hero on one cell, at most)


def level_rows(n):
    data = open(os.path.join(ROOT, 'build', 'LEVELS.DAT'), 'rb').read()
    return levelgen.decode(data[16 + 240 * (n - 1):16 + 240 * n])


def dist_to(grid, targets):
    """frames-free distance (moves) from every cell to the nearest target,
    the hero's ways including digging (levelgen's model)"""
    fwd, back = levelgen.graph(grid, dig=True)
    dist = {t: 0 for t in targets}
    q = deque(targets)
    while q:
        p = q.popleft()
        for r in back.get(p, ()):
            if r not in dist:
                dist[r] = dist[p] + 1
                q.append(r)
    return dist


class Solver:
    def __init__(self, rows, width=200, per_cell=PER_CELL, brave=1.0):
        self.rows = rows
        self.width = width
        self.per_cell = per_cell
        self.brave = brave              # (danger's weight: less, bolder)
        g0 = [list(r.replace('T', '.').replace('E', '.').replace('P', '.').replace('X', '.')) for r in rows]
        self.grid = g0
        self.geodes = [(r, c) for r in range(15) for c in range(32) if rows[r][c] == 'T']
        xs = [(r, c) for r in range(15) for c in range(32) if rows[r][c] == 'X']
        col = xs[0][1]
        ge = [row[:] for row in g0]
        for y in range(max(r for r, c in xs if c == col) + 1):
            ge[y][col] = 'X'
        self.exit_dist = dist_to(ge, [(0, col)])
        self.gdist = {p: dist_to(g0, [p]) for p in self.geodes}
        self.extra = {}

    def score(self, g):
        """bigger is better"""
        here = (g.r, g.c)
        if g.g_left:
            ds = []
            for (r, c) in g_geodes(g):
                ds.append(self.gdist[(r, c)].get(here, 999) if (r, c) in self.gdist
                          else self.reach(g, (r, c)))
            # a geode a guard carries: go after him (trapped, he drops it
            # above himself)
            for gd in g.guards:
                if gd.carry:
                    ds.append(abs(gd.c - g.c) + 3 * abs(gd.r - g.r) + 4)
            d = min(ds, default=999)
            if d >= 999:
                return None             # (nowhere to go from here: stuck)
            return (len(self.geodes) - g.g_left) * 1000 - d * 10 - g.loops * 0.01 - danger(g) * self.brave
        d = self.exit_dist.get(here, 999)
        if d >= 999:
            return None
        return 100000 - d * 10 - g.loops * 0.01 - danger(g) * self.brave

    def reach(self, g, p):
        """distance to a geode not where the level put it (one a guard put
        down): computed once per place"""
        if p not in self.extra:
            self.extra[p] = dist_to(self.grid, [p])
        return self.extra[p].get((g.r, g.c), 999)

    def play(self, g, joy):
        """the action from a decision point to the next: the inputs used"""
        used = []
        n = WAIT if joy == 0 else MAXRUN
        for i in range(n):
            j = joy if (i == 0 or not joy & J.J_FIRE) else (joy & ~J.J_FIRE)
            if joy & J.J_FIRE and i > 0:
                j = 0
            g.step(j)
            used.append(j)
            if g.dead or g.done:
                break
            if joy and i > 0 and g.t == 0 and g.dig == 0:
                break
        return used

    def solve(self, max_steps=1200, report=None):
        start = sim.Game(self.rows)
        beam = [(self.score(start), start, [])]
        seen = set()
        for step in range(max_steps):
            nxt = {}
            for sc, g, path in beam:
                for name, moves in ACTIONS:
                    h = g.clone()
                    used = []
                    for joy in moves:
                        used += self.play(h, joy)
                        if h.dead or h.done:
                            break
                    if h.dead:
                        continue
                    if h.done:
                        return path + used, h
                    key = (h.r, h.c, h.g_left, h.ex_state,
                           tuple((gd.r, gd.c, gd.st) for gd in h.guards),
                           tuple(tuple(x[:3]) for x in h.holes if x[2]))
                    if key in seen:
                        continue
                    s2 = self.score(h)
                    if s2 is None:
                        continue
                    if key not in nxt or nxt[key][0] < s2:
                        nxt[key] = (s2, h, path + used)
            if not nxt:
                if report is not None:
                    report.update(end='no states left', step=step, best=beam[0][1])
                return None, None
            seen.update(nxt.keys())
            # the best, but not all alike: at most PER_CELL states with the
            # hero on the same cell (else one greedy plan crowds out the rest)
            beam, per = [], {}
            for t in sorted(nxt.values(), key=lambda t: -t[0]):
                k = (t[1].r, t[1].c, t[1].g_left)
                if per.get(k, 0) < self.per_cell:
                    per[k] = per.get(k, 0) + 1
                    beam.append(t)
                    if len(beam) == self.width:
                        break
        if report is not None:
            report.update(end='out of steps', step=max_steps, best=beam[0][1])
        return None, None


# the searches tried in turn, until one finds a way: (width, per cell, brave)
TRIES = [(200, 3, 1.0), (600, 6, 0.3)]


def solve_hard(rows, report=None):
    """the plain search first, then wider and bolder ones"""
    for w, pc, b in TRIES:
        joys, g = Solver(rows, w, pc, b).solve(report=report)
        if joys is not None:
            return joys, g
    return None, None


def danger(g):
    """how close the free guards are (nearer: more)"""
    d = 0
    for gd in g.guards:
        if not gd.st:
            n = abs(gd.c - g.c) + 3 * abs(gd.r - g.r)
            if n < 6:
                d += (6 - n) * 40
    return d


def g_geodes(g):
    """the geodes on the map now"""
    return [(r, c) for r in range(15) for c in range(32) if g.map[r][c] == sim.C_GEODE]


def pairs(joys):
    out = []
    for j in joys:
        if out and out[-1][1] == j and out[-1][0] < 255:
            out[-1][0] += 1
        else:
            out.append([1, j])
    return out


def verify(n, pr, rows=None):
    """the solution played on the real game (the VMC10 emulator, a test
    build replaying it): True if the game goes on to the next level (with
    rows, on that level in place of the file's level n)"""
    import re
    import shutil
    import subprocess
    import profile as prof
    sd = os.path.join(ROOT, 'build', 'sd-verify-%d' % n)
    os.makedirs(sd, exist_ok=True)
    for a, b in (('geode.bin', 'GEODE.BIN'), ('LEVELS.DAT', 'LEVELS.DAT')):
        shutil.copy(os.path.join(ROOT, 'build', a), os.path.join(sd, b))
    if rows is not None:
        with open(os.path.join(sd, 'LEVELS.DAT'), 'r+b') as f:
            f.seek(16 + 240 * (n - 1))
            f.write(levelgen.encode(rows))
    buf = prof.sym('replay_buf')
    data = sim.replay_hex(pr)
    if len(data) // 2 > 2048:                      # (RP_SIZE)
        return False
    pokes = ['poke:%04X,%s' % (buf + i // 2, data[i:i + 64]) for i in range(0, len(data), 64)]
    loops = sum(k for k, j in pr)
    lv = prof.sym('level')
    args = [os.path.join(prof.VMC10, 'build', 'headless'), os.path.join(prof.VMC10, 'roms', 'MC10.BIN'),
            'mcx32sd:' + os.path.join(prof.VMC10, 'roms', 'mcx32sd_flash.bin'), '8k', 'sd:' + sd,
            'frames:200', 'type:RUNM"GEODE"\n', 'frames:240', 'type: ', 'frames:60'] + pokes + [
            'poke:%04X,%04X' % (prof.sym('rp_pend'), buf), 'type:N%03d' % n,
            'frames:%d' % (loops + 1200), 'mem:%04X,1' % prof.sym('lives')]   # (the load, the bonus count)
    out = subprocess.run(args, capture_output=True, text=True).stdout
    shutil.rmtree(sd, ignore_errors=True)
    m = re.findall(r'^mem %04X: (\w+)' % prof.sym('lives'), out, re.M)
    return bool(m) and int(m[-1], 16) == 4        # (3, and a life for the level)


if __name__ == '__main__':
    import time
    os.makedirs(os.path.join(ROOT, 'build', 'solutions'), exist_ok=True)
    for a in sys.argv[1:]:
        n = int(a)
        t = time.time()
        joys, g = solve_hard(level_rows(n))
        if joys is None:
            print('level %d: no solution found (%.0f s)' % (n, time.time() - t))
            continue
        pr = pairs(joys)
        with open(os.path.join(ROOT, 'build', 'solutions', '%d.txt' % n), 'w') as f:
            f.write(''.join('%d %d\n' % (k, j) for k, j in pr))
        ok = verify(n, pr)
        print('level %d: solved in %d loops (%d input pairs, %.0f s); on the real game: %s'
              % (n, len(joys), len(pr), time.time() - t, 'WINS' if ok else 'fails'))
