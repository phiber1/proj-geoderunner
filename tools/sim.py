#!/usr/bin/env python3
"""sim.py: Geode Runner's rules in Python, step for step as the game plays
them (src/hero.inc, holes.inc, guards.inc, geode.asm), for solvers and
level design.  One step() is one pass of the game's main loop.

    from sim import Game
    g = Game(level_rows)          # 15 strings of 32 cells, '.BSH-TPEX'
    g.step(joy)                   # joy: J_UP | J_DOWN | J_LEFT | J_RIGHT | J_FIRE
    g.dead, g.done, g.trace()

Only play is modeled (no drawing, no sound).  tools/simcheck.py checks it
against the real game, frame by frame, in the VMC10 emulator.  Public
domain (Unlicense)."""

J_UP, J_DOWN, J_LEFT, J_RIGHT, J_FIRE = 1, 2, 4, 8, 16
C_AIR, C_BRICK, C_STONE, C_LADDER, C_CABLE, C_GEODE, C_HERO, C_GUARD, C_EXIT = range(9)
C_DIG1, C_DIG2, C_FILL1, C_FILL2 = 9, 10, 11, 12
CODES = '.BSH-TPEX'
ROWS, COLS = 15, 32
MAX_GUARDS, HOLES = 4, 8

H_WALK, H_CLIMB, H_FALL, DIG_LATCH = 8, 10, 12, 12
D_NONE, D_LEFT, D_RIGHT, D_UP, D_DOWN, D_FALL = range(6)
CLIMBTAB = [0, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1]
HS_DIG, HS_OPEN, HS_FILL = 1, 2, 3
DIG_T, OPEN_T, FILL_T = 12, 300, 24
G_WALK, G_CLIMB, G_FALL = 14, 16, 14       # guards_speed: one pace on every level
TRAP_T, CARRY_T = 210, 600
GS_FREE, GS_TRAP = 0, 1
SEED = 0xACE1                               # (RP_SEED: a replay's respawn seed)

W_WALL, W_UP, W_FLOOR, W_DOWN = 1, 2, 4, 8


def is_solid(a):
    return a in (C_BRICK, C_STONE, C_DIG1, C_DIG2)


def guard_solid(a):
    return is_solid(a) or a in (C_FILL1, C_FILL2)


class Guard:
    __slots__ = ('x', 'y', 'r', 'c', 't', 'dir', 'face', 'on', 'st', 'tt',
                 'carry', 'ct', 'out', 'acc')

    def __init__(self, r, c):
        self.r, self.c = r, c
        self.x, self.y = c * 4, (r + 1) * 12
        self.t = self.dir = self.face = self.on = self.st = 0
        self.tt = self.carry = self.ct = self.out = self.acc = 0


