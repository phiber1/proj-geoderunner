#!/bin/sh
# check.sh: headless checks of Geode Runner (src/geode.asm), run with
# "make check" from the repository root.  Loads build/geode.bin with
# RUNM from an SD folder holding build/LEVELS.DAT, as a player would.
# Needs the VMC10 for Linux emulator's headless harness and ROMs
# (VMC10=..., default ~/vmc10-linux).  The game's debug hooks hold keys
# (joy_force), keep the guards from catching the hero (dbg_safe) and count
# main loop passes (dbg_loops).
set -u
VMC10=${VMC10:-$HOME/vmc10-linux}
H=$VMC10/build/headless
R=$VMC10/roms
LST=build/geode.lst
SD=build/sd-check
mkdir -p $SD && cp build/geode.bin $SD/GEODE.BIN && cp build/LEVELS.DAT $SD/LEVELS.DAT
pass=0; fail=0
check() {   # name, condition (shell test)
    if eval "$2"; then echo "PASS  $1"; pass=$((pass+1)); else echo "FAIL  $1"; fail=$((fail+1)); fi
}
sym() { printf '%04X' 0x$(awk '/Symbol Table/{p=1} p' $LST | tr '|' '\n' | awk -v n=$1 '$1==n{print $3}'); }
off() { printf '%04X' $((0x$1 + $2)); }
# load the game the way a player does; level 1 is drawn after ~60 frames
run() { $H $R/MC10.BIN mcx32sd:$R/mcx32sd_flash.bin 8k sd:$SD frames:200 'type:RUNM"GEODE"\n' frames:60 "$@"; }
byte() { grep "^mem $1" | sed -n "${2:-1}p" | awk '{print strtonum("0x"$3)}'; }
bytes() { grep "^mem $1" | sed -n "${2:-1}p" | cut -d: -f2 | tr -d ' '; }

MAP=$(sym lv_map); TMAP=$(sym tmap); HERO=$(sym hero_a); GUARDS=$(sym guards); NGUARD=$(sym nguard)
GD=$(awk '/^GD_SIZE/{print $3}' src/geode.asm)
HR=$(sym h_r); JF=$(sym joy_force); DS=$(sym dbg_safe); DL=$(sym dbg_loops); FC=$(sym frame_count)
SC=$(sym score); LI=$(sym lives); LV=$(sym level); GL=$(sym g_left); ES=$(sym ex_state); HD=$(sym h_dead)
G0R=$(off $GUARDS 8); G0ST=$(off $GUARDS 14)
cell() { off $MAP $(($1 * 32 + $2)); }
LOWEND=$(off $TMAP 480); LOWLEN=$((0x2000 - 0x$LOWEND))
# the memory the integrity check reads
STATE="mem:$MAP,480 mem:$TMAP,480 mem:4000,6144 mem:$HERO,8 mem:$GUARDS,$((GD * 4)) mem:$NGUARD,1"
integrity() { python3 tests/expect.py integrity $1 $MAP $TMAP $HERO $GUARDS $NGUARD $GD; }
D=$(mktemp -d)

# 1. Level 1 loads from LEVELS.DAT and is drawn: the tile map and every
#    screen byte of the level (outside the actors) match the tile art.
run $STATE > $D/s1
r=$(integrity $D/s1)
check "level 1 drawn: $r" "[ \"$r\" = 'tmap_bad=0 screen_bad=0' ]"

# 2. Moving (walking left, up the ladder, along the floor) and the guard
#    chasing leave the screen intact: no tiles drawn in the wrong places.
run poke:$DS,01 poke:$JF,04 frames:24 poke:$JF,01 frames:36 poke:$JF,04 frames:60 poke:$JF,08 frames:40 poke:$JF,00 frames:30 $STATE > $D/s2
r=$(integrity $D/s2)
check "after walking, climbing and a guard chasing: $r" "[ \"$r\" = 'tmap_bad=0 screen_bad=0' ]"

