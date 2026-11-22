#!/usr/bin/env python3
"""levelgen.py: Geode Runner's level generator (a prototype in Python, to
be ported to the 6803 once the rules settle).

Level N is always the same level: N seeds the generator.  A level is 15
rows of 32 cells:

    .  air          B  brick (diggable)    S  stone (can't be dug)
    H  ladder       -  cable (hang from it, travel along, drop off)
    T  a geode      P  the hero's start    E  a guard's start
    X  the hidden exit ladder (appears when every geode is collected)

Levels come in styles, mixed more as the levels go up: floors, scattered
ledges, rooms walled with stone, a brick pyramid with hidden chambers,
caverns dug out of solid rock, mirror images, and, every 10th level, a
word spelled in ladders.

How every level is made sure to be finishable: a style lays out its
shapes, then the generator works out where the hero can go (walking,
climbing, hanging, falling, and digging down through one or two layers of
brick) and where he can get back from, and adds ladders until nearly all
of the level is both.  Geodes go only where he can get to and back from,
so they can be collected in any order; the exit ladder climbs to the top
from such a place, one column in from either edge.  Several
candidates are made and the most interesting kept.

    python3 tools/levelgen.py N [N2 ...]     print levels
    python3 tools/levelgen.py --sheet OUT.png N1 N2 ...   a contact sheet
    python3 tools/levelgen.py --dat OUT COUNT     levels 1..COUNT as a level file (the game: 150)
    python3 tools/levelgen.py --check FILE N...   compare a level file with the generator

The level file (LEVELS.DAT on the SD card): a 16-byte header, "GR", a
format number (1), a reserved byte, the number of levels (2 bytes, high
first), 10 bytes of zeros; then each level, 240 bytes, at offset
16 + 240 * (N - 1): its 15 rows of 32 cells, two cells a byte (the left
one in the high nibble), with the codes in CODES below.

Public domain (Unlicense)."""
import os
import sys

COLS, ROWS = 32, 15
SOLID = 'BS'
WORDS = [('DIG', 'DEEP'), ('MC10', '1983'), ('GEMS', 'RUN'), ('ROCK', 'ON'),
         ('CAVE', 'IN'), ('HI', 'MOM'), ('LOOT', 'DIG'), ('GO', 'WEST'),
         ('OH', 'NO'), ('GEO', 'DES'), ('BLRP', '!'), ('HALF', 'WAY?'),
         ('DONT', 'STOP'), ('THE', 'END?'), ('LAST', 'ONE!')]    # levels 10, 20 ... 150
HERE = os.path.dirname(os.path.abspath(__file__))
CODES = '.BSH-TPEX'                 # a cell's code in the level file: its index
HEADER, RECORD = 16, 240


