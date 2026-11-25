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
so they can be collected in any order (those in vaults by digging in and
out, checked the same way); the exit ladder climbs to the top
from such a place, one column in from either edge.  Several
candidates are made and the most interesting kept.

    python3 tools/levelgen.py N [N2 ...]     print levels
    python3 tools/levelgen.py --sheet OUT.png N1 N2 ...   a contact sheet
    python3 tools/levelgen.py --dat OUT COUNT     levels 1..COUNT as a level file (the game: 150)
    python3 tools/levelgen.py --check FILE N...   compare a level file with the generator
    python3 tools/levelgen.py --verify FILE       every level in a level file playable

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
WORDS = [('DIG', 'DEEP'), ('MC10', '1983'), ('XTAL', 'RUN'), ('ROCK', 'ON'),
         ('CAVE', 'IN'), ('HI', 'MOM'), ('LOOT', 'DIG'), ('GO', 'WEST'),
         ('OH', 'NO'), ('GEO', 'DES'), ('BLRP', '!'), ('HALF', 'WAY?'),
         ('DONT', 'STOP'), ('THE', 'END?'), ('LAST', 'ONE!')]    # levels 10, 20 ... 150
HERE = os.path.dirname(os.path.abspath(__file__))
CODES = '.BSH-TPEX'                 # a cell's code in the level file: its index
HEADER, RECORD = 16, 240


def vaults(n, t):
    """how many vaults level n has: now and then, never knowing when (about
    a level in three, more later; two at once now and then after 60)"""
    if n < 4:
        return 0
    r = Rng(n * 101 + 3).random()
    p = 0.3 + 0.2 * t
    return 0 if r >= p else 2 if n > 60 and r < p * 0.25 else 1


def doubles(n, t):
    """how many of level n's vaults need a double dig (from level 15, about
    half of them, more later)"""
    if n < 15:
        return 0
    return sum(Rng(n * 103 + 7 * i + 1).random() < 0.5 + 0.3 * t for i in range(vaults(n, t)))


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
        dig_geodes=vaults(n, t),                         # geodes in vaults (dug into)
        doubles=doubles(n, t),                           # ... of them needing a double dig
        guards=1 if n < 3 else 2 if n < 21 else 3 if n < 41 else 4,  # (4 at most: the MC-10 keeps up)
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


def moves(g, r, c, dig=True, double=True):
    """the cells the hero can get to from (r, c) in one move (digging: down
    through one brick, and with double, two)"""
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
                    out.append((r + 2, c + dc))
                # two bricks deep: dig two side by side, drop into the near
                # one, dig the brick under the far one, drop through it
                far = c + 2 * dc
                if (double and side not in SOLID + 'HX-' and at(g, r, far) not in SOLID + 'HX-'
                        and under == 'B' and at(g, r + 1, far) == 'B'
                        and at(g, r + 2, far) == 'B' and at(g, r + 3, far) not in SOLID
                        and at(g, r + 2, c + dc) in SOLID):
                    out.append((r + 3, far))
    return [q for q in out if 0 <= q[0] < ROWS and at(g, *q) not in SOLID]


def graph(g, dig=True, double=True):
    """every open cell's moves, and the reverse"""
    fwd, back = {}, {}
    for r in range(ROWS):
        for c in range(COLS):
            if g[r][c] in SOLID:
                continue
            fwd[(r, c)] = moves(g, r, c, dig, double)
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


def reach(g, start, dig=True, double=True):
    return bfs(graph(g, dig, double)[0], start)


def two_way(g, start, dig=False):
    """(cells the hero can reach from start, cells he can also get back from)
    (the layout is made walkable without digging; only vaults need it)"""
    fwd, back = graph(g, dig)
    out = bfs(fwd, start)
    return out, out & bfs(back, start)


def standing(g, p):
    r, c = p
    return at(g, r, c) not in SOLID + 'HX-' and at(g, r + 1, c) in SOLID