# 3. The hero walks (left 3 cells) and climbs (the ladder at column 27).
out=$(run mem:$HR,2 poke:$JF,04 frames:24 mem:$HR,2 poke:$JF,01 frames:36 mem:$HR,2)
check "walks left: $(echo "$out" | bytes $HR 1) -> $(echo "$out" | bytes $HR 2)" "[ $(echo "$out" | bytes $HR 2) = 0D1B ]"
check "climbs the ladder: -> $(echo "$out" | bytes $HR 3)" "[ $(echo "$out" | bytes $HR 3) = 0A1B ]"

# 4. The guard waits for the hero's first move.
out=$(run mem:$G0R,2 frames:240 mem:$G0R,2 poke:$JF,04 frames:4 poke:$JF,00 frames:60 mem:$G0R,2)
g1=$(echo "$out" | bytes $G0R 1); g2=$(echo "$out" | bytes $G0R 2); g3=$(echo "$out" | bytes $G0R 3)
check "the guard waits ($g1, still $g2), then moves ($g3)" "[ $g1 = $g2 ] && [ $g2 != $g3 ]"

# 5. Digging: the brick below-left crumbles (still solid), opens, and fills
#    again; the screen stays right throughout.
out=$(run poke:$JF,14 frames:1 poke:$JF,00 frames:4 mem:$(cell 14 29),1 frames:12 mem:$(cell 14 29),1 frames:330 mem:$(cell 14 29),1 $STATE)
echo "$out" > $D/s5
check "digging: $(echo "$out" | bytes $(cell 14 29) 1) (digging), $(echo "$out" | bytes $(cell 14 29) 2) (open), $(echo "$out" | bytes $(cell 14 29) 3) (brick again)" \
      "[ $(echo "$out" | bytes $(cell 14 29) 1) = 09 ] && [ $(echo "$out" | bytes $(cell 14 29) 2) = 00 ] && [ $(echo "$out" | bytes $(cell 14 29) 3) = 01 ]"
r=$(integrity $D/s5)
check "after a hole dug and filled: $r" "[ \"$r\" = 'tmap_bad=0 screen_bad=0' ]"

# 6. A hole filling on the hero kills him: a life less, the level again.
out=$(run poke:$JF,14 frames:1 poke:$JF,00 frames:16 poke:$JF,04 frames:6 poke:$JF,00 poke:$DS,01 frames:450 mem:$LI,1 mem:$HR,2)
check "a hole filling on him: lives $(echo "$out" | byte $LI), back at the start ($(echo "$out" | bytes $HR))" \
      "[ $(echo "$out" | byte $LI) -eq 2 ] && [ $(echo "$out" | bytes $HR) = 0D1E ]"

# 7. The guard catches a hero who stands still: a life less.
out=$(run poke:$JF,04 frames:2 poke:$JF,08 frames:2 poke:$JF,00 frames:500 mem:$LI,1)
check "caught by the guard: lives $(echo "$out" | byte $LI)" "[ $(echo "$out" | byte $LI) -eq 2 ]"

# 8. Trapped in a hole (75), buried when it fills (75 more), back at the
#    top; the memory past the buffers untouched, the screen right.  The
#    scene is set up by hand (not left to the level's layout): the hero
#    digs left, and late in the hole's life the guard is put on the cell
#    above it (13, 29), so he falls in and the hole fills on him.  (State
#    and score are sampled every 5 frames.)
samples=""; for i in $(seq 1 60); do samples="$samples frames:5 mem:$G0ST,1 mem:$SC,3"; done
out=$(run mem:$LOWEND,$LOWLEN poke:$DS,01 poke:$JF,14 frames:1 poke:$JF,00 frames:200 \
      poke:$GUARDS,74A8 poke:$G0R,0D1D0000000000 $samples mem:$G0R,1 mem:$LOWEND,$LOWLEN $STATE)
echo "$out" > $D/s8
trapped=$(echo "$out" | grep "^mem $G0ST" | awk '$3=="01"' | wc -l)
s75=$(echo "$out" | grep "^mem $SC" | cut -d: -f2 | tr -d ' ' | grep -c '^000075$')
last=$(echo "$out" | grep "^mem $SC" | tail -1 | cut -d: -f2 | tr -d ' ')
m1=$(echo "$out" | bytes $LOWEND 1 | md5sum); m2=$(echo "$out" | bytes $LOWEND 2 | md5sum)
check "trapped (seen $trapped times, score 000075 $s75 times), buried (score $last), back up (row $(echo "$out" | byte $G0R))" \
      "[ $trapped -gt 0 ] && [ $s75 -gt 0 ] && [ $last = 000150 ] && [ $(echo "$out" | byte $G0R) -lt 13 ]"
