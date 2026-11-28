#!/usr/bin/env python3
"""shots.py: the one-pager's pictures (docs/img/*.png), taken from the
game itself in the VMC10 headless emulator (a test build: it can jump to
a level, and replay a solution to reach the ending).

    python3 tools/shots.py

Public domain (Unlicense)."""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, HERE)
import profile as prof          # noqa: E402
import sim                      # noqa: E402
from PIL import Image           # noqa: E402

IMG = os.path.join(ROOT, 'docs', 'img')
TMP = os.path.join(ROOT, 'build', 'shots')
GAME = (32, 24, 288, 216)       # (the 256x192 picture in the 320x240 frame)


def emulate(steps, name):
    sd = os.path.join(TMP, 'sd-' + name)
    os.makedirs(sd, exist_ok=True)
    for a, b in (('geode.bin', 'GEODE.BIN'), ('LEVELS.DAT', 'LEVELS.DAT')):
        shutil.copy(os.path.join(ROOT, 'build', a), os.path.join(sd, b))
    args = [os.path.join(prof.VMC10, 'build', 'headless'), os.path.join(prof.VMC10, 'roms', 'MC10.BIN'),
            'mcx32sd:' + os.path.join(prof.VMC10, 'roms', 'mcx32sd_flash.bin'), '8k', 'sd:' + sd,
            'frames:200', 'type:RUNM"GEODE"\n'] + steps
    subprocess.run(args, capture_output=True, text=True)


def save(ppm, name):
    im = Image.open(ppm).crop(GAME)
    im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
    im.save(os.path.join(IMG, name + '.png'))


def sparks(ppm):
    """how much of the sky isn't sky blue (fireworks)"""
    im = Image.open(ppm).crop(GAME).convert('RGB')
    sky = im.crop((0, 60, 256, 100))
    bg = sky.getpixel((2, 2))
    return sum(1 for p in sky.getdata() if p != bg)


def main():
    os.makedirs(IMG, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    t = lambda n: os.path.join(TMP, n + '.ppm')
    emulate(['frames:420', 'ppm:' + t('title')], 'title')
    save(t('title'), 'title')
    S = prof.sym
    emulate(['frames:240', 'type: ', 'frames:60', 'type:N001', 'frames:90',
             'poke:%04X,04' % S('joy_force'), 'frames:40', 'poke:%04X,00' % S('joy_force'), 'frames:20',
             'ppm:' + t('play')], 'play')
    save(t('play'), 'play')
    emulate(['frames:240', 'type: ', 'frames:60', 'type:N053', 'frames:120', 'ppm:' + t('vault')], 'vault')
    save(t('vault'), 'vault')
    # the ending: level 150 won by a replayed solution, then the frame
    # with the most fireworks
    pr = [tuple(map(int, l.split())) for l in open(os.path.join(ROOT, 'build', 'solutions-react8', '150.txt'))]
    loops = sum(k for k, j in pr)
    buf = S('replay_buf')
    data = sim.replay_hex(pr)
    pokes = ['poke:%04X,%s' % (buf + i // 2, data[i:i + 64]) for i in range(0, len(data), 64)]
    shots = []
    for i in range(60):
        shots += ['frames:6', 'ppm:' + t('end%02d' % i)]
    emulate(['frames:240', 'type: ', 'frames:60'] + pokes + ['poke:%04X,%04X' % (S('rp_pend'), buf), 'type:N150',
             'frames:%d' % (loops + 600)] + shots, 'end')
    best = max(range(60), key=lambda i: sparks(t('end%02d' % i)))
    save(t('end%02d' % best), 'ending')
    print('pictures in docs/img (the ending: frame %d, %d spark pixels)' % (best, sparks(t('end%02d' % best))))


if __name__ == '__main__':
    main()
