#!/usr/bin/env python3
"""levelgen.py: Geode Runner's level generator (a prototype in Python, to
be ported to the 6803 once the rules settle).

Level N is always the same level: N seeds the generator.  A level is 15
rows of 32 cells:

    .  air          B  brick (diggable)    S  stone (can't be dug)
    H  ladder       -  cable (hang from it, travel along, drop off)
    T  a geode      P  the hero's start    E  a thief's start
    X  the hidden exit ladder (appears when every geode is collected)

How a level is made sure to be finishable: the generator lays out floors,
ladders, gaps, cables and stone, then works out where the hero can go
(walking, climbing, hanging, falling and digging down through brick) and
puts geodes only where he can both get to and get back from, so they can
be collected in any order.  The exit ladder climbs to the top from a
place he can reach.

    python3 tools/levelgen.py N [N2 ...]     print levels
    python3 tools/levelgen.py --sheet OUT.png N1 N2 ...   a contact sheet

Public domain (Unlicense)."""
import os
import random
import sys

COLS, ROWS = 32, 15
SOLID = 'BS'
BANDS = [2, 5, 8, 11]           # floor rows (row 14 is the bottom: stone)


def params(n):
    """difficulty for level n (1 = easiest)"""
    t = min(1.0, (n - 1) / 60)              # ramps up over the first 60 levels
    return dict(
        stone=0.08 + 0.32 * t,              # share of floor that is stone
        gaps=0.10 + 0.10 * t,               # chance a floor run ends in a gap
        ladders=3 if t < 0.3 else 2 if t < 0.7 else 1,   # extra ladders per band
        cables=0.0 if n < 3 else 0.25 + 0.35 * t,        # chance a gap gets a cable
        double=0.0 if n < 8 else 0.15 + 0.35 * t,        # chance a run is two bricks deep
        geodes=6 + int(6 * t),
        dig_geodes=0 if n < 2 else 1 + int(3 * t),       # geodes that need digging to reach
        thieves=min(5, 1 + n // 6),
    )


# ---------------------------------------------------------------- movement

def at(g, r, c):
    if r < 0:
        return '.'
    if r >= ROWS or c < 0 or c >= COLS:
        return 'S'
    return g[r][c]


def supported(g, r, c):
    """standing (or hanging, or on a ladder) rather than falling"""
    here, below = at(g, r, c), at(g, r + 1, c)
    return here in 'HX-' or below in SOLID + 'HX'


def moves(g, r, c, dig=True):
    """the cells the hero can get to from (r, c) in one move"""
    here = at(g, r, c)
    if not supported(g, r, c):
        return [(r + 1, c)]                 # falling
    out = []
    for dc in (-1, 1):                      # walk or swing along
        if at(g, r, c + dc) not in SOLID:
            out.append((r, c + dc))
    if here in 'HX' and at(g, r - 1, c) not in SOLID and r > 0:
        out.append((r - 1, c))              # climb up
    below = at(g, r + 1, c)
    if below in 'HX' or (here in 'HX-' and below not in SOLID):
        out.append((r + 1, c))              # climb down, or let go
    if dig and here not in 'HX-' and at(g, r + 1, c) in SOLID:
        for dc in (-1, 1):
            side, under = at(g, r, c + dc), at(g, r + 1, c + dc)
            # dig the brick below-left/right, step over and drop through it
            if side not in SOLID + 'HX-' and under == 'B' and at(g, r + 2, c + dc) not in SOLID:
                out.append((r + 1, c + dc))
            # two bricks deep: dig two side by side, drop into the near one,
            # dig the brick under the far one from inside, drop through it
            far = c + 2 * dc
            if (side not in SOLID + 'HX-' and at(g, r, far) not in SOLID + 'HX-'
                    and under == 'B' and at(g, r + 1, far) == 'B'
                    and at(g, r + 2, far) == 'B' and at(g, r + 3, far) not in SOLID
                    and at(g, r + 2, c + dc) in SOLID):
                out.append((r + 2, far))
    return out


def reach(g, start, dig=True):
    seen, todo = {start}, [start]
    while todo:
        p = todo.pop()
        for q in moves(g, *p, dig=dig):
            if 0 <= q[0] < ROWS and q not in seen and at(g, *q) not in SOLID:
                seen.add(q)
                todo.append(q)
    return seen


def standing(g, p):
    r, c = p
    return at(g, r, c) not in SOLID + 'HX-' and at(g, r + 1, c) in SOLID


# ---------------------------------------------------------------- building

def build(n):
    rnd = random.Random(n * 7919 + 17)
    P = params(n)
    g = [['.'] * COLS for _ in range(ROWS)]
    g[14] = ['S'] * COLS
    gaps = {}                                       # band row -> gap columns
    for f in BANDS:
        c = 0
        gaps[f] = []
        while c < COLS:                             # runs of floor and gaps
            run = rnd.randint(4, 12)
            kind = 'S' if rnd.random() < P['stone'] else 'B'
            for x in range(c, min(COLS, c + run)):
                g[f][x] = kind
            c += run
            if c < COLS and rnd.random() < P['gaps'] * 3:
                w = rnd.randint(1, 4)
                gaps[f].append((c, min(COLS, c + w)))
                c += w
        # some brick runs two deep (the row under the floor)
        if P['double'] and f + 1 < 14:
            for x in range(COLS):
                if g[f][x] == 'B' and rnd.random() < P['double'] and x % 6 == 0:
                    for y in range(x, min(COLS, x + rnd.randint(3, 6))):
                        if g[f][y] == 'B':
                            g[f + 1][y] = 'B'
    # ladders between neighbouring bands (and from the bottom to the lowest)
    levels = [0] + BANDS + [14]                     # 0: the top row's "floor"
    for i in range(1, len(levels) - 1):
        top, bot = levels[i], levels[i + 1]         # ladder from floor top down to bot
        count = 1 + rnd.randint(0, P['ladders'])
        cols = []
        for _ in range(50):                         # spread out, never side by side
            x = rnd.randint(1, COLS - 2)
            if all(abs(x - y) > 3 for y in cols):
                cols.append(x)
            if len(cols) == count:
                break
        for x in cols:
            if g[bot][x] not in SOLID:
                g[bot][x] = 'B'                     # something to stand on at its foot
            for y in range(top, bot):
                g[y][x] = 'H'
    # cables over some gaps, in the row just above the floor
    for f in BANDS:
        for (a, b) in gaps[f]:
            if rnd.random() < P['cables'] and b - a >= 2:
                for x in range(max(0, a - 1), min(COLS, b + 1)):
                    if g[f - 1][x] == '.':
                        g[f - 1][x] = '-'
    return g, rnd, P


def place(g, rnd, P, n):
    """the hero, the exit, the geodes, the thieves; None if the level is poor"""
    starts = [(13, c) for c in range(COLS) if standing(g, (13, c))]
    if not starts:
        return None
    hero = rnd.choice(starts)
    out = reach(g, hero)
    if len(out) < 120:
        return None
    # cells he can reach and come back from
    both = [p for p in out if hero in reach(g, p)]
    stand = [p for p in both if standing(g, p) and p != hero]
    nodig = reach(g, hero, dig=False)
    needdig = [p for p in stand if p not in nodig]
    easy = [p for p in stand if p in nodig]
    k = min(P['dig_geodes'], len(needdig))
    if len(easy) < P['geodes'] - k:
        return None
    geodes = rnd.sample(needdig, k) + rnd.sample(easy, P['geodes'] - k)
    # the exit: a column climbing from a reachable standing cell to the top
    cands = [p for p in both if standing(g, p) and p[0] <= 7 and p not in geodes]
    rnd.shuffle(cands)
    exit_col = None
    for (r, c) in cands:
        if all(at(g, y, c) in '.B' for y in range(0, r)):
            exit_col = (r, c)
            break
    if not exit_col:
        return None
    # thieves: reachable standing cells away from the hero
    far = [p for p in stand if abs(p[1] - hero[1]) + 3 * abs(p[0] - hero[0]) > 12
           and p not in geodes]
    if len(far) < P['thieves']:
        return None
    thieves = []
    rnd.shuffle(far)
    for p in far:                                   # not side by side
        if all(abs(p[1] - q[1]) > 2 or p[0] != q[0] for q in thieves):
            thieves.append(p)
        if len(thieves) == P['thieves']:
            break
    if len(thieves) < P['thieves']:
        return None
    lv = [row[:] for row in g]
    for (r, c) in geodes:
        lv[r][c] = 'T'
    for (r, c) in thieves:
        lv[r][c] = 'E'
    lv[hero[0]][hero[1]] = 'P'
    r, c = exit_col
    for y in range(0, r + 1):
        if lv[y][c] == '.':
            lv[y][c] = 'X'
    # with the exit open (its bricks become ladder), the top must be reachable
    opened = [row[:] for row in g]
    for y in range(0, r + 1):
        opened[y][c] = 'X'
    if (0, c) not in reach(opened, hero):
        return None
    return lv


def level(n):
    """level n: 15 strings of 32 cells (retries with the next seed if poor)"""
    for attempt in range(200):
        g, rnd, P = build(n + attempt * 100003)
        P = params(n)
        lv = place(g, rnd, P, n)
        if lv:
            return [''.join(row) for row in lv]
    raise RuntimeError('no level %d' % n)


def sheet(out, numbers):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'mockups'))
    from plat_cg6 import render, image
    from PIL import Image, ImageDraw
    cols = 4
    rows = (len(numbers) + cols - 1) // cols
    cw, ch = 128 * 4, 192 * 2                 # CG6 pixels are twice as wide as tall: 4:3
    S = Image.new('RGB', (cols * (cw + 12) + 12, rows * (ch + 28) + 12), (24, 24, 24))
    d = ImageDraw.Draw(S)
    for i, n in enumerate(numbers):
        lv = level(n)
        status = "SCORE 000000  LEVEL %03d  LIVES 3" % n
        im = image(render(lv, status)).resize((cw, ch), Image.NEAREST)
        x, y = 12 + (i % cols) * (cw + 12), 12 + (i // cols) * (ch + 28)
        S.paste(im, (x, y))
        P = params(n)
        d.text((x, y + ch + 6), "level %d: %d geodes (%d by digging), %d thieves"
               % (n, P['geodes'], P['dig_geodes'], P['thieves']), fill=(220, 220, 220))
    S.save(out)


if __name__ == '__main__':
    if sys.argv[1] == '--sheet':
        sheet(sys.argv[2], [int(a) for a in sys.argv[3:]])
    else:
        for a in sys.argv[1:]:
            print('level', a)
            print('\n'.join(level(int(a))))