def stand_cells(g, tops=False):
    """the cells to stand in (on floor; with tops, on a ladder's top too)"""
    return [(r, c) for r in range(ROWS - 1) for c in range(COLS) if standing(g, (r, c))
            or (tops and at(g, r, c) == '.' and at(g, r + 1, c) == 'H')]


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


def repair(g, rnd, start, tries=40, keep=(), slack=20, skip=()):
    """add ladders until nearly every standing cell (all but 1/slack; not
    counting those in skip, the vaults) is two-way reachable from start;
    False if it can't"""
    for _ in range(tries):
        out, both = two_way(g, start)
        stands = [p for p in stand_cells(g) if p not in skip]
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
    """words spelled in ladders, big and plain, to climb about on: two
    lines of up to 4 letters, each letter pixel two ladder cells across and
    a row down; the first line stands on a brick floor, the second on the
    bottom one"""
    font = load_font()
    g = blank()
    keep = set()
    for line, word in enumerate(words):
        top = 2 + 7 * line              # rows 2-6 on a floor at 7; 9-13 on the bottom
        step = 8 if len(word) < 4 else 7    # (4 letters: closer, leaving the exit columns)
        x0 = (COLS - (len(word) * step - step + 6)) // 2
        for i, ch in enumerate(word):
            rows = font[ch].split()
            keep.update((top + yy, x0 + i * step + xx) for yy in range(5) for xx in range(6))

            def on(yy, xx):
                return 0 <= yy < 5 and 0 <= xx < 3 and rows[yy][xx] == '#'
            for gy in range(5):
                for gx in range(3):
                    if on(gy, gx):                          # every stroke a ladder
                        x, y = x0 + i * step + gx * 2, top + gy
                        g[y][x] = g[y][x + 1] = 'H'
    # the first line stands on a floor (brick: holes to dig, gaps to drop)
    for x in range(COLS):
        g[7][x] = 'B' if rnd.random() > 0.12 else '.'
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


STONE_RUN = 5       # at most this many stone cells in a row under a walkway


def break_stone(g):
    """no long stone floors: under a walkway, a stretch of more than
    STONE_RUN stone cells gets two bricks after every STONE_RUN (owner:
    long stone floors with the guards coming down a ladder onto them left
    nowhere to trap them: level 102)"""
    for r in range(1, ROWS):
        x = 0
        while x < COLS:
            if g[r][x] == 'S' and g[r - 1][x] not in SOLID:
                x0 = x
                while x < COLS and g[r][x] == 'S' and g[r - 1][x] not in SOLID:
                    x += 1
                if x - x0 > STONE_RUN:
                    for k in range(x0 + STONE_RUN, x, STONE_RUN + 2):
                        g[r][k] = 'B'
                        if k + 1 < x:
                            g[r][k + 1] = 'B'
            else:
                x += 1


STONE_MAX = 0.25    # at most this share of the floor walked on is stone


def soften(g):
    """at the end, stone eased into brick (so nothing else about the level
    changes: both are solid to walk on): stone walls (stone on stone)
    become brick, and while more than STONE_MAX of the floor walked on is
    stone, its longest stretch becomes brick (owner: level 103's solid
    blocks and stone floors left too little to dig, four guards about)"""
    walls = [(r, x) for r in range(ROWS) for x in range(COLS) if g[r][x] == 'S'
             and (at(g, r - 1, x) == 'S' or (r + 1 < ROWS and g[r + 1][x] == 'S'))]
    for r, x in walls:
        g[r][x] = 'B'
    while True:
        floor = [(r, x) for r in range(1, ROWS) for x in range(COLS)
                 if g[r][x] in SOLID and g[r - 1][x] not in SOLID]
        stone = [p for p in floor if g[p[0]][p[1]] == 'S']
        if not floor or len(stone) <= STONE_MAX * len(floor):
            return
        runs = []                           # stone stretches under walkways
        for r in range(1, ROWS):
            x = 0
            while x < COLS:
                if g[r][x] == 'S' and g[r - 1][x] not in SOLID:
                    x0 = x
                    while x < COLS and g[r][x] == 'S' and g[r - 1][x] not in SOLID:
                        x += 1
                    runs.append((x - x0, r, x0))
                else:
                    x += 1
        n, r, x0 = max(runs)                # (the longest; ties: the lowest, rightmost)
        for x in range(x0, x0 + n):
            g[r][x] = 'B'


