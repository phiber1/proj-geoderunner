#!/usr/bin/env python3
"""expect.py: checks of Geode Runner's state, for tests/check.sh.

    python3 tests/expect.py integrity DUMP MAP TMAP HERO GUARDS NGUARD GDSIZE

DUMP is the headless emulator's output with "mem" lines covering the level
map (MAP, 480 bytes), the tile map (TMAP, 480), the screen ($4000, 6144),
the hero's actor record (HERO, 8), the guards' records (GUARDS, NGUARD of
GDSIZE bytes) and the guard count (NGUARD's address).  It prints

    tmap_bad=N screen_bad=M

N: cells whose noted tile isn't the one their code (and brick neighbours)
call for; M: screen bytes of the level, outside the actors' boxes, that
aren't the tile art.  Both must be 0.  Public domain (Unlicense)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
from mktiles import tile_bytes      # noqa: E402

COLS, ROWS = 32, 15
# cell codes (geode.asm) -> tiles (mktiles TILE_ORDER), brick worked out apart
AIR, BRICK, STONE, LADDER, CABLE, GEODE, HERO, GUARD, EXIT, DIG1, DIG2, FILL1, FILL2 = range(13)
T_AIR, T_BRICK, T_BRICK_TOP, T_BRICK_LOW, T_STONE, T_LADDER, T_CABLE, T_GEODE, T_DIG1, T_DIG2 = range(10)
CODE_TILE = {AIR: T_AIR, STONE: T_STONE, LADDER: T_LADDER, CABLE: T_CABLE, GEODE: T_GEODE,
             HERO: T_AIR, GUARD: T_AIR, EXIT: T_AIR, DIG1: T_DIG1, DIG2: T_DIG2,
             FILL1: T_DIG1, FILL2: T_DIG2}


def memory(dump):
    mem = {}
    for line in open(dump):
        if line.startswith('mem '):
            addr, data = line[4:].split(':', 1)
            a = int(addr, 16)
            for i, b in enumerate(data.split()):
                mem[a + i] = int(b, 16)
    return mem


def tile_of(m, r, c):
    code = m[r * COLS + c]
    if code != BRICK:
        return CODE_TILE.get(code, -1)
    if r == ROWS - 1:
        return T_BRICK_TOP
    if m[(r + 1) * COLS + c] == BRICK:
        return T_BRICK_TOP
    if r > 0 and m[(r - 1) * COLS + c] == BRICK:
        return T_BRICK_LOW
    return T_BRICK


def sprite_x(x):
    return x if x == 0 else min(x - 1, 128 - 6)


def integrity(dump, amap, atmap, ahero, aguards, angu, gdsize):
    mem = memory(dump)
    m = [mem[amap + i] for i in range(COLS * ROWS)]
    tm = [mem[atmap + i] for i in range(COLS * ROWS)]
    tmap_bad = sum(1 for i in range(COLS * ROWS) if tm[i] != tile_of(m, i // COLS, i % COLS))
    # the actors' boxes (as drawn: A_OX, A_OY), a byte either side
    boxes = []
    recs = [ahero] + [aguards + k * gdsize for k in range(mem[angu])]
    for a in recs:
        x, y = mem[a + 2], mem[a + 3]
        sx = sprite_x(x)
        boxes.append((sx // 4 - 1, (sx + 5) // 4 + 1, y - 1, y + 12))
    tiles = tile_bytes()
    screen_bad = 0
    for r in range(ROWS):
        for c in range(COLS):
            t = tm[r * COLS + c]
            for k in range(12):
                y = (r + 1) * 12 + k
                if any(b0 <= c <= b1 and y0 <= y <= y1 for b0, b1, y0, y1 in boxes):
                    continue
                if mem[0x4000 + y * 32 + c] != tiles[t][k]:
                    screen_bad += 1
    print('tmap_bad=%d screen_bad=%d' % (tmap_bad, screen_bad))


if __name__ == '__main__':
    if sys.argv[1] == 'integrity':
        a = [int(v, 16) for v in sys.argv[3:8]]
        integrity(sys.argv[2], *a, int(sys.argv[8]))