def params(n):
    """difficulty for level n (1 = easiest)"""
    t = min(1.0, (n - 1) / 120)             # ramps up over the first 120 of 150
    return dict(
        t=t,
        stone=0.08 + 0.32 * t,              # share of floor that is stone
        gaps=0.10 + 0.10 * t,               # chance a floor run ends in a gap
        ladders=3 if t < 0.3 else 2 if t < 0.7 else 1,   # extra ladders per floor
        cables=0.0 if n < 3 else 0.25 + 0.35 * t,        # chance a gap gets a cable
        double=0.0 if n < 8 else 0.15 + 0.35 * t,        # chance of two-deep brick
        geodes=6 + int(6 * t),
        dig_geodes=0 if n < 4 else 1 + int(3 * t),       # geodes only digging reaches
        guards=min(4, 1 + n // 6),          # (4 at most: the MC-10 keeps up)
        bottom=0.0 if n < 60 else min(1.0, (n - 60) / 60),  # stone in the bottom floor
    )


# ---------------------------------------------------------------- randomness

class Rng:
    """the generator's own random numbers (xorshift32), so a level depends
    only on this code and its number, never on the Python version"""

    def __init__(self, seed):
        self.s = (seed * 2654435761 + 0x9E3779B9) & 0xFFFFFFFF or 1
        for _ in range(4):
            self.next()

    def next(self):
        x = self.s
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self.s = x
        return x

    def random(self):                   # [0, 1), exact in binary floating point
        return self.next() / 4294967296

    def randint(self, a, b):            # a..b inclusive
        return a + self.next() % (b - a + 1)

    def choice(self, seq):
        return seq[self.randint(0, len(seq) - 1)]

    def shuffle(self, lst):             # Fisher-Yates
        for i in range(len(lst) - 1, 0, -1):
            j = self.randint(0, i)
            lst[i], lst[j] = lst[j], lst[i]

    def sample(self, seq, k):
        lst = list(seq)
        self.shuffle(lst)
        return lst[:k]


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
        out = [(r + 1, c)]                  # falling
    else:
        out = []
        for dc in (-1, 1):                  # walk or swing along
            if at(g, r, c + dc) not in SOLID:
                out.append((r, c + dc))
        if here in 'HX' and r > 0 and at(g, r - 1, c) not in SOLID:
            out.append((r - 1, c))          # climb up
        below = at(g, r + 1, c)
        if below in 'HX' or (here in 'HX-' and below not in SOLID):
            out.append((r + 1, c))          # climb down, or let go
        if dig and here not in 'HX-' and below in SOLID:
            for dc in (-1, 1):
                side, under = at(g, r, c + dc), at(g, r + 1, c + dc)
                # dig the brick below-left/right, step over, drop through it
                if side not in SOLID + 'HX-' and under == 'B' and at(g, r + 2, c + dc) not in SOLID:
                    out.append((r + 1, c + dc))
                # two bricks deep: dig two side by side, drop into the near
                # one, dig the brick under the far one, drop through it
                far = c + 2 * dc
                if (side not in SOLID + 'HX-' and at(g, r, far) not in SOLID + 'HX-'
                        and under == 'B' and at(g, r + 1, far) == 'B'
                        and at(g, r + 2, far) == 'B' and at(g, r + 3, far) not in SOLID
                        and at(g, r + 2, c + dc) in SOLID):
                    out.append((r + 2, far))
    return [q for q in out if 0 <= q[0] < ROWS and at(g, *q) not in SOLID]


def graph(g, dig=True):
    """every open cell's moves, and the reverse"""
    fwd, back = {}, {}
    for r in range(ROWS):
        for c in range(COLS):
            if g[r][c] in SOLID:
                continue
            fwd[(r, c)] = moves(g, r, c, dig)
            for q in fwd[(r, c)]:
                back.setdefault(q, []).append((r, c))
    return fwd, back


def bfs(edges, start):
    seen, todo = {start}, [start]
    while todo:
        p = todo.pop()
        for q in edges.get(p, ()):
            if q not in seen:
                seen.add(q)
                todo.append(q)
    return seen


def reach(g, start, dig=True):
    return bfs(graph(g, dig)[0], start)


def two_way(g, start):
    """(cells the hero can reach from start, cells he can also get back from)"""
    fwd, back = graph(g)
    out = bfs(fwd, start)
    return out, out & bfs(back, start)


def standing(g, p):
    r, c = p
    return at(g, r, c) not in SOLID + 'HX-' and at(g, r + 1, c) in SOLID


def stand_cells(g):
    return [(r, c) for r in range(ROWS - 1) for c in range(COLS) if standing(g, (r, c))]


# ---------------------------------------------------------------- repair

def ladder(g, c, r0, r1):
    """a ladder in column c from row r0 down to row r1 (inclusive)"""
    for y in range(r0, r1 + 1):
        g[y][c] = 'H'


def beside(g, c, r0, r1, keep=()):
    """would a ladder in column c, rows r0..r1, run alongside another, or
    through cells to be kept as they are (a word's letters)?"""
    return (any(at(g, y, c + d) in 'HX' for y in range(r0, r1 + 1) for d in (-1, 1))
            or any((y, c) in keep for y in range(r0, r1 + 1)))


def repair(g, rnd, start, tries=40, keep=(), slack=20):
    """add ladders until nearly every standing cell (all but 1/slack) is
    two-way reachable from start; False if it can't"""
    for _ in range(tries):
        out, both = two_way(g, start)
        stands = stand_cells(g)
        bad = [p for p in stands if p not in both]
        if len(bad) <= len(stands) // slack:
            return True
        rnd.shuffle(bad)
        walk = graph(g, dig=False)[0]
        fixed = False
        for (r, c) in bad[:12]:
            # the platform he'd be on there: try ladders from its cells
            plat = sorted({q[1] for q in bfs(walk, (r, c)) if q[0] == r})
            rnd.shuffle(plat)
            for x in plat[:8]:
                if g[r][x] in 'H-' or g[r + 1][x] == 'H':
                    continue
                for y in range(r + 1, ROWS - 1):        # down to a good place
                    if (y, x) in both and at(g, y + 1, x) in SOLID + 'H':
                        if not beside(g, x, r + 1, y, keep):
                            ladder(g, x, r + 1, y)
                            fixed = True
                        break
                if not fixed:                           # or up to one
                    for y in range(r - 1, -1, -1):
                        if (y, x) in both and at(g, y + 1, x) in SOLID:
                            if not beside(g, x, y + 1, r, keep):
                                ladder(g, x, y + 1, r)
                                fixed = True
                            break
                if fixed:
                    break
            if fixed:
                break
        if not fixed:
            return False
    return False


# ---------------------------------------------------------------- styles

def blank():
    g = [['.'] * COLS for _ in range(ROWS)]
    g[14] = ['S'] * COLS
    return g


def floor_run(g, rnd, P, r, c0, c1):
    kind = 'S' if rnd.random() < P['stone'] else 'B'
    for x in range(max(0, c0), min(COLS, c1)):
        g[r][x] = kind


def add_cables(g, rnd, P):
    """cables across gaps between floors, in the row just above"""
    for r in range(2, 14):
        c = 1
        while c < COLS:
            if g[r][c] == '.' and g[r][c - 1] in SOLID:
                e = c
                while e < COLS and g[r][e] == '.':
                    e += 1
                if (e < COLS and g[r][e] in SOLID and 2 <= e - c <= 8
                        and rnd.random() < P['cables']
                        and all(g[r - 1][x] == '.' for x in range(c - 1, e + 1))):
                    for x in range(c - 1, e + 1):
                        g[r - 1][x] = '-'
                c = e
            c += 1


def add_double(g, rnd, P):
    """some brick floors two deep"""
    if not P['double']:
        return
    for r in range(2, 12):
        for x in range(COLS):
            if (g[r][x] == 'B' and g[r + 1][x] == '.' and g[r - 1][x] == '.'
                    and rnd.random() < P['double'] / 4):
                for y in range(x, min(COLS, x + rnd.randint(3, 6))):
                    if g[r][y] == 'B' and g[r + 1][y] == '.' and g[r + 2][y] == '.':
                        g[r + 1][y] = 'B'


def style_floors(rnd, P, even=False):
    """floors right across, at varying heights (or evenly spaced, for the
    first levels), with gaps"""
    g = blank()
    rows, r = [], rnd.randint(2, 3)
    while r <= 11:
        rows.append(r)
        r += rnd.choice((3, 3, 3, 4, 2)) if r < 10 else 4
    if even:
        rows = [2, 5, 8, 11]
    for f in rows:
        c = 0
        while c < COLS:
            run = rnd.randint(4, 12)
            floor_run(g, rnd, P, f, c, c + run)
            c += run
            if c < COLS and rnd.random() < P['gaps'] * 3:
                c += rnd.randint(1, 4)
    levels = [0] + rows + [14]
    for i in range(1, len(levels) - 1):
        top, bot = levels[i], levels[i + 1]
        want, cols = 1 + rnd.randint(0, P['ladders']), []
        for _ in range(50):
            x = rnd.randint(1, COLS - 2)
            if all(abs(x - y) > 3 for y in cols):
                cols.append(x)
            if len(cols) == want:
                break
        for x in cols:
            if g[bot][x] not in SOLID:
                g[bot][x] = 'B'
            ladder(g, x, top, bot - 1)
    return g


def style_ledges(rnd, P):
    """many short ledges at staggered heights"""
    g = blank()
    for _ in range(rnd.randint(14, 22)):
        for _ in range(30):
            r, w = rnd.randint(2, 12), rnd.randint(3, 9)
            c = rnd.randint(0, COLS - w)
            span = range(max(0, c - 1), min(COLS, c + w + 1))
            if all(g[y][x] == '.' for y in (r - 1, r, r + 1) for x in span):
                floor_run(g, rnd, P, r, c, c + w)
                break
    return g


def style_rooms(rnd, P):
    """floors cut into rooms by stone walls"""
    g = style_floors(rnd, P)
    floors = [r for r in range(1, 14) if sum(ch in SOLID for ch in g[r]) > COLS // 2]
    levels = floors + [14]
    for i in range(len(levels) - 1):
        top, bot = levels[i], levels[i + 1]
        if bot - top < 3:
            continue
        for _ in range(rnd.randint(1, 2)):
            x = rnd.randint(4, COLS - 5)
            if any(g[y][x] == 'H' for y in range(top, bot)):
                continue
            for y in range(top + 1, bot):
                g[y][x] = 'S'
    return g


def style_pyramid(rnd, P):
    """a brick pyramid with chambers inside, ledges around it"""
    g = style_ledges(rnd, dict(P, stone=P['stone'] / 2))
    cx, top = rnd.randint(10, 21), rnd.randint(4, 6)
    for r in range(top, 14):
        half = (r - top) + 1
        for x in range(cx - half, cx + half + 1):
            if 0 <= x < COLS:
                g[r][x] = 'S' if (r - top) % 3 == 2 and rnd.random() < P['stone'] else 'B'
    for x in range(cx - 1, cx + 2):                 # headroom on top
        g[top - 1][x] = '.'
    for _ in range(rnd.randint(2, 4)):              # chambers: hollow pockets
        r = rnd.randint(top + 2, 12)
        half = r - top
        w = rnd.randint(2, 4)
        x0 = rnd.randint(cx - half + 2, max(cx - half + 2, cx + half - 2 - w))
        for x in range(x0, x0 + w):
            if g[r + 1][x] in SOLID:
                g[r][x] = '.'
    return g


def style_cavern(rnd, P):
    """tunnels and shafts dug out of solid rock"""
    g = blank()
    for r in range(2, 14):
        for x in range(COLS):
            g[r][x] = 'B'
    for _ in range(int(40 * P['stone']) + 3):       # stone seams
        r, x, w = rnd.randint(3, 13), rnd.randint(0, COLS - 1), rnd.randint(2, 6)
        for k in range(x, min(COLS, x + w)):
            g[r][k] = 'S'
    tunnels, r = [], rnd.randint(3, 4)
    while r <= 13:
        tunnels.append(r)
        r += rnd.choice((2, 3, 3))
    for t in tunnels:                               # each tunnel: segments
        c = rnd.randint(0, 4)
        while c < COLS:
            w = rnd.randint(5, 16)
            for x in range(c, min(COLS, c + w)):
                g[t][x] = '.'
            c += w + rnd.randint(2, 5)
    for i in range(len(tunnels) - 1):               # shafts between tunnels
        for _ in range(rnd.randint(1, 2)):
            x = rnd.randint(1, COLS - 2)
            if g[tunnels[i]][x] == '.' and g[tunnels[i + 1]][x] == '.':
                ladder(g, x, tunnels[i] + 1, tunnels[i + 1])
    return g


def load_font():
    """the engine's 3x5 font (engine/tools/mkfont.py)"""
    src = open(os.path.join(HERE, '..', 'engine', 'tools', 'mkfont.py')).read()
    font = {}
    exec(src[src.index('G = {'):src.index('}', src.index('G = {')) + 1], font)
    return font['G']


def style_word(rnd, P, words):
    """words spelled in ladders and brick, to climb about on: two lines of
    up to 4 letters, each letter pixel two cells across and a row down;
    vertical strokes are ladders, horizontal ones brick floor"""
    font = load_font()
    g = blank()
    keep = set()
    for line, word in enumerate(words):
        top = 2 + 6 * line
        x0 = (COLS - (len(word) * 8 - 2)) // 2
        for i, ch in enumerate(word):
            rows = font[ch].split()
            keep.update((top + yy, x0 + i * 8 + xx) for yy in range(5) for xx in range(6))

            def on(yy, xx):
                return 0 <= yy < 5 and 0 <= xx < 3 and rows[yy][xx] == '#'
            for gy in range(5):
                for gx in range(3):
                    if not on(gy, gx):
                        continue
                    x, y = x0 + i * 8 + gx * 2, top + gy
                    if on(gy - 1, gx) or on(gy + 1, gx):    # a vertical stroke
                        g[y][x] = 'H'
                        if not on(gy, gx + 1) and not on(gy, gx - 1):
                            pass
                        else:
                            g[y][x + 1] = 'B'               # (and a horizontal one)
                        if not on(gy + 1, gx):              # its foot
                            if y + 1 == 13:
                                g[13][x] = 'H'
                            elif g[y + 1][x] == '.':
                                g[y + 1][x] = 'B'
                    else:                                   # a horizontal stroke
                        g[y][x] = g[y][x + 1] = 'B'
    # ledges in the top corners, for the exit ladder near an edge
    for c0 in (0, COLS - 3):
        if all(g[y][x] == '.' for y in (1, 2) for x in range(c0, c0 + 3)):
            floor_run(g, rnd, dict(P, stone=0), 2, c0, c0 + 3)
    # ledges in the space around the text
    near = {(y + dy, x + dx) for (y, x) in keep for dy in (-1, 0, 1) for dx in (-2, -1, 0, 1, 2)}
    for _ in range(30):
        for _ in range(30):
            r, w = rnd.randint(2, 12), rnd.randint(3, 6)
            c = rnd.randint(0, COLS - w)
            span = range(max(0, c - 1), min(COLS, c + w + 1))
            if all(g[y][x] == '.' and (y, x) not in near for y in (r - 1, r, r + 1) for x in span):
                floor_run(g, rnd, P, r, c, c + w)
                break
    # ways in: ladders the full height either side of the text; the rows
    # above each line of letters are walkways along their tops
    xs = [x for (y, x) in keep]
    for x in (min(xs) - 2, max(xs) + 2):
        if 0 <= x < COLS:
            ladder(g, x, 1, 13)
    return g, keep


def bottom_floor(g, rnd, P):
    """the bottom floor: brick (holes dug there trap guards), stone mixing
    in on higher levels"""
    c = 0
    while c < COLS:
        w = rnd.randint(4, 10)
        kind = 'S' if rnd.random() < P['bottom'] else 'B'
        for x in range(c, min(COLS, c + w)):
            g[14][x] = kind
        c += w


def mirror(g):
    for r in range(ROWS):
        for x in range(COLS // 2):
            g[r][COLS - 1 - x] = g[r][x]
    return g


STYLES = {'first': lambda rnd, P: style_floors(rnd, P, even=True), 'floors': style_floors, 'ledges': style_ledges, 'rooms': style_rooms,
          'pyramid': style_pyramid, 'cavern': style_cavern}


def style_for(n):
    """the style of level n: the first ten gentle, new styles joining every
    ten levels"""
    if n % 10 == 0:
        return 'word'
    if n < 10:
        return 'first'
    choices = ['floors', 'ledges', 'rooms']
    if n > 20:
        choices += ['pyramid', 'ledges']
    if n > 30:
        choices += ['cavern', 'rooms']
    return Rng(n * 31 + 7).choice(choices)


# ---------------------------------------------------------------- a level

def place(g, rnd, P, start):
    """the exit, the geodes, the guards: (score, level) or None if poor"""
    out, both = two_way(g, start)
    stand = [p for p in stand_cells(g) if p in both and p != start]
    if len(stand) < 40:
        return None
    nodig = reach(g, start, dig=False)
    needdig = [p for p in stand if p not in nodig]
    easy = [p for p in stand if p in nodig]
    k = min(P['dig_geodes'], len(needdig))
    if len(easy) < P['geodes'] - k:
        return None
    geodes = rnd.sample(needdig, k) + rnd.sample(easy, P['geodes'] - k)
    # the exit: a column climbing from a two-way cell to the top, one cell in
    # from the far left or the far right (so the hero climbs it centered),
    # never in the middle
    # (one starting from row 9 or higher if there is one, else from lower)
    edge = [p for p in sorted(both) if standing(g, p) and p not in geodes
            and p[1] in (1, COLS - 2)]
    high = [p for p in edge if p[0] <= 9]
    low = [p for p in edge if p[0] > 9]
    rnd.shuffle(high)
    rnd.shuffle(low)
    cands = high + low
    exit_at = None
    for (r, c) in cands[:40]:
        if all(at(g, y, c) in '.B-S' for y in range(0, r)):
            opened = [row[:] for row in g]
            for y in range(0, r + 1):
                opened[y][c] = 'X'
            if (0, c) in reach(opened, start):
                exit_at = (r, c)
                break
    if not exit_at:
        return None
    far = [p for p in stand if abs(p[1] - start[1]) + 3 * abs(p[0] - start[0]) > 12
           and p not in geodes]
    rnd.shuffle(far)
    guards = []
    for p in far:
        if all(abs(p[1] - q[1]) > 2 or p[0] != q[0] for q in guards):
            guards.append(p)
        if len(guards) == P['guards']:
            break
    if len(guards) < P['guards']:
        return None
    lv = [row[:] for row in g]
    for (r, c) in geodes:
        lv[r][c] = 'T'
    for (r, c) in guards:
        lv[r][c] = 'E'
    lv[start[0]][start[1]] = 'P'
    r, c = exit_at
    for y in range(0, r + 1):
        if lv[y][c] == '.':
            lv[y][c] = 'X'
    score = len(stand) + 3 * len(needdig) + rnd.random()    # interest
    return score, lv


def candidate(n, seed):
    rnd = Rng(seed)
    P = params(n)
    style = style_for(n)
    keep = ()
    if style == 'word':
        g, keep = style_word(rnd, P, WORDS[(n // 10 - 1) % len(WORDS)])
    else:
        g = STYLES[style](rnd, P)
        if n > 20 and style not in ('cavern', 'first') and rnd.random() < 0.3:
            g = mirror(g)
            style += ', mirrored'
        add_cables(g, rnd, P)
        add_double(g, rnd, P)
    bottom_floor(g, rnd, P)
    starts = [(13, c) for c in range(COLS) if standing(g, (13, c))]
    if not starts:
        return None
    start = rnd.choice(starts)
    # (a word level may keep some letter floors out of reach: its geodes
    # still go only where the hero can get to and back from)
    if not repair(g, rnd, start, keep=keep, slack=4 if keep else 20) and not keep:
        return None
    got = place(g, rnd, P, start)
    return got and (got[0], got[1], style)


def level(n, want=4):
    """level n: (15 strings of 32 cells, its style), the best of a few
    candidates"""
    best = None
    for attempt in range(80):
        got = candidate(n, n * 7919 + attempt * 104729)
        if got and (best is None or got[0] > best[0]):
            best = got
        if best and attempt >= want:
            break
    if not best:
        raise RuntimeError('no level %d' % n)
    return [''.join(row) for row in best[1]], best[2]


def sheet(out, numbers):
    sys.path.insert(0, os.path.join(HERE, '..', 'mockups'))
    from plat_cg6 import render, image
    from PIL import Image, ImageDraw
    cols = 4
    rows = (len(numbers) + cols - 1) // cols
    cw, ch = 128 * 4, 192 * 2                 # CG6 pixels are twice as wide as tall: 4:3
    S = Image.new('RGB', (cols * (cw + 12) + 12, rows * (ch + 28) + 12), (24, 24, 24))
    d = ImageDraw.Draw(S)
    for i, n in enumerate(numbers):
        lv, style = level(n)
        status = "SCORE 000000  LEVEL %03d  LIVES 3" % n
        im = image(render(lv, status)).resize((cw, ch), Image.NEAREST)
        x, y = 12 + (i % cols) * (cw + 12), 12 + (i // cols) * (ch + 28)
        S.paste(im, (x, y))
        P = params(n)
        d.text((x, y + ch + 6), "level %d (%s): %d geodes (%d by digging), %d guards"
               % (n, style, P['geodes'], P['dig_geodes'], P['guards']), fill=(220, 220, 220))
    S.save(out)


def encode(lv):
    cells = [CODES.index(ch) for row in lv for ch in row]
    return bytes((cells[i] << 4) | cells[i + 1] for i in range(0, len(cells), 2))


def decode(rec):
    cells = ''.join(CODES[b >> 4] + CODES[b & 15] for b in rec)
    return [cells[r * COLS:(r + 1) * COLS] for r in range(ROWS)]


def _one(n):
    return encode(level(n)[0])


def write_dat(out, count):
    from multiprocessing import Pool
    with Pool() as pool:
        recs = pool.map(_one, range(1, count + 1), chunksize=16)
    head = b'GR' + bytes([1, 0]) + count.to_bytes(2, 'big') + bytes(10)
    with open(out, 'wb') as f:
        f.write(head + b''.join(recs))


def check_dat(path, numbers):
    data = open(path, 'rb').read()
    assert data[:3] == b'GR\x01', 'not a level file'
    count = int.from_bytes(data[4:6], 'big')
    bad = 0
    for n in numbers:
        if not 1 <= n <= count:
            continue
        rec = data[HEADER + RECORD * (n - 1):HEADER + RECORD * n]
        if decode(rec) != level(n)[0]:
            print('level', n, 'differs')
            bad += 1
    return bad


if __name__ == '__main__':
    if sys.argv[1] == '--dat':
        write_dat(sys.argv[2], int(sys.argv[3]))
    elif sys.argv[1] == '--check':
        sys.exit(1 if check_dat(sys.argv[2], [int(a) for a in sys.argv[3:]]) else 0)
    elif sys.argv[1] == '--sheet':
        sheet(sys.argv[2], [int(a) for a in sys.argv[3:]])
    else:
        for a in sys.argv[1:]:
            lv, style = level(int(a))
            print('level', a, style)
            print('\n'.join(lv))
