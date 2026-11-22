#!/usr/bin/env python3
"""plat.py: a still mock-up of a single-screen platformer in mono RG6
(256x192, CSS=0, no artifacting), for judging the look before any code.

Tiles and sprites are 8 x 12 pixels (one byte by 12 rows), so the screen
is a 32 x 16 grid: a status row on top, then 15 rows of level.  Writes

    build/mockup_scr.inc   the screen as fcb lines (bench/mockup.asm shows it)
    build/mockup.png       a preview, 3x, green on black

Public domain (Unlicense)."""
import os, sys
from PIL import Image

W, H = 8, 12
COLS, ROWS = 32, 16

TILES = {
    'B': [  # brick, diggable: two courses, at the top of the cell (what
        "#######.",   # stands on it touches it; the 4 rows under it are air)
        "#######.",
        "#######.",
        "........",
        "###.####",
        "###.####",
        "###.####",
        "........",
        "........",
        "........",
        "........",
        "........"],
    'S': [  # stone: solid, can't be dug (as thick as the brick)
        "########",
        "#.#.#.##",
        "##.#.#.#",
        "#.#.#.##",
        "##.#.#.#",
        "#.#.#.##",
        "########",
        "........",
        "........",
        "........",
        "........",
        "........"],
    'H': [  # ladder
        ".#....#.",
        ".######.",
        ".#....#.",
        ".#....#.",
        ".#....#.",
        ".######.",
        ".#....#.",
        ".#....#.",
        ".#....#.",
        ".######.",
        ".#....#.",
        ".#....#."],
    'T': [  # treasure: a gem
        "........",
        "........",
        "........",
        "........",
        "..####..",
        ".#.##.#.",
        "########",
        ".#.##.#.",
        "..#..#..",
        "...##...",
        "........",
        "........"],
    'P': [  # the hero, side on, striding
        "...###..",
        "..######",
        "...#.##.",
        "...####.",
        "....##..",
        "..####..",
        ".#.####.",
        "...###.#",
        "...##...",
        "..#..#..",
        ".#....#.",
        "##....##"],
    'E': [  # a baddie
        ".#....#.",
        "..####..",
        ".######.",
        "##.##.##",
        "########",
        ".#.##.#.",
        "..####..",
        ".######.",
        "#.####.#",
        "..#..#..",
        ".##..##.",
        "........"],
}

# the level: 32 x 15 (row 0 of the screen is the status bar)
LEVEL = [
    "................................",
    "..T.......E...........T.....T...",
    "BBBBBBH.BBBBBBBBBBBBBBBBH.BBBBBB",
    "......H.................H.......",
    "......H....T......E.....H..T....",
    "BBH.SSSSSSSBBBBBBBBBBH..SSSSSBBB",
    "..H..................H..........",
    "..H...T.....P........H....E....T",
    "BBBBBBBBBBBBBBH...BBBBBBBBBBH...",
    "..............H.............H...",
    "....T....E....H.......T.....H...",
    "SSSH...BBBBBBBBBBBBBBH....BBBBBB",
    "...H.................H..........",
    "...H....T.......E....H......T...",
    "SSSSSSSSSSSSSSSSSSSSSSSSSSSSSSSS",
]
STATUS = "SCORE 000000  LEVEL 01  LIVES 3"

# the engine's 3x5 font (engine/tools/mkfont.py), doubled to 6x10 in mono
FONT = {}
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'engine', 'tools', 'mkfont.py')).read()
exec(src[src.index('G = {'):src.index('}', src.index('G = {')) + 1], FONT)
FONT = FONT['G']


def glyph(ch):
    rows = FONT.get(ch, FONT[' ']).split()
    cell = ["." * W for _ in range(H)]
    for y, r in enumerate(rows):
        line = "".join(c * 2 for c in r) + ".."
        cell[1 + 2 * y] = cell[2 + 2 * y] = line
    return cell


assert len(LEVEL) == ROWS - 1 and all(len(r) == COLS for r in LEVEL), "level size"
for k, t in TILES.items():
    assert len(t) == H and all(len(r) == W for r in t), k

def main():
    px = [[0] * (COLS * W) for _ in range(ROWS * H)]


    def put(cell, cx, cy):
        for y, r in enumerate(cell):
            for x, c in enumerate(r):
                if c == '#':
                    px[cy * H + y][cx * W + x] = 1


    for i, ch in enumerate(STATUS.ljust(COLS)):
        put(glyph(ch), i, 0)
    for y, r in enumerate(LEVEL):
        for x, ch in enumerate(r):
            if ch in TILES:
                put(TILES[ch], x, y + 1)

    os.makedirs('build', exist_ok=True)
    with open('build/mockup_scr.inc', 'w') as f:
        f.write("; the mock-up's screen (mockups/plat.py), 32 bytes x 192 rows\n")
        for row in px:
            b = [int("".join(map(str, row[i:i + 8])), 2) for i in range(0, 256, 8)]
            for j in range(0, 32, 16):
                f.write("                fcb     " + ",".join(f"${v:02X}" for v in b[j:j + 16]) + "\n")
    img = Image.new('RGB', (256, 192))
    img.putdata([(64, 255, 64) if v else (0, 0, 0) for row in px for v in row])
    img.resize((768, 576), Image.NEAREST).save('build/mockup.png')


if __name__ == '__main__':
    main()
