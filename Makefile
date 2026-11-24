# proj-geoderunner: Geode Runner, a single-screen digging platformer for
# the MC-10 (8K internal RAM mod + MCX32-SD required), in CG6, built on
# mc10-game-engine (the engine/ git submodule: `git submodule update
# --init` after cloning).
#
#   make                 build the game and the tools
#   make run             run the game in the emulator (also: run-geode)
#   make run-view        a still display of a sprite file's sprites
#                        (VIEW=sprites/NAME.spr, default sprites/geode.spr)
#   make run-mockup      early still mock-ups: mono RG6 (mockups/plat.py);
#                        run-mockup_blue, run-mockup_green: CG6
#   make check           headless checks (needs the VMC10 for Linux emulator)
#   make sheet           build/levels.png: a contact sheet of generated levels
#                        (tools/levelgen.py; LEVELS="1 2 3 ..." to choose)
#   make levels          build/LEVELS.DAT: the game's 150 levels (NLEVELS=...);
#                        the game reads its levels from it
#   make DEBUG=0         release build: no debug-port writes, no N level jump
#
# On the SD card the game is GEODE.BIN (RUNM"GEODE").

ENGINE  ?= engine
VMC10   ?= $(HOME)/vmc10-linux
EMU     ?= $(VMC10)/vmc10
DEBUG   ?= 1
CPPDEFS ?=
CC      ?= cc
CFLAGS  ?= -O2 -Wall -Wextra -std=c11

LOAD     := 6000
SEGMENTS := 0400-1FFF 6000-ADFF
CPPFLAGS := -E -P -w -x assembler-with-cpp -I$(ENGINE)/engine -Ibuild -Isrc -DDEBUG=$(DEBUG)
ENGSRC   := $(wildcard $(ENGINE)/engine/*.asm $(ENGINE)/engine/*.inc)
SRCINC   := $(wildcard src/*.inc)
SPRITES  := $(patsubst sprites/%.spr,build/%_spr.inc,$(wildcard sprites/*.spr))

all: build/geode.bin

build:
	mkdir -p build

# the engine's tools, built from the submodule
build/spritec: $(ENGINE)/tools/spritec.c | build
	$(CC) $(CFLAGS) -o $@ $<
build/p2decb: $(ENGINE)/tools/p2decb.c | build
	$(CC) $(CFLAGS) -o $@ $<

# the tiles, from the mock-up's art
build/tiles.inc: tools/mktiles.py mockups/plat_cg6.py | build
	python3 tools/mktiles.py > $@
build/geode.s: build/tiles.inc build/title_px.inc
build/title_px.inc: tools/mktitle.py mockups/plat_cg6.py $(ENGINE)/tools/mkfont.py | build
	python3 tools/mktitle.py > $@

# compiled sprites
build/%_spr.inc: sprites/%.spr build/spritec
	build/spritec $< > $@

# cpp handles #include/#define, then ASL assembles; p2decb writes the DECB
# binary, every byte checked to lie in the low or main segment
build/%.s: src/%.asm $(ENGSRC) $(SPRITES) $(SRCINC) | build
	$(CC) $(CPPFLAGS) $(CPPDEFS) $< -o $@
build/%.p: build/%.s
	cd build && asl -q -L -U $*.s
build/%.bin: build/%.p build/p2decb
	build/p2decb $< $@ $(LOAD) $(SEGMENTS)

# The mock-ups: still screens drawn by mockups/*.py
build/mockup_scr.inc build/mockup.png: mockups/plat.py | build
	python3 mockups/plat.py
build/mockup.s: build/mockup_scr.inc
build/mockup_%.inc build/mockup_%.png: mockups/plat_cg6.py mockups/plat.py | build
	python3 mockups/plat_cg6.py $*
build/mockup_%.s: src/mockup.asm build/mockup_%.inc $(ENGSRC) | build
	$(CC) $(CPPFLAGS) -DMK_CG6 -DMK_SCR='"mockup_$*.inc"' $(CPPDEFS) $< -o $@

# The level generator's contact sheet
LEVELS  ?= 1 3 5 8 10 15 21 33 47 88 123 150
sheet: tools/levelgen.py mockups/plat_cg6.py | build
	python3 tools/levelgen.py --sheet build/levels.png $(LEVELS)

# The level file: every level, made once by the generator
NLEVELS ?= 150
levels: build/LEVELS.DAT
build/LEVELS.DAT: tools/levelgen.py | build
	python3 tools/levelgen.py --dat $@ $(NLEVELS)
	python3 tools/levelgen.py --check $@ 1 2 3 10 75 100 $(NLEVELS)
	python3 tools/levelgen.py --verify $@

# The sprite viewer (the engine's), in the sprite file's mode
VIEW    ?= sprites/geode.spr
build/view_spr.inc: FORCE build/spritec | build
	build/spritec $(VIEW) > $@
build/view_list.inc: build/view_spr.inc $(ENGINE)/tools/sprview.py
	python3 $(ENGINE)/tools/sprview.py $(VIEW) build/view_spr.inc > $@
build/view.s: $(ENGINE)/bench/view.asm build/view_list.inc build/view_spr.inc $(ENGSRC) | build
	$(CC) $(CPPFLAGS) $(shell python3 $(ENGINE)/tools/sprview.py --defs $(VIEW)) $(CPPDEFS) $< -o $@
FORCE:

# Run in the emulator: build/sd is the MCX32-SD's SD card
SD      := build/sd
run: build/geode.bin build/LEVELS.DAT
	mkdir -p $(SD)
	cp build/LEVELS.DAT $(SD)/LEVELS.DAT
	$(MAKE) --no-print-directory run-geode
run-%: build/%.bin
	mkdir -p $(SD)
	cp $< $(SD)/$(shell echo $* | tr a-z A-Z).BIN
	$(EMU) --mcx32sd --8k --sd $(SD) --type 'RUNM"$(shell echo $* | tr a-z A-Z)"\n'

# Headless checks (needs the emulator's harness and ROMs: VMC10=...)
check: build/geode.bin build/LEVELS.DAT
	VMC10=$(VMC10) sh tests/check.sh

clean:
	rm -rf build

.PHONY: all check clean run sheet levels FORCE
.PRECIOUS: build/%.s build/%.p build/%_spr.inc build/%.bin
