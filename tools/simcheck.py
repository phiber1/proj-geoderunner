#!/usr/bin/env python3
"""simcheck.py: tools/sim.py against the real game.  Plays the same input
script on a TRACE build in the VMC10 emulator (replayed one entry a game
loop) and in the simulation, and compares their state loop by loop.

    make TRACE=1 build/geode.bin && python3 tools/simcheck.py [LEVEL ...]

Prints, per level, how many loops agreed and where they first differ.
Public domain (Unlicense)."""
import os
import random
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, HERE)
import sim                      # noqa: E402
import levelgen                 # noqa: E402
import profile as prof          # noqa: E402  (sym(), VMC10)

MOVES = [sim.J_LEFT, sim.J_RIGHT, sim.J_UP, sim.J_DOWN, 0,
         sim.J_FIRE, sim.J_FIRE | sim.J_LEFT, sim.J_FIRE | sim.J_RIGHT]


def script(seed, loops):
    rnd = random.Random(seed)
    out, n = [], 0
    while n < loops:
        k = rnd.randint(2, 40)
        j = rnd.choice(MOVES)
        if j & sim.J_FIRE:
            k = rnd.randint(1, 3)
        out.append((k, j))
        n += k
    return out


def emulate(level, scr, frames, safe=False):
    sd = os.path.join(ROOT, 'build', 'sd-sim-%d' % os.getpid() + '-%d' % id(scr))
    os.makedirs(sd, exist_ok=True)
    for a, b in (('geode.bin', 'GEODE.BIN'), ('LEVELS.DAT', 'LEVELS.DAT')):
        open(os.path.join(sd, b), 'wb').write(open(os.path.join(ROOT, 'build', a), 'rb').read())
    buf = prof.sym('replay_buf')
    data = ''.join('%02X%02X' % (k, j) for k, j in scr) + '00'
    pokes = ['poke:%04X,%s' % (buf + i // 2, data[i:i + 64]) for i in range(0, len(data), 64)]
    args = [os.path.join(prof.VMC10, 'build', 'headless'), os.path.join(prof.VMC10, 'roms', 'MC10.BIN'),
            'mcx32sd:' + os.path.join(prof.VMC10, 'roms', 'mcx32sd_flash.bin'), '8k', 'sd:' + sd,
            'frames:200', 'type:RUNM"GEODE"\n', 'frames:240', 'type: ', 'frames:60'] + pokes + (
            ['poke:%04X,01' % prof.sym('dbg_safe')] if safe else []) + [
            'poke:%04X,%04X' % (prof.sym('rp_pend'), buf), 'dbgport:BE00',
            'type:N%03d' % level, 'frames:%d' % frames]
    out = subprocess.run(args, capture_output=True, text=True).stdout
    import shutil
    shutil.rmtree(sd, ignore_errors=True)
    vals = [int(v, 16) for v in re.findall(r'val=\$(\w+)', out)]
    starts = [i for i in range(len(vals) - 3) if vals[i:i + 4] == [0x5A, 0xA5, 0x5A, 0xC3]]
    return vals[starts[0] + 4:]           # (the first: a death restarts the level)


def records(vals, nguard):
    """the loops' records: $A5 and 5 + 4 a guard bytes each, back to back"""
    n = 1 + 5 + 4 * nguard
    recs = []
    for i in range(0, len(vals) - n + 1, n):
        if vals[i] != 0xA5:
            break
        recs.append(vals[i + 1:i + n])
    return recs


def check(level, seed=1, loops=900, safe=False, events=None):
    data = open(os.path.join(ROOT, 'build', 'LEVELS.DAT'), 'rb').read()
    rows = levelgen.decode(data[16 + 240 * (level - 1):16 + 240 * level])
    g = sim.Game(rows, safe=safe)
    scr = script(seed * 1000 + level, loops)
    real = records(emulate(level, scr, loops + 200, safe), len(g.guards))
    if events is not None:
        events.append(g.events)
    joys = [j for k, j in scr for _ in range(k)]
    for i, rec in enumerate(real):
        if i >= len(joys):
            return i, None
        g.step(joys[i])
        mine = g.trace()
        if mine != rec:
            return i, (mine, rec)
        if g.dead:                      # (the game restarts the level: done)
            return i + 1, None
    return len(real), None


if __name__ == '__main__':
    for lv in [int(a) for a in sys.argv[1:]] or [1, 5, 20, 41, 60, 100, 150]:
        n, diff = check(lv)
        print('level %d: %d loops agree' % (lv, n) + ('' if not diff else
              '; then sim %s, game %s' % diff))