check "the memory past the buffers untouched by the burial" "[ \"$m1\" = \"$m2\" ]"
r=$(integrity $D/s8)
check "after a burial and respawn: $r" "[ \"$r\" = 'tmap_bad=0 screen_bad=0' ]"

# 9. A guard moved far in one go (as a respawn does) is erased and redrawn
#    by itself: the patch never outgrows the shadow buffer.
out=$(run mem:$LOWEND,$LOWLEN poke:$GUARDS,7CB4 poke:$G0R,0E1F frames:4 poke:$GUARDS,400C poke:$(off $GUARDS 6),0000 poke:$G0R,0010 poke:$JF,04 frames:2 poke:$JF,00 frames:10 mem:$LOWEND,$LOWLEN)
m1=$(echo "$out" | bytes $LOWEND 1 | md5sum); m2=$(echo "$out" | bytes $LOWEND 2 | md5sum)
check "a teleported guard leaves the memory past the buffers untouched" "[ \"$m1\" = \"$m2\" ]"

# 10. Geodes: one collected (250); the last makes the exit ladder grow;
#     out at the top: the level done (1500 more, a life), level 2.
EXC=$(python3 tools/levelgen.py 1 | awk 'NR>1 { i = index($0, "X"); if (i) { print i - 1; exit } }')
out=$(run poke:$(cell 13 29),05 poke:$GL,01 poke:$JF,04 frames:9 poke:$JF,00 frames:4 mem:$SC,3 mem:$GL,1 frames:100 mem:$ES,1 \
      poke:$HR,00$(printf '%02X' $EXC) frames:3 mem:$SC,3 mem:$LI,1 frames:150 mem:$LV,1)
check "a geode (score $(echo "$out" | bytes $SC 1)), the last: the exit grows (state $(echo "$out" | byte $ES))" \
      "[ $(echo "$out" | bytes $SC 1) = 000250 ] && [ $(echo "$out" | byte $GL) -eq 0 ] && [ $(echo "$out" | byte $ES) -eq 2 ]"
check "out at the top: score $(echo "$out" | bytes $SC 2), lives $(echo "$out" | byte $LI), level $(echo "$out" | byte $LV)" \
      "[ $(echo "$out" | bytes $SC 2) = 001750 ] && [ $(echo "$out" | byte $LI) -eq 4 ] && [ $(echo "$out" | byte $LV) -eq 2 ]"

# 11. The last life lost: GAME OVER, then a new game at level 1.
out=$(run poke:$SC,001234 poke:$LV,05 poke:$LI,01 poke:$HD,01 frames:450 mem:$LI,1 mem:$LV,1 mem:$SC,3)
check "game over: a new game (lives $(echo "$out" | byte $LI), level $(echo "$out" | byte $LV), score $(echo "$out" | bytes $SC))" \
      "[ $(echo "$out" | byte $LI) -eq 3 ] && [ $(echo "$out" | byte $LV) -eq 1 ] && [ $(echo "$out" | bytes $SC) = 000000 ]"

# 12. Speed: on levels with four guards chasing, the game loop keeps up with
#     the frames (measured after the level is drawn).
for L in 60 100 150; do
    out=$(run poke:$DS,01 poke:$LV,$(printf '%02X' $L) poke:$HD,01 frames:130 mem:$DL,1 frames:200 mem:$DL,1 mem:$NGUARD,1)
    l1=$(echo "$out" | byte $DL 1); l2=$(echo "$out" | byte $DL 2)
    loops=$(( (l2 - l1 + 256) % 256 ))
    check "speed, level $L ($(echo "$out" | byte $NGUARD) guards): $loops game loops in 200 frames" "[ $loops -ge 196 ]"
