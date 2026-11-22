#!/usr/bin/env python3
"""plat_cg6.py: the platformer mock-up (mockups/plat.py's level) in CG6,
128x192 in four real colors (CSS=0: green, yellow, blue, red), which PAL
machines show as well as NTSC ones.  CG6 has no black, so the background
is a choice: blue (the engine's erase would write blue) or green (pixel
value 0, what the engine erases to now).

The grid stays 32 x 16, so a tile is 4 color pixels wide (each as wide as
two mono pixels) by 12 rows; the hero and thieves are 6 pixels wide,
centered on their cell.

    python3 mockups/plat_cg6.py blue|green
        -> build/mockup_NAME.inc (bench/mockup.asm) and build/mockup_NAME.png

Public domain (Unlicense)."""
import os, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plat import LEVEL, STATUS, FONT

W, H, COLS, ROWS = 4, 12, 32, 16
GREEN, YELLOW, BLUE, RED = 0, 1, 2, 3
RGB = {GREEN: (40, 224, 40), YELLOW: (240, 240, 80), BLUE: (40, 40, 220), RED: (220, 40, 40)}

# roles -> colors, per scheme ('.' is the background)
SCHEMES = {
    'blue':  {'.': BLUE, 'B': RED, 'S': GREEN, 's': BLUE, 'L': YELLOW, 'G': YELLOW, 'g': GREEN,
              'H': YELLOW, 'h': GREEN, 'E': RED, 'e': YELLOW, 'T': YELLOW},
    'green': {'.': GREEN, 'B': RED, 'S': BLUE, 's': GREEN, 'L': YELLOW, 'G': YELLOW, 'g': RED,
              'H': YELLOW, 'h': BLUE, 'E': RED, 'e': YELLOW, 'T': BLUE},
}

TILES = {
    'B': ["BBB.", "BBB.", "BBB.", "....", "B.BB", "B.BB", "B.BB", "....",
          "....", "....", "....", "...."],
    'S': ["SSSS", "SsSs", "sSsS", "SsSs", "sSsS", "SsSs", "SSSS", "....",
          "....", "....", "....", "...."],
    'H': ["L..L", "LLLL", "L..L", "L..L", "L..L", "LLLL", "L..L", "L..L",
          "L..L", "LLLL", "L..L", "L..L"],
    'T': ["....", "....", "....", "....", ".GG.", "GgGG", "GGGG", ".Gg.",
          "..G.", "....", "....", "...."],
}
SPRITES = {
    'P': ["..hh..", ".hhhh.", ".HHHH.", ".H.HH.", "..HH..", "hhhhhh",
          "H.hh.H", "..hh..", ".h..h.", ".h..h.", "hh..hh", "......"],
    'E': ["E....E", ".EEEE.", "EEEEEE", "EeEEeE", "EEEEEE", ".EEEE.",
          "EEEEEE", "E.EE.E", "..EE..", ".E..E.", "EE..EE", "......"],
}


def main(name):
    col = SCHEMES[name]
    px = [[col['.']] * (COLS * W) for _ in range(ROWS * H)]

    def put(art, x0, y0):
        for y, r in enumerate(art):
            for x, c in enumerate(r):
                if c != '.' and 0 <= x0 + x < COLS * W:
                    px[y0 + y][x0 + x] = col[c]

    for i, ch in enumerate(STATUS.ljust(COLS)):     # the 3x5 font, rows doubled
        for y, r in enumerate(FONT.get(ch, FONT[' ']).split()):
            for x, c in enumerate(r):
                if c == '#':
                    px[1 + 2 * y][i * W + x] = px[2 + 2 * y][i * W + x] = col['T']
    for y, r in enumerate(LEVEL):
        for x, ch in enumerate(r):
            if ch in TILES:
                put(TILES[ch], x * W, (y + 1) * H)
            elif ch in SPRITES:
                put(SPRITES[ch], x * W - 1, (y + 1) * H)

    with open(f'build/mockup_{name}.inc', 'w') as f:
        f.write(f"; the CG6 mock-up on {name} (mockups/plat_cg6.py), 32 bytes x 192 rows\n")
        for row in px:
            b = [(row[i] << 6) | (row[i + 1] << 4) | (row[i + 2] << 2) | row[i + 3] for i in range(0, 128, 4)]
            for j in range(0, 32, 16):
                f.write("                fcb     " + ",".join(f"${v:02X}" for v in b[j:j + 16]) + "\n")
    img = Image.new('RGB', (128, 192))
    img.putdata([RGB[v] for row in px for v in row])
    img.resize((768, 576), Image.NEAREST).save(f'build/mockup_{name}.png')


if __name__ == '__main__':
    os.makedirs('build', exist_ok=True)
    main(sys.argv[1])
