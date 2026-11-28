# Geode Runner

A single-screen digging platformer for the TRS-80 MC-10, in CG6: four
real colors at 128x192, so it looks the same on NTSC and PAL machines.
Run, climb and dig through a cavern to collect every geode and escape
upward, level after level, while the guards close in.  Built on
[mc10-game-engine](https://github.com/phiber1/mc10-game-engine).

**Needs:** an MC-10 with the 8K internal RAM mod and an MCX32-SD (or the
[VMC10 for Linux](https://github.com/phiber1/vmc10-linux) emulator with
`--8k --mcx32sd`).

## Playing

`release/` has the game: copy `GEODE.BIN` and `LEVELS.DAT` to the SD card
and type `RUNM"GEODE"`.  `release/geoderunner.pdf` has the rules on one
page.  A and S walk, W and Z climb, SPACE digs (hold A or S with it to
choose the side), BREAK gives up a level.  A PiKey-10's joystick works
too.  Collect every geode, then climb the exit ladder out; finishing
level 150 earns a proper celebration.

## Building

    git clone --recurse-submodules https://github.com/phiber1/proj-geoderunner.git
    cd proj-geoderunner
    make            # build/geode.bin (GEODE.BIN on the SD card: RUNM"GEODE")
    make run        # in the emulator (VMC10=path to vmc10-linux, default ~/vmc10-linux)
    make check      # headless checks: drawing, movement, digging, guards,
                    # geodes, the exit, lives, the title, memory, speed
    make release    # release/: the release build, LEVELS.DAT and the one-pager

Needs `asl` (the Macroassembler AS), a C compiler, cpp and Python 3 (with
Pillow); `make docs` (the one-pager) needs Chromium.  The default build
is a test build: N followed by three digits (`N041`) jumps to that level;
`make DEBUG=0` builds without it.  Also: `make run-view` (the sprites),
`make sheet` (`build/levels.png`: a contact sheet of the levels).

## The levels

The 150 levels are made by `tools/levelgen.py` and written to
`build/LEVELS.DAT` (`make levels`; 240 bytes a level, the same byte for
byte every build).  New styles join as the game goes on: floors,
staggered ledges, rooms walled with stone, a brick pyramid, caverns dug
out of solid rock, mirror images, and every 10th level a message spelled
out in ladders.  Some geodes sit in sealed brick vaults, a few with roofs
two bricks deep.

Every level is checked to be beatable: `tools/sim.py` reproduces the
game's rules exactly (`make simcheck` compares it with the real game,
game loop by game loop), and `tools/solve.py` searches for a way through
each level, playing with a person's reaction time rather than a
machine's.  Every way it finds is then replayed on the real game in the
emulator, and must win there.  The levels come in order of how hard they
press the player, with a few gentler ones along the way.

## License

Public domain (Unlicense): see `LICENSE`.