done

# 13. BREAK gives up the level: a life lost, the level as it started (the
#     geode collected is back).
out=$(run mem:$GL,1 poke:$(cell 13 29),05 poke:$JF,04 frames:9 poke:$JF,00 frames:4 mem:$GL,1 break:3 frames:200 mem:$GL,1 mem:$LI,1 mem:$(cell 13 29),1)
check "BREAK: geodes $(echo "$out" | byte $GL 1) -> $(echo "$out" | byte $GL 2) -> $(echo "$out" | byte $GL 3), lives $(echo "$out" | byte $LI)" \
      "[ $(echo "$out" | byte $GL 3) -eq $(echo "$out" | byte $GL 1) ] && [ $(echo "$out" | byte $LI) -eq 2 ] && [ $(echo "$out" | byte $(cell 13 29)) -eq 0 ]"

# 14. The guards are slower on the first levels, faster later.
GW=$(sym gu_walk)
w1=$(run mem:$GW,1 | byte $GW); w2=$(run poke:$LV,96 poke:$HD,01 frames:150 mem:$GW,1 | byte $GW)
check "guard speed: $w1 frames a cell on level 1, $w2 on level 150" "[ $w1 -gt $w2 ]"

# 15. A guard doesn't cross a hole that's closing: he waits at its edge
#     until it has closed, then walks over it (he used to fall in and,
#     if it closed meanwhile, on through the floor).  The scene: a hole
#     filling at (14, 28), the guard at (13, 27), the hero at (13, 30).
HOLES=$(sym holes)
samples=""; for i in $(seq 1 16); do samples="$samples frames:5 mem:$G0R,2"; done
out=$(run poke:$DS,01 poke:$JF,04 frames:2 poke:$JF,08 frames:2 poke:$JF,00 frames:20 \
      poke:$HOLES,0E1C030018 poke:$(cell 14 28),0C poke:$GUARDS,6CA8 poke:$G0R,0D1B0000000000 $samples)
pos=$(echo "$out" | grep "^mem $G0R" | cut -d: -f2 | tr -d ' ' | tr '\n' ' ')
first=$(echo "$out" | grep "^mem $G0R" | head -4 | cut -d: -f2 | tr -d ' ' | sort -u | tr '\n' ' ')
fell=$(echo "$out" | grep "^mem $G0R" | cut -d: -f2 | awk '$1!="0D"' | wc -l)
check "a guard waits at a closing hole (first $first), never falls in ($fell below row 13), then crosses ($(echo "$out" | bytes $G0R 16))" \
      "[ \"$first\" = '0D1B ' ] && [ $fell -eq 0 ] && [ $(echo "$out" | bytes $G0R 16) != 0D1B ]"

# 16. A guard on a cable hangs from it hand over hand (its own poses).
HH0=$(sym guard_h0_hr); HH1=$(sym guard_h1_hr); GSPR=$(off $GUARDS 4)
out=$(run poke:$DS,01 poke:$JF,04 frames:2 poke:$JF,08 frames:2 poke:$JF,00 frames:4 \
      poke:$(cell 13 18),040404040404040404 poke:$GUARDS,48A8 poke:$G0R,0D120000000000 frames:30 mem:$GSPR,2 frames:7 mem:$GSPR,2)
p1=$(echo "$out" | bytes $GSPR 1); p2=$(echo "$out" | bytes $GSPR 2)
check "a guard on a cable hangs from it (poses $p1, $p2: guard_h0 $HH0, guard_h1 $HH1)" \
      "{ [ $p1 = $HH0 ] || [ $p1 = $HH1 ]; } && { [ $p2 = $HH0 ] || [ $p2 = $HH1 ]; }"

# 17. The release build assembles (no debug hooks).
make --no-print-directory -s DEBUG=0 build/geode.bin > $D/rel.log 2>&1; st=$?
check "the release build (DEBUG=0) assembles" "[ $st -eq 0 ]"
make --no-print-directory -s -B build/geode.bin > /dev/null 2>&1      # (back to the debug build)

rm -rf $D
echo "$pass passed, $fail failed"
[ $fail -eq 0 ]
