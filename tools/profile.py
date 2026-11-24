#!/usr/bin/env python3
"""profile.py: where the game's frames go.  Runs a PROFILE=1 build
(make PROFILE=1) in the VMC10 headless emulator on some levels, the hero
put in a few places and walking back and forth there with the guards
chasing (unable to catch him; the frames he's put in are left out), and
sums the cycles between the game's timing marks (PROF in src/geode.asm).

    python3 tools/profile.py [LEVEL ...]       (default: 41 53 60 100 150)

Prints, per level, the main loop's cycles (median, worst; a frame has
14,934) and the parts' (median and worst per frame).  Needs build/geode.bin
built with PROFILE=1 and VMC10 (default ~/vmc10-linux).  Public domain
(Unlicense)."""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
VMC10 = os.environ.get('VMC10', os.path.expanduser('~/vmc10-linux'))
FRAME = 14934
PARTS = {1: 'keys', 2: 'hero', 3: 'holes/exit', 4: 'hero draw', 0x10: 'guard update',
         0x11: 'guard pose', 0x12: 'guard draw', 0x13: 'guards (rest)', 7: 'loop (rest)'}


def sym(name):
    lst = open(os.path.join(ROOT, 'build', 'geode.lst')).read()
    tab = lst[lst.index('Symbol Table'):]
    m = re.search(r'\b%s\s*:\s*([0-9A-F]+)' % re.escape(name), tab)
    return int(m.group(1), 16)


def run(level, places):
    sd = os.path.join(ROOT, 'build', 'sd-prof')
    os.makedirs(sd, exist_ok=True)
    for a, b in (('geode.bin', 'GEODE.BIN'), ('LEVELS.DAT', 'LEVELS.DAT')):
        open(os.path.join(sd, b), 'wb').write(open(os.path.join(ROOT, 'build', a), 'rb').read())
    args = [os.path.join(VMC10, 'build', 'headless'), os.path.join(VMC10, 'roms', 'MC10.BIN'),
            'mcx32sd:' + os.path.join(VMC10, 'roms', 'mcx32sd_flash.bin'), '8k', 'sd:' + sd,
            'frames:200', 'type:RUNM"GEODE"\n', 'frames:240', 'type: ', 'frames:60',
            'type:N%03d' % level, 'frames:120', 'poke:%04X,01' % sym('dbg_safe'),
            'poke:%04X,04' % sym('joy_force'), 'frames:2', 'poke:%04X,00' % sym('joy_force')]
    args += ['dbgport:BE00']
    for (r, c) in places:
        args += ['poke:%04X,%02X%02X' % (sym('h_r'), r, c),
                 'poke:%04X,%02X%02X' % (sym('hero_a'), c * 4, (r + 1) * 12),
                 'frames:60']
        for k in (4, 8) * 5:            # (walking back and forth)
            args += ['poke:%04X,%02X' % (sym('joy_force'), k), 'frames:30']
        args += ['poke:%04X,00' % sym('joy_force')]
    out = subprocess.run(args, capture_output=True, text=True).stdout
    marks = [(int(t), int(v, 16)) for t, v in re.findall(r'total=(\d+) dt=\d+ val=\$(\w+)', out)]
    return marks


def analyse(marks):
    loops, cur = [], None
    for t, v in marks:
        if v == 1:
            if cur:
                loops.append(cur)
            cur = [(t, v)]
        elif cur:
            cur.append((t, v))
    totals, parts = [], {}
    for lp in loops:
        if len(lp) < 2:
            continue
        totals.append(lp[-1][0] - lp[0][0])
        acc = {}
        for (t0, v0), (t1, v1) in zip(lp, lp[1:]):
            name = PARTS.get(v0, '')
            if name:
                acc[name] = acc.get(name, 0) + t1 - t0
        if acc.get('hero draw', 0) > 6000:      # (the hero put somewhere: not play)
            totals.pop()
            continue
        for k, v in acc.items():
            parts.setdefault(k, []).append(v)
    return totals, parts


def med(a):
    a = sorted(a)
    return a[len(a) // 2] if a else 0


def main():
    levels = [int(a) for a in sys.argv[1:]] or [41, 53, 60, 100, 150]
    sys.path.insert(0, HERE)
    import levelgen
    data = open(os.path.join(ROOT, 'build', 'LEVELS.DAT'), 'rb').read()
    for n in levels:
        lv = levelgen.decode(data[16 + 240 * (n - 1):16 + 240 * n])
        g = [list(r.replace('T', '.').replace('E', '.').replace('P', '.').replace('X', '.')) for r in lv]
        cells = levelgen.stand_cells(g)
        places = [cells[i * len(cells) // 4] for i in range(4)]
        totals, parts = analyse(run(n, places))
        over = sum(1 for t in totals if t > FRAME)
        print('level %d: loop median %d, worst %d, over a frame %d of %d' %
              (n, med(totals), max(totals or [0]), over, len(totals)))
        for k in ('keys', 'hero', 'holes/exit', 'hero draw', 'guard update', 'guard pose',
                  'guard draw', 'guards (rest)', 'loop (rest)'):
            if k in parts:
                print('    %-14s median %5d  worst %5d' % (k, med(parts[k]), max(parts[k])))


if __name__ == '__main__':
    main()
