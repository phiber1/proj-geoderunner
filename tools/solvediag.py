#!/usr/bin/env python3
"""solvediag.py: why tools/solve.py gives up on a level: how its search
ended (no states left, or out of steps), and the best state then (geodes
left, those carried by guards, those in vaults, the exit).

    python3 tools/solvediag.py LEVEL ...

Public domain (Unlicense)."""
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import solve                    # noqa: E402
import levelgen                 # noqa: E402


def diag(n):
    rows = solve.level_rows(n)
    s = solve.Solver(rows)
    info = {}
    joys, g = s.solve(report=info)
    if joys is not None:
        return n, 'solved'
    b = info.get('best')
    g0 = [list(r.replace('T', '.').replace('E', '.').replace('P', '.').replace('X', '.')) for r in rows]
    st = [(r, c) for r in range(15) for c in range(32) if rows[r][c] == 'P'][0]
    nod = levelgen.reach(g0, st, dig=False)
    vault = [p for p in solve.g_geodes(b) if p not in nod]
    return n, '%s at step %d: geodes left %d (on the map %d, in vaults %d, carried %d), exit %d, loops %d' % (
        info['end'], info['step'], b.g_left, len(solve.g_geodes(b)), len(vault),
        sum(1 for gd in b.guards if gd.carry), b.ex_state, b.loops)


if __name__ == '__main__':
    with Pool(20) as p:
        for n, msg in p.imap_unordered(diag, [int(a) for a in sys.argv[1:]]):
            print('level %3d: %s' % (n, msg), flush=True)