def add_vaults(g, rnd, P):
    """vaults: sealed brick boxes under a floor, a geode inside, dug into from
    above (through one brick, or for a double, two: dig two holes side by
    side, drop into one, dig under the other) and dug out of through the
    brick floor, dropping to the open space below.  Each roof lies in a
    long run of brick, room to trap the guards before breaking in.
    [(the geode's cell, the entrance cell, double?)]"""
    vaults, used = [], set()
    want = P['dig_geodes']
    if not want:
        return vaults
    w = 3                                   # the room's width
    for i in range(want):
        double = i < P['doubles']
        fits = []
        for R in range(2, 11):              # the roof row (a floor)
            for a in range(4, COLS - w - 3):
                # (ladders where it goes are cut: the repair afterwards
                # adds others, around it)
                # (ladders and stone where it goes give way: the repair
                # afterwards adds ladders around it; a double may use a
                # floor already two deep)
                lo = R + 2 if double else R + 1     # the room's rows: lo .. F-1
                F = lo                      # the room's floor: the next floor down
                while F < ROWS - 2 and g[F][a] in '.H-':
                    F += 1
                box = {(y, x) for y in range(R - 1, F + 2) for x in range(a - 4, a + w + 4)}
                if (1 <= F - lo <= 2 and F + 1 < ROWS - 1 and not box & used
                        and all(g[R][x] in 'BHS' and g[R - 1][x] in '.H' for x in range(a - 2, a + w + 2))
                        and all(g[R + 1][x] in ('.H-B' if double else '.H-') for x in range(a - 1, a + w + 1))
                        and all(g[y][x] in '.H-' for y in range(lo, F) for x in range(a - 1, a + w + 1))
                        and all(g[F][x] in 'BHS' and g[F + 1][x] == '.' for x in range(a, a + w))):
                    fits.append((R, a, F, box))
        if not fits:
            break
        R, a, F, box = rnd.choice(fits)
        for x in range(a - 2, a + w + 2):
            g[R][x] = 'B'
            for y in range(R + 1, F):
                if a - 1 <= x <= a + w:
                    g[y][x] = '.'
        for x in range(a, a + w):
            g[F][x] = 'B'
        for y in range(R + 1, F):           # brick all round: a box
            g[y][a - 1] = g[y][a + w] = 'B'
        if double:
            for x in range(a, a + w):
                g[R + 1][x] = 'B'
        used |= box
        vaults.append(((F - 1, a + rnd.randint(0, w - 1)), (R - 1, a + 1), double,
                       {(y, x) for y in range(R, F + 1) for x in range(a - 1, a + w + 1)}))
    return vaults


def vault_ok(g, start, v, both, nodig, single):
    """a vault's geode: reached and left only by digging (a double's only
    by a double dig)"""
    cell, entry, double, cells = v
    return cell in both and cell not in nodig and (not double or cell not in single)