class Game:
    def __init__(self, rows, seed=SEED, safe=False):
        self.safe = safe                # (as the game's dbg_safe: never caught)
        self.events = {}
        self.map = [[CODES.index(ch) for ch in row] for row in rows]
        self.guards = []
        hero = None
        for r in range(ROWS):                       # lv_actors
            for c in range(COLS):
                a = self.map[r][c]
                if a == C_HERO:
                    hero = (r, c)
                    self.map[r][c] = C_AIR
                elif a == C_GUARD:
                    if len(self.guards) < MAX_GUARDS:
                        self.guards.append(Guard(r, c))
                        self.map[r][c] = C_AIR
        self.g_left, self.ex_state, self.ex_bot, self.ex_col = 0, 0, 0, 0
        for r in range(ROWS):                       # lv_scan
            for c in range(COLS):
                a = self.map[r][c]
                if a == C_GEODE:
                    self.g_left += 1
                if a == C_EXIT:
                    self.ex_bot, self.ex_col = r, c
        self.ex_row = self.ex_t = 0
        self.holes = [[0, 0, 0, 0] for _ in range(HOLES)]   # r, c, st, t
        self.seed = seed or 0xACE1
        self.started = 0
        self.r, self.c = hero                       # hero_init
        self.x, self.y = self.c * 4, (self.r + 1) * 12
        self.t = self.dir = self.face = self.on = self.dig = 0
        self.dlat = self.ddir = self.spw = self.head = 0
        self.dead = 0
        self.loops = 0
        self.score = 0

    # ---------------------------------------------------------------- map

    def cell_at(self, r, c):
        if r < 0:
            return C_AIR
        if r >= ROWS or c < 0 or c >= COLS:
            return C_STONE
        a = self.map[r][c]
        return C_AIR if a == C_EXIT else a

    @property
    def done(self):
        return self.ex_state == 2 and self.r == 0 and self.t == 0

    # ---------------------------------------------------------------- the loop

    def step(self, joy):
        """one pass of the main loop with these keys down"""
        self.joy = joy
        self.hero_update()
        self.hole_update()
        self.exit_update()
        if not self.started and (self.t or self.dig):
            self.started = 1
        if self.started:
            self.think = 1
            for gd in self.guards:
                self.guard_update(gd)
        if not self.safe and self.caught():
            self.dead = 1
        self.loops += 1

    def trace(self):
        """as the game's TRACE build reports it, each loop"""
        out = [self.x & 255, self.y & 255, self.dead, self.g_left, self.ex_state]
        for gd in self.guards:
            out += [gd.x & 255, gd.y & 255, gd.st, gd.carry]
        return out

    # ---------------------------------------------------------------- hero

    def hero_update(self):
        j = self.joy
        f = j & J_FIRE
        press = (f ^ self.spw) & f
        self.spw = f
        if press:
            b = j & (J_LEFT | J_RIGHT)
            if not b:
                b = J_LEFT if self.face else J_RIGHT
            self.ddir = b
            self.dlat = DIG_LATCH
        elif self.dlat:
            self.dlat -= 1
        if self.dig:
            self.dig -= 1
            return
        if not self.t:
            return self.hero_decide()
        if self.dir == D_LEFT:
            if not self.t & 1:
                self.x -= 1
        elif self.dir == D_RIGHT:
            if not self.t & 1:
                self.x += 1
        elif self.dir == D_UP:
            self.y -= CLIMBTAB[self.t]
        elif self.dir == D_DOWN:
            self.y += CLIMBTAB[self.t]
        else:
            self.y += 1
        self.t -= 1
        if not self.t:
            self.hero_decide()

    def floor_at(self, c):
        return 0 <= c < COLS and is_solid(self.cell_at(self.r + 1, c))

    def head_in(self, r, c):
        return any(gd.r == r and gd.c == c for gd in self.guards)

    def hero_decide(self):
        self.dir = self.on = self.head = 0
        here = self.cell_at(self.r, self.c)
        if here == C_GEODE:
            self.geode_take()
            here = C_AIR
        below = self.cell_at(self.r + 1, self.c)
        self.here, self.below = here, below
        if here == C_LADDER:
            if is_solid(below) or self.floor_at(self.c - 1) or self.floor_at(self.c + 1):
                pass                                    # (standing at a ladder's foot)
            else:
                self.on = 1
        elif here == C_CABLE:
            self.on = 2
        elif below == C_LADDER or is_solid(below):
            pass
        elif self.head_in(self.r + 1, self.c):
            self.head = 1
        else:
            return self.hero_fall()
        j = self.joy
        if self.dlat:                                   # hu_keys
            if self.on:
                self.dlat = 0
            else:
                b = self.ddir
                dc = -1 if b & J_LEFT else 1 if b & J_RIGHT else (-1 if self.face else 1)
                self.face = 1 if dc < 0 else 0
                cc = self.c + dc
                if (self.cell_at(self.r, cc) == C_AIR and self.cell_at(self.r + 1, cc) == C_BRICK
                        and self.hole_start(self.r + 1, cc)):
                    self.dig = DIG_T
                    self.dlat = 0
                    return
                self.dlat = 0
        if j & J_UP and here == C_LADDER and self.r > 0 and not is_solid(self.cell_at(self.r - 1, self.c)):
            self.r -= 1
            self.dir, self.t = D_UP, H_CLIMB
            return
        if j & J_DOWN:
            if self.head:
                self.dead = 1
                return
            if below == C_LADDER:
                self.r += 1
                self.dir, self.t = D_DOWN, H_CLIMB
                return
            if not is_solid(below) and here in (C_LADDER, C_CABLE):
                return self.hero_fall()
        if j & J_LEFT and self.c > 0 and not is_solid(self.cell_at(self.r, self.c - 1)):
            self.c -= 1
            self.face = 1
            self.dir, self.t = D_LEFT, H_WALK
            return
        if j & J_RIGHT and self.c < COLS - 1 and not is_solid(self.cell_at(self.r, self.c + 1)):
            self.c += 1
            self.face = 0
            self.dir, self.t = D_RIGHT, H_WALK

    def hero_fall(self):
        self.r += 1
        self.dir, self.t = D_FALL, H_FALL

    def geode_take(self):
        self.events['geode'] = self.events.get('geode', 0) + 1
        self.map[self.r][self.c] = C_AIR
        self.score += 250
        self.g_left -= 1
        if not self.g_left:
            self.ex_state, self.ex_row, self.ex_t = 1, self.ex_bot, 1

    def exit_update(self):
        if self.ex_state != 1:
            return
        self.ex_t -= 1
        if self.ex_t:
            return
        self.ex_t = 4
        self.map[self.ex_row][self.ex_col] = C_LADDER
        self.ex_row -= 1
        if self.ex_row < 0:
            self.ex_state = 2

    # ---------------------------------------------------------------- holes

    def hole_start(self, r, c):
        for h in self.holes:
            if not h[2]:
                h[0], h[1], h[2], h[3] = r, c, HS_DIG, DIG_T
                self.map[r][c] = C_DIG1
                return True
        return False

    def hole_update(self):
        for h in self.holes:
            if not h[2]:
                continue
            r, c = h[0], h[1]
            h[3] -= 1
            if h[2] == HS_DIG:
                if h[3] == DIG_T // 2:
                    self.map[r][c] = C_DIG2
                elif h[3] == 0:
                    h[2], h[3] = HS_OPEN, OPEN_T
                    self.map[r][c] = C_AIR
            elif h[2] == HS_OPEN:
                if h[3] == 0:
                    h[2], h[3] = HS_FILL, FILL_T
                    self.map[r][c] = C_FILL2
            else:
                if h[3] == FILL_T // 2:
                    self.map[r][c] = C_FILL1
                elif h[3] == 0:
                    h[2] = 0
                    self.map[r][c] = C_BRICK
                    self.guard_bury(r, c)
                    if (self.r, self.c) == (r, c):
                        self.dead = 1

    def hole_open(self, gd):
        return any(h[2] >= HS_OPEN and h[0] == gd.r and h[1] == gd.c for h in self.holes)

    # ---------------------------------------------------------------- guards

    def guard_in(self, me, r, c):
        return any(gd is not me and gd.r == r and gd.c == c for gd in self.guards)

    def trapped_in(self, r, c):
        return any(gd.st == GS_TRAP and gd.r == r and gd.c == c for gd in self.guards)

    def gd_free(self, me, r, c):
        if is_solid(self.cell_at(r, c)):
            return False
        if self.cell_at(r + 1, c) in (C_FILL1, C_FILL2):
            return False
        return not self.guard_in(me, r, c)

    def guard_update(self, gd):
        if gd.st == GS_TRAP:
            gd.tt -= 1
            if gd.tt:
                return
            if is_solid(self.cell_at(gd.r - 1, gd.c)) or self.guard_in(gd, gd.r - 1, gd.c):
                gd.tt = 10
                return
            self.events['climb out'] = self.events.get('climb out', 0) + 1
            gd.st = GS_FREE
            gd.r -= 1
            gd.out = 1
            gd.dir, gd.t, gd.acc = D_UP, G_CLIMB, 0
            return
        if gd.carry and gd.ct:
            gd.ct -= 1
        if not gd.t:
            return self.gd_decide(gd)
        if gd.dir in (D_LEFT, D_RIGHT):
            a = gd.acc + 4
            if a >= G_WALK:
                gd.acc = a - G_WALK
                gd.x += -1 if gd.dir == D_LEFT else 1
            else:
                gd.acc = a
        elif gd.dir:
            n = G_FALL if gd.dir == D_FALL else G_CLIMB
            a = gd.acc + 12
            if a >= n:
                gd.acc = a - n
                gd.y += -1 if gd.dir == D_UP else 1
            else:
                gd.acc = a
        gd.t -= 1
        if not gd.t:
            self.gd_decide(gd)

    def gd_decide(self, gd):
        gd.dir = gd.on = 0
        here = self.cell_at(gd.r, gd.c)
        if here == C_GEODE and not gd.carry:
            self.map[gd.r][gd.c] = C_AIR
            self.events['carry'] = self.events.get('carry', 0) + 1
            gd.carry, gd.ct = 1, CARRY_T
            here = C_AIR
        if gd.out:                                  # just out of a hole: step off
            gd.out = 0
            goal = self.c if self.c != gd.c else gd.c + 1
            self.gd_toward(gd, goal)
            if not gd.dir:
                self.gd_toward(gd, (2 * gd.c - goal) & 255)
            return
        if self.hole_open(gd):
            return self.gd_trap(gd)
        if here == C_LADDER:
            gd.on = 1
            below = self.cell_at(gd.r + 1, gd.c)
        elif here == C_CABLE:
            gd.on = 2
            below = self.cell_at(gd.r + 1, gd.c)
        else:
            below = self.cell_at(gd.r + 1, gd.c)
            if not (below == C_LADDER or guard_solid(below) or self.trapped_in(gd.r + 1, gd.c)):
                return self.gd_fall(gd)
        if gd.carry and not gd.ct and not gd.on and here == C_AIR:
            self.map[gd.r][gd.c] = C_GEODE
            self.events['drop'] = self.events.get('drop', 0) + 1
            gd.carry = 0
        if not self.think:                          # gd_think: one a frame
            return
        self.think = 0
        hr = self.gd_hrow()
        if hr == gd.r:
            return self.gd_toward(gd, self.c)
        if hr > gd.r:                               # the hero lower
            if below == C_LADDER and self.gd_free(gd, gd.r + 1, gd.c):
                gd.r += 1
                gd.dir, gd.t, gd.acc = D_DOWN, G_CLIMB, 0
                return
            if gd.on and not guard_solid(below) and not self.guard_in(gd, gd.r + 1, gd.c):
                return self.gd_fall(gd)
            return self.gd_toward(gd, self.gd_scan(gd, 2))
        if here == C_LADDER and self.gd_free(gd, gd.r - 1, gd.c):   # higher
            gd.r -= 1
            gd.dir, gd.t, gd.acc = D_UP, G_CLIMB, 0
            return
        return self.gd_toward(gd, self.gd_scan(gd, 1))

    def gd_toward(self, gd, goal):
        if goal == gd.c:
            return self.gd_stand(gd)
        d = -1 if goal < gd.c else 1
        cc = gd.c + d
        if not self.gd_free(gd, gd.r, cc) or self.gd_inpath(gd, cc):
            return self.gd_stand(gd)
        gd.c = cc
        gd.face = 1 if d < 0 else 0
        gd.dir, gd.t, gd.acc = (D_LEFT if d < 0 else D_RIGHT), G_WALK, 0

    def gd_stand(self, gd):
        gd.dir, gd.t = 0, 6

    def gd_fall(self, gd):
        if self.guard_in(gd, gd.r + 1, gd.c):
            return self.gd_stand(gd)
        gd.r += 1
        gd.dir, gd.t, gd.acc = D_FALL, G_FALL, 0

    def gd_trap(self, gd):
        self.events['trap'] = self.events.get('trap', 0) + 1
        gd.st, gd.tt = GS_TRAP, TRAP_T
        self.score += 75
        if gd.carry:
            gd.carry = 0
            if gd.r > 0 and self.cell_at(gd.r - 1, gd.c) == C_AIR:
                self.map[gd.r - 1][gd.c] = C_GEODE

    def gd_hrow(self):
        if self.dir != D_FALL:
            return self.r
        hr = self.r
        while True:
            a = self.cell_at(hr, self.c)
            if a in (C_LADDER, C_CABLE):
                return hr
            b = self.cell_at(hr + 1, self.c)
            if b == C_LADDER or is_solid(b):
                return hr
            hr += 1
            if hr >= ROWS - 1:
                return hr

    def gd_inpath(self, gd, col):
        if self.dir != D_FALL or col != self.c:
            return False
        if self.r - 1 > gd.r:
            return False
        return self.gd_hrow() >= gd.r

    def way(self, r, c):
        """waytab's entry for a cell (as way_cell)"""
        here = self.cell_at(r, c)
        below = C_STONE if r == ROWS - 1 else self.cell_at(r + 1, c)
        if is_solid(here):
            return W_WALL
        v = 0
        if here == C_LADDER and not is_solid(self.cell_at(r - 1, c)):
            v |= W_UP
        if here in (C_LADDER, C_CABLE) or below == C_LADDER or guard_solid(below):
            v |= W_FLOOR
        if below == C_LADDER or (here != C_LADDER and not guard_solid(below)):
            v |= W_DOWN
        return v

    def gd_way(self, gd, col, want):
        """None: a wall or a gap (stop); True: the way wanted; False: on"""
        v = self.way(gd.r, col)
        if v & W_WALL:
            return None
        if want == 1:
            if v & W_UP:
                return True
            return False if v & W_FLOOR else None
        return bool(v & W_DOWN)

    def gd_scan(self, gd, want):
        goal = self.c
        l = rr = gd.c
        lok = rok = True
        while lok or rok:
            if lok:
                l -= 1
                if l < 0:
                    lok = False
                else:
                    w = self.gd_way(gd, l, want)
                    if w is None:
                        lok = False
                    elif w:
                        goal = l
                        if rok and rr + 1 < COLS:
                            w2 = self.gd_way(gd, rr + 1, want)
                            if w2 and self.c > gd.c:
                                goal = rr + 1
                        return goal
            if rok:
                rr += 1
                if rr >= COLS:
                    rok = False
                else:
                    w = self.gd_way(gd, rr, want)
                    if w is None:
                        rok = False
                    elif w:
                        return rr
        return goal

    def rnd(self):
        s = self.seed
        lsb = s & 1
        s >>= 1
        if lsb:
            s ^= 0xB400
        self.seed = s
        return s & 255

    def guard_bury(self, r, c):
        for gd in self.guards:
            if gd.st == GS_TRAP and gd.r == r and gd.c == c:
                self.events['bury'] = self.events.get('bury', 0) + 1
                while True:                         # guard_respawn
                    col = self.rnd() & (COLS - 1)
                    if self.cell_at(0, col) == C_AIR:
                        break
                gd.r, gd.c = 0, col
                gd.x, gd.y = col * 4, 12
                gd.t = gd.dir = gd.st = gd.carry = gd.on = gd.out = 0
                self.score += 75

    def caught(self):
        for gd in self.guards:
            if gd.st:
                continue
            if abs(gd.x - self.x) <= 3 and abs(gd.y - self.y) <= 8:
                return True
        return False
