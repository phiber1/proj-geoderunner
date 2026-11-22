# Geode Runner

A single-screen digging platformer for the TRS-80 MC-10, in CG6: four
real colors at 128x192, so it looks the same on NTSC and PAL machines.
Run, climb and dig through a cavern to collect every geode, while the
thieves try to carry them off.  Built on
[mc10-game-engine](https://github.com/phiber1/mc10-game-engine).

**Status: early development.**  Nothing playable yet.

**Needs:** an MC-10 with the 8K internal RAM mod and an MCX32-SD (or the
[VMC10 for Linux](https://github.com/phiber1/vmc10-linux) emulator with
`--8k --mcx32sd`).

## Building

    git clone --recurse-submodules https://github.com/phiber1/proj-geoderunner.git
    cd proj-geoderunner
    make            # build/geode.bin (GEODE.BIN on the SD card: RUNM"GEODE")
    make run        # in the emulator (VMC10=path to vmc10-linux, default ~/vmc10-linux)

Needs `asl` (the Macroassembler AS), a C compiler, cpp and Python 3 (with
Pillow for the mock-ups).  Also: `make run-view` (the sprites),
`make run-mockup_blue` (an early still mock-up of a level), `make sheet`
(`build/levels.png`: a contact sheet of generated levels).

Levels are generated: level N is always the same level, made by
`tools/levelgen.py` (a Python prototype of the generator the game will
carry).  The first levels are gentle; new styles join every ten levels: floors,
staggered ledges, rooms walled with stone, a brick pyramid with hidden
chambers, caverns dug out of solid rock, mirror images, and every 10th
level a message spelled out in ladders.  Geodes are only placed where the
hero can both reach and leave, so every level can be finished.

## Licence

Public domain (Unlicense): see `LICENSE`.