def mirror(g):
    for r in range(ROWS):
        for x in range(COLS // 2):
            g[r][COLS - 1 - x] = g[r][x]
    return g


STYLES = {'first': lambda rnd, P: style_floors(rnd, P, even=True), 'floors': style_floors, 'ledges': style_ledges, 'rooms': style_rooms,
          'pyramid': style_pyramid, 'cavern': style_cavern}


# levels given another style, the owner having found the first unfair
STYLE_SET = {102: 'floors'}     # (102: a cavern, all dead ends, nowhere to trap four guards)


def style_for(n):
    """the style of level n: the first ten gentle, then plain floors, new
    styles joining every ten levels from 21 (the owner found ledges with
    three guards at 13 far too hard, far too soon)"""
    if n in STYLE_SET:
        return STYLE_SET[n]
    if n % 10 == 0:
        return 'word'
    if n < 10:
        return 'first'
    choices = ['floors']
    if n > 20:
        choices += ['rooms', 'floors']
    if n > 30:
        choices += ['ledges']
    if n > 40:
        choices += ['pyramid', 'ledges', 'rooms']
    if n > 50:
        choices += ['cavern']
    return Rng(n * 31 + 7).choice(choices)


# ---------------------------------------------------------------- a level

def gap(a, b):
    """how far apart two cells are, for spreading geodes (a floor apart
    counts as three cells across)"""
    return abs(a[1] - b[1]) + 3 * abs(a[0] - b[0])


def spread(rnd, pool, k, placed, start):
    """placed + k cells from pool, each as far as it can be from the ones
    before it and the start: picked at random among the farthest few"""
    out = list(placed)
    pool = [p for p in pool if p not in out]
    for _ in range(k):
        if not pool:
            break
        far = [(min(gap(p, q) for q in out + [start]), p) for p in pool]
        best = max(d for d, p in far)
        top = [p for d, p in far if d >= best - 2]
        p = rnd.choice(top)
        out.append(p)
        pool.remove(p)
    return out


def guard_times(g, fwd, back, p):
    """for every cell: the frames between it and p for a guard, the shorter
    way (to p or from it): walking 14, climbing 16, falling 14 a cell"""
    from heapq import heappush, heappop
    best = {}
    for edges in (fwd, back):
        dist, pq = {p: 0}, [(0, p)]
        while pq:
            t, (r, c) = heappop(pq)
            if t > dist[(r, c)]:
                continue
            for q in edges.get((r, c), ()):
                nt = t + (14 if q[0] == r else 16 if at(g, r, c) in 'HX' or at(g, q[0], q[1]) in 'HX' else 14)
                if nt < dist.get(q, 1 << 30):
                    dist[q] = nt
                    heappush(pq, (nt, q))
        for q, t in dist.items():
            best[q] = min(best.get(q, 1 << 30), t)
    return best


def place(g, rnd, P, start, room=40, vaults=()):
    """the exit, the geodes, the guards: (score, level, (vaults, doubles))
    or None if poor (fewer than `room` places to stand)"""
    out, both = two_way(g, start)
    stand = [p for p in stand_cells(g, tops=room < 40) if p in both and p != start]
    if len(stand) < room:
        return None
    nodig = reach(g, start, dig=False)
    if vaults:
        dug = two_way(g, start, dig=True)[1]
        single = reach(g, start, double=False) if any(v[2] for v in vaults) else set()
        vaults = [v for v in vaults if vault_ok(g, start, v, dug, nodig, single)]
    inside = set().union(*(v[3] for v in vaults)) if vaults else set()
    needdig = [p for p in stand if p not in nodig and p not in inside]
    easy = [p for p in stand if p in nodig]
    k = min(max(0, P['dig_geodes'] - len(vaults)), len(needdig))
    if len(easy) < P['geodes'] - k - len(vaults):
        return None
    # a geode in each vault; the rest spread out: the ones that need digging
    # first, then the others, each far from those placed (and from the
    # hero's start)
    geodes = [v[0] for v in vaults]
    geodes = spread(rnd, needdig, k, geodes, start)
    geodes = spread(rnd, easy, P['geodes'] - len(geodes), geodes, start)
    # the exit: a column climbing from a two-way cell to the top, one cell in
    # from the far left or the far right (so the hero climbs it centered),
    # never in the middle
    # (one starting from row 9 or higher if there is one, else from lower)
    edge = [p for p in sorted(both) if standing(g, p) and p not in geodes
            and p != start and p[1] in (1, COLS - 2)]
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
            if (0, c) in reach(opened, start, dig=False):
                exit_at = (r, c)
                break
    if not exit_at:
        return None
    # guards: far from the hero, never in a dug-into place, and well away
    # from a vault's entrance (time to trap them before breaking in)
    far = [p for p in easy if abs(p[1] - start[1]) + 3 * abs(p[0] - start[0]) > 12
           and p not in geodes and all(gap(p, v[1]) > 14 for v in vaults)
           and not (p[1] == exit_at[1] and p[0] <= exit_at[0])]    # (not on the exit)
    rnd.shuffle(far)
    guards = []
    if P['guards'] >= 4:
        # four: spread to the far ends of the level, never together, so
        # they can't meet up and come down on him at once (owner: level
        # 102).  Far by the way a guard goes (walking, climbing, falling at
        # guard speed, either way between the two): each as far as can be
        # from the nearest of the hero and the ones placed (ties: the
        # shuffled order)
        fwd, back = graph(g, dig=False)
        near = guard_times(g, fwd, back, start)
        for _ in range(P['guards']):
            if not far:
                break
            p = max(far, key=lambda p: near.get(p, 99999))
            guards.append(p)
            t = guard_times(g, fwd, back, p)
            near = {q: min(near.get(q, 99999), t.get(q, 99999)) for q in set(near) | set(t)}
            far = [q for q in far if q != p]
    else:
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
    score = len(stand) + 3 * len(needdig) + 60 * len(vaults) + rnd.random()    # interest
    return score, lv, (len(vaults), sum(1 for v in vaults if v[2]))


def candidate(n, seed):
    rnd = Rng(seed)
    P = params(n)
    style = style_for(n)
    keep = ()
    if style == 'word':
        g, keep = style_word(rnd, P, WORDS[(n // 10 - 1) % len(WORDS)])
    else:
        g = STYLES[style](rnd, P)
        if n > 40 and style not in ('cavern', 'first') and rnd.random() < 0.3:
            g = mirror(g)
            style += ', mirrored'
        add_cables(g, rnd, P)
        add_double(g, rnd, P)
    # (a word level's bottom floor is all brick: somewhere to trap guards
    # among the letters' ladders)
    bottom_floor(g, rnd, dict(P, bottom=0) if style == 'word' else P)
    break_stone(g)
    vaults = add_vaults(g, rnd, P) if style != 'word' else []
    if vaults:                      # (no ladders through them)
        keep = set().union(*(v[3] for v in vaults))
    starts = [(13, c) for c in range(COLS) if standing(g, (13, c))]
    if not starts:
        return None
    start = rnd.choice(starts)
    # brick under the hero's start and four cells either side, even on the
    # stone bottoms of the higher levels: somewhere to trap the first guards
    # (owner: level 101 started him in a stone corridor, the only ladders
    # far off and the guards coming down them: no way to survive)
    for x in range(max(0, start[1] - 4), min(COLS, start[1] + 5)):
        if g[14][x] == 'S':
            g[14][x] = 'B'
    # (a word level may keep some letter floors out of reach: its geodes
    # still go only where the hero can get to and back from)
    # (no ladder through the start cell: the hero's mark would cut it)
    if not repair(g, rnd, start, keep=set(keep) | {start}, slack=4 if style == 'word' else 20,
                  skip=keep if vaults else ()) and style != 'word':
        return None
    break_stone(g)                  # (again: the repair's ladders change the walkways)
    soften(g)
    got = place(g, rnd, P, start, room=20 if style == 'word' else 40, vaults=vaults)
    if not got:
        return None
    if fairness(got[1] if isinstance(got[1][0], str) else [''.join(row) for row in got[1]]):
        return None
    nv, nd = got[2]
    if nv:
        style += ', %d vault%s' % (nv, 's' if nv > 1 else '') + (' (%d double)' % nd if nd else '')
    return got[0], got[1], style, nv


# levels made again from other random numbers, the owner having found the
# first ones unfair (level: a number mixed into its seeds)
REROLL = {47: 1,       # (47: four guards camped the one way to the exit: the solver found no way)
          48: 1,       # (48: three guards closed on the start at once: no way)
          100: 3,      # (100: the first had a guard parked in a dead-end corner)
          104: 1,      # (104: the solver found no way)
          105: 1,      # (105, 121: none a player could do: with a
          121: 2}      # player's reactions the solver found no way)


# levels touched up by hand after they're made: (row, col, cell) changes
# (tools/trapfit.py moves a guard prison off the patrol path)
EDITS = {}


# the order the layouts are played in: slot: the number of the layout
# put there (each layout is made, rerolled and touched up by its own
# number).  Levels 41-148 sorted by how hard they press the hero
# (tools/pressure.py), gentlest first: by chance they had no curve at all
# (51, a late-game puzzle, came mid-game).  Word levels (on the tens), 53,
# 149 and 150 (beaten by the owner) and 1-40 (played and tuned) as made.
ORDER = {41: 61, 42: 77, 43: 92, 44: 131, 45: 94, 46: 108, 47: 104, 48: 128,
         49: 146, 51: 79, 52: 93, 54: 86, 55: 52, 56: 126, 57: 148, 58: 76,
         59: 41, 61: 87, 62: 54, 63: 121, 64: 129, 65: 69, 66: 122, 67: 143,
         68: 127, 69: 88, 71: 133, 72: 106, 73: 96, 74: 99, 75: 118, 76: 124,
         77: 98, 78: 132, 79: 42, 81: 137, 82: 125, 83: 135, 84: 49, 85: 63,
         86: 82, 87: 115, 88: 119, 89: 83, 91: 73, 92: 144, 93: 59, 94: 66,
         95: 113, 96: 84, 97: 123, 98: 134, 99: 147, 101: 105, 102: 45,
         103: 91, 104: 139, 105: 85, 106: 78, 107: 142, 108: 109, 109: 112,
         111: 56, 112: 47, 113: 68, 114: 101, 115: 102, 116: 103, 117: 145,
         118: 89, 119: 65, 121: 107, 122: 111, 123: 114, 124: 71, 125: 136,
         126: 57, 127: 55, 128: 141, 129: 44, 131: 67, 132: 62, 133: 48,
         134: 138, 135: 46, 136: 97, 137: 64, 138: 74, 139: 81, 141: 72,
         142: 75, 143: 117, 144: 43, 145: 95, 146: 58, 147: 51, 148: 116}


def level(n):
    """the level in slot n: (15 strings of 32 cells, its style)"""
    return make(ORDER.get(n, n))


def make(n, want=4):
    """the layout numbered n: (15 strings of 32 cells, its style), the
    best of a few candidates"""
    best = None
    vaults = params(n)['dig_geodes'] if style_for(n) != 'word' else 0
    for attempt in range(80):
        got = candidate(n, n * 7919 + attempt * 104729 + REROLL.get(n, 0) * 15485863)
        if got and (best is None or got[0] > best[0]):
            best = got
        # (a few candidates, more until one has all the vaults wanted)
        if best and attempt >= want and (best[3] >= vaults or attempt >= 30):
            break
    if not best:
        raise RuntimeError('no level %d' % n)
    rows = [list(row) for row in best[1]]
    for r, c, ch in EDITS.get(n, ()):
        rows[r][c] = ch
    return [''.join(row) for row in rows], best[2] + (', touched up' if n in EDITS else '')


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
        d.text((x, y + ch + 6), "level %d (%s): %d geodes, %d guards"
               % (n, style, P['geodes'], P['guards']), fill=(220, 220, 220))
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


# ---------------------------------------------------------------- fairness

# The owner can't play all 150 levels to prove each fair, so the
# generator avoids layouts like the ones he found impossible: no stone
# floor walked on runs more than STONE_RUN cells (break_stone); and a level
# whose start, or a geode, lies down a long stretch of floor that can't be
# dug (stone, or ladders over it: nowhere to trap a guard following him)
# before any way off that floor is rejected.
FAIR_START = 6      # the start: at most this much undiggable floor on the way to a ladder up
FAIR_GEODE = 9      # a geode: ... on the way to any way off its floor (up, down, a drop)


def _run_out(g, p, ways):
    """from p along its row, each way, to the nearest cell where ways(r, x)
    is true: the longest stretch of floor that can't be dug, walked over to
    get there; the better way's (99: no way out either way)"""
    r, c = p
    best = 99
    for d in (-1, 1):
        x, run, worst = c, 0, 0
        while 0 <= x < COLS and at(g, r, x) not in SOLID:
            if ways(r, x):
                best = min(best, worst)
                break
            run = run + 1 if at(g, r + 1, x) != 'B' else 0
            worst = max(worst, run)
            x += d
    return best


def fairness(lv):
    """level lv as the game loads it: [] if fair, else what isn't"""
    g = [list(r.replace('T', '.').replace('E', '.').replace('P', '.').replace('X', '.')) for r in lv]
    cells = [(r, c) for r in range(ROWS) for c in range(COLS)]
    start = [p for p in cells if lv[p[0]][p[1]] == 'P'][0]

    def up(r, x):
        return at(g, r, x) == 'H' and at(g, r - 1, x) not in SOLID

    def off(r, x):
        return up(r, x) or at(g, r + 1, x) == 'H' or at(g, r + 1, x) not in SOLID

    wrong = []
    if _run_out(g, start, up) > FAIR_START:
        wrong.append('start cornered')
    for r in range(1, ROWS):                # no long stone floor walked on
        run = 0
        for x in range(COLS):
            run = run + 1 if g[r][x] == 'S' and g[r - 1][x] not in SOLID else 0
            if run > STONE_RUN:
                wrong.append('stone floor at %d,%d' % (r, x))
                break
    floor = [(r, x) for r in range(1, ROWS) for x in range(COLS)
             if g[r][x] in SOLID and g[r - 1][x] not in SOLID]
    if floor and sum(1 for r, x in floor if g[r][x] == 'S') > STONE_MAX * len(floor):
        wrong.append('too much stone floor')
    if any(g[r][x] == 'S' and g[r + 1][x] == 'S' for r in range(ROWS - 1) for x in range(COLS)):
        wrong.append('a stone wall')
    walk = reach(g, start, dig=False)
    for p in cells:
        if lv[p[0]][p[1]] == 'T' and p in walk and _run_out(g, p, off) > FAIR_GEODE:
            wrong.append('geode %d,%d cornered' % p)       # (not a vault's: those aren't walked to)
    return wrong


def playable(lv):
    """level lv as the game loads it (geodes, guards, start: air; the exit
    hidden): [] if every geode can be reached and left and the exit, once
    grown, climbed; else what's wrong"""
    g = [list(r.replace('T', '.').replace('E', '.').replace('P', '.').replace('X', '.')) for r in lv]
    cells = [(r, c) for r in range(ROWS) for c in range(COLS)]
    start = [p for p in cells if lv[p[0]][p[1]] == 'P'][0]
    both = two_way(g, start, dig=True)[1]
    wrong = ['geode %d,%d' % p for p in cells if lv[p[0]][p[1]] == 'T' and p not in both]
    xs = [p for p in cells if lv[p[0]][p[1]] == 'X']
    if not xs:
        return wrong + ['no exit']
    c = xs[0][1]
    for y in range(max(r for (r, x) in xs if x == c) + 1):  # (it grows through anything)
        g[y][c] = 'X'
    if (0, c) not in reach(g, start):
        wrong.append('exit')
    return wrong + fairness(lv)


def verify_dat(path):
    """every level in a level file playable as the game loads it: the count
    of those that aren't"""
    data = open(path, 'rb').read()
    count = int.from_bytes(data[4:6], 'big')
    bad = 0
    for n in range(1, count + 1):
        wrong = playable(decode(data[HEADER + RECORD * (n - 1):HEADER + RECORD * n]))
        if wrong:
            print('level', n, 'not playable:', ', '.join(wrong))
            bad += 1
    return bad


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
    elif sys.argv[1] == '--verify':
        sys.exit(1 if verify_dat(sys.argv[2]) else 0)
    elif sys.argv[1] == '--sheet':
        sheet(sys.argv[2], [int(a) for a in sys.argv[3:]])
    else:
        for a in sys.argv[1:]:
            lv, style = level(int(a))
            print('level', a, style)
            print('\n'.join(lv))
