#!/usr/bin/env python3
"""shots.py: the one-pager's pictures (docs/img/*.png), taken from the
game itself in the VMC10 headless emulator (a test build: it can jump to
a level).

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
    # a word level (every tenth: a message in ladders: level 20's, MC10
    # 1983, a hint in plain sight at the password); not the ending,
    # which stays a surprise
    emulate(['frames:240', 'type: ', 'frames:60', 'type:N020', 'frames:120', 'ppm:' + t('words')], 'words')
    save(t('words'), 'words')
    print('pictures in docs/img')


if __name__ == '__main__':
    main()
