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
# load the game the way a player does; level 1 is drawn ~60 frames after SPACE
# (the title and its jingle, then SPACE)
run() { $H $R/MC10.BIN mcx32sd:$R/mcx32sd_flash.bin 8k sd:$SD frames:200 'type:RUNM"GEODE"\n' frames:240 'type: ' frames:60 "$@"; }
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

# 0. Every level is playable and fair as the game loads it: each geode can be
#    reached and left (digging where needed), and the exit climbed; and
#    neither the start nor a geode lies down a long stretch of floor that
#    can't be dug before any way off it (levelgen.py fairness()).
r=$(python3 tools/levelgen.py --verify build/LEVELS.DAT 2>&1); rc=$?
check "every level in LEVELS.DAT playable and fair as loaded${r:+: $r}" "[ $rc -eq 0 ]"

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

# 4b. The hidden level select: MC10 typed on the title, then a level (096)
#     starts the game there, a game that won't count for the best score;
#     an ordinary SPACE starts at level 1.
out=$($H $R/MC10.BIN mcx32sd:$R/mcx32sd_flash.bin 8k sd:$SD frames:200 'type:RUNM"GEODE"\n' frames:240 'type:MC10096' frames:120 mem:$LV,1 mem:$(sym chosen),1)
check "MC10 096 on the title: level $(echo "$out" | byte $LV 1) (chosen $(echo "$out" | byte $(sym chosen) 1))" \
      "[ $(echo "$out" | byte $LV 1) = 96 ] && [ $(echo "$out" | byte $(sym chosen) 1) != 0 ]"
out=$(run frames:30 mem:$LV,1 mem:$(sym chosen),1)
check "SPACE on the title: level $(echo "$out" | byte $LV 1) (chosen $(echo "$out" | byte $(sym chosen) 1))" \
      "[ $(echo "$out" | byte $LV 1) = 1 ] && [ $(echo "$out" | byte $(sym chosen) 1) = 0 ]"

# 5b. A quick SPACE tap in the middle of a step isn't lost: the step is
#     done at once and it digs from the next cell (left, the way he
#     walked), now, not when he'd have got there.
out=$(run poke:$JF,04 frames:3 poke:$JF,10 frames:1 poke:$JF,00 frames:2 mem:$HR,2 mem:$(cell 14 28),1)
check "a SPACE tap mid-step digs on arrival (at $(echo "$out" | bytes $HR 1): cell $(echo "$out" | bytes $(cell 14 28) 1))" \
      "[ $(echo "$out" | bytes $HR 1) = 0D1D ] && echo \" 09 0A \" | grep -q \" $(echo "$out" | bytes $(cell 14 28) 1) \""

# 5c. No digging under a geode (as under a ladder).
out=$(run poke:$(cell 13 29),05 poke:$JF,14 frames:1 poke:$JF,00 frames:20 mem:$(cell 14 29),1)
check "no dig under a geode (brick $(echo "$out" | bytes $(cell 14 29) 1))" "[ $(echo "$out" | bytes $(cell 14 29) 1) = 01 ]"

# 5e. The hole goes the way he faced when SPACE was pressed: tapped
#     walking left, then right held before he arrives: still left.
out=$(run poke:$JF,04 frames:3 poke:$JF,10 frames:1 poke:$JF,08 frames:5 poke:$JF,00 frames:10 mem:$(cell 14 28),1 mem:$(cell 14 30),1)
check "dig way from the press (left $(echo "$out" | bytes $(cell 14 28) 1), right $(echo "$out" | bytes $(cell 14 30) 1))" \
      "echo \" 09 0A 00 \" | grep -q \" $(echo "$out" | bytes $(cell 14 28) 1) \" && [ $(echo "$out" | bytes $(cell 14 30) 1) = 01 ]"

# 5d. One press, one hole: SPACE held digs once (the way he faces, right),
#     and pressing A with it still held walks him left, no second hole.
out=$(run poke:$JF,10 frames:30 poke:$JF,14 frames:6 poke:$JF,10 frames:20 mem:$(cell 14 31),1 mem:$(cell 14 29),1 mem:$(cell 14 28),1 mem:$HR,2)
check "SPACE held: one hole ($(echo "$out" | bytes $(cell 14 31) 1)), none as he runs ($(echo "$out" | bytes $(cell 14 29) 1) $(echo "$out" | bytes $(cell 14 28) 1)), at $(echo "$out" | bytes $HR 1)" \
      "[ $(echo "$out" | bytes $(cell 14 31) 1) = 00 ] && [ $(echo "$out" | bytes $(cell 14 29) 1) = 01 ] && [ $(echo "$out" | bytes $(cell 14 28) 1) = 01 ] && [ $(echo "$out" | bytes $HR 1) != 0D1E ]"

# 5f. Walking onto a ladder's foot and stopping, he stands (not on the
#     ladder) and can dig beside it; UP still climbs.
HON=$(sym h_on)
out=$(run poke:$JF,04 frames:24 poke:$JF,00 frames:4 mem:$HR,2 mem:$HON,1 poke:$JF,14 frames:1 poke:$JF,00 frames:4 mem:$(cell 14 26),1)
check "at a ladder's foot ($(echo "$out" | bytes $HR 1)): standing (on $(echo "$out" | bytes $HON 1)), digs beside it ($(echo "$out" | bytes $(cell 14 26) 1))" \
      "[ $(echo "$out" | bytes $HR 1) = 0D1B ] && [ $(echo "$out" | bytes $HON 1) = 00 ] && [ $(echo "$out" | bytes $(cell 14 26) 1) = 09 ]"

# 5g. Where a tall ladder passes a floor (column 17, row 7 of level 1:
#     floor either side below), he stands and can dig beside it; UP held
#     climbs on past it, DOWN held climbs down past it to the bottom.
out=$(run poke:$DS,01 poke:$HR,0711 poke:$HERO,4460 frames:4 mem:$HON,1 poke:$JF,18 frames:1 poke:$JF,00 frames:4 mem:$(cell 8 18),1 \
      poke:$JF,01 frames:44 mem:$HR,2 poke:$JF,02 frames:70 mem:$HR,2 poke:$JF,00)
check "a ladder through a floor: stands (on $(echo "$out" | bytes $HON 1)), digs beside ($(echo "$out" | bytes $(cell 8 18) 1)), up past it ($(echo "$out" | bytes $HR 1)), down past it ($(echo "$out" | bytes $HR 2))" \
      "[ $(echo "$out" | bytes $HON 1) = 00 ] && [ $(echo "$out" | bytes $(cell 8 18) 1) = 09 ] && [ $(echo "$out" | bytes $HR 1) = 0411 ] && [ $(echo "$out" | bytes $HR 2) = 0A11 ]"

# 5h. A double dig into a vault (built here under floor 8, columns 2-4: a
#     second brick layer, stone walls, a geode inside): dig the far hole,
#     then the near one, drop in, dig under the far one, drop through into
#     the vault, take the geode, dig out through its floor, land below.
VAULT="poke:$(cell 9 1),02010101 poke:$(cell 9 5),02 poke:$(cell 10 1),02 poke:$(cell 10 5),02 poke:$(cell 10 4),05"
out=$(run poke:$DS,01 $VAULT poke:$HR,0702 poke:$HERO,0860 frames:4 mem:$GL,1 \
      poke:$JF,18 frames:1 poke:$JF,00 frames:14 poke:$JF,04 frames:2 poke:$JF,00 frames:10 \
      poke:$JF,18 frames:1 poke:$JF,00 frames:14 poke:$JF,08 frames:2 poke:$JF,00 frames:24 \
      poke:$JF,18 frames:1 poke:$JF,00 frames:14 poke:$JF,08 frames:2 poke:$JF,00 frames:40 mem:$HR,2 \
      poke:$JF,08 frames:2 poke:$JF,00 frames:12 mem:$GL,1 \
      poke:$JF,14 frames:1 poke:$JF,00 frames:14 poke:$JF,04 frames:2 poke:$JF,00 frames:60 mem:$HR,2 mem:$LI,1)
check "a double dig into a vault (in at $(echo "$out" | bytes $HR 1), geodes $(echo "$out" | byte $GL 1) -> $(echo "$out" | byte $GL 2), out at $(echo "$out" | bytes $HR 2), lives $(echo "$out" | byte $LI))" \
      "[ $(echo "$out" | bytes $HR 1) = 0A03 ] && [ $(echo "$out" | byte $GL 2) -eq $(( $(echo "$out" | byte $GL 1) - 1 )) ] && [ $(echo "$out" | bytes $HR 2) = 0D03 ] && [ $(echo "$out" | byte $LI) -eq 3 ]"

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
      poke:$HR,00$(printf '%02X' $EXC) frames:120 mem:$SC,3 frames:150 mem:$SC,3 mem:$LI,1 mem:$LV,1)
check "a geode (score $(echo "$out" | bytes $SC 1)), the last: the exit grows (state $(echo "$out" | byte $ES))" \
      "[ $(echo "$out" | bytes $SC 1) = 000250 ] && [ $(echo "$out" | byte $GL) -eq 0 ] && [ $(echo "$out" | byte $ES) -eq 2 ]"
mid=$(echo "$out" | bytes $SC 2); tens=0; case $mid in *0) tens=1 ;; esac
check "out at the top: the bonus counts up by tens (score $mid partway)" \
      "[ $mid -gt 250 ] && [ $mid -lt 1750 ] && [ $tens -eq 1 ]"
check "the count done: score $(echo "$out" | bytes $SC 3), lives $(echo "$out" | byte $LI), level $(echo "$out" | byte $LV)" \
      "[ $(echo "$out" | bytes $SC 3) = 001750 ] && [ $(echo "$out" | byte $LI) -eq 4 ] && [ $(echo "$out" | byte $LV) -eq 2 ]"

# 10a. The count shows on screen in every column, even from a score not
#      ending in 0 (a trapped guard is 75): the thousands digit changes
#      during the count, not only at its end.
out=$(run poke:$SC,000075 poke:$(cell 13 29),05 poke:$GL,01 poke:$JF,04 frames:9 poke:$JF,00 frames:100 \
      poke:$HR,00$(printf '%02X' $EXC) frames:3 mem:4000,544 frames:117 mem:$SC,3 mem:4000,544)
thou() { echo "$out" | grep "^mem 4000" | sed -n "$1p" | cut -d: -f2 | awk '{for (r = 0; r < 17; r++) printf "%s", $(r * 32 + 9)}'; }
check "the count on screen: thousands digit redrawn partway (score $(echo "$out" | bytes $SC 1))" \
      "[ \"$(thou 1)\" != \"$(thou 2)\" ] && [ $(echo "$out" | bytes $SC 1 | cut -c3) = 1 ]"

# 10b. The level bonus is only for climbing out: every geode collected and
#      then dying before the exit gives none (the level starts over).
out=$(run poke:$(cell 13 29),05 poke:$GL,01 poke:$JF,04 frames:9 poke:$JF,00 frames:100 mem:$SC,3 poke:$HD,01 frames:150 mem:$SC,3 mem:$LV,1)
check "no bonus without climbing out: score $(echo "$out" | bytes $SC 1) after the last geode, $(echo "$out" | bytes $SC 2) after dying, level $(echo "$out" | byte $LV)" \
      "[ $(echo "$out" | bytes $SC 1) = 000250 ] && [ $(echo "$out" | bytes $SC 2) = 000250 ] && [ $(echo "$out" | byte $LV) -eq 1 ]"

# 11. The last life lost: GAME OVER, the title (waiting, the score now the
#     best), then SPACE: a new game at level 1.
HI=$(sym hiscore)
out=$(run poke:$SC,001234 poke:$LV,05 poke:$LI,01 poke:$HD,01 frames:600 mem:$LV,1 mem:$HI,3 'type: ' frames:60 mem:$LI,1 mem:$LV,1 mem:$SC,3)
check "game over: the title (still level $(echo "$out" | byte $LV 1), best $(echo "$out" | bytes $HI)), then a new game (lives $(echo "$out" | byte $LI), level $(echo "$out" | byte $LV 2), score $(echo "$out" | bytes $SC))" \
      "[ $(echo "$out" | byte $LV 1) -eq 5 ] && [ $(echo "$out" | bytes $HI) = 001234 ] && [ $(echo "$out" | byte $LI) -eq 3 ] && [ $(echo "$out" | byte $LV 2) -eq 1 ] && [ $(echo "$out" | bytes $SC) = 000000 ]"

# 12. Speed: on levels with four guards chasing, the game loop keeps up with
#     the frames (measured after the level is drawn).
for L in 60 100 150; do
    out=$(run poke:$DS,01 poke:$LV,$(printf '%02X' $L) poke:$HD,01 frames:130 mem:$DL,1 frames:200 mem:$DL,1 mem:$NGUARD,1)
    l1=$(echo "$out" | byte $DL 1); l2=$(echo "$out" | byte $DL 2)
    loops=$(( (l2 - l1 + 256) % 256 ))
    check "speed, level $L ($(echo "$out" | byte $NGUARD) guards): $loops game loops in 200 frames" "[ $loops -ge 199 ]"
done

# 12b. Test builds: N then three digits goes to that level (041: 41); a
#      number out of range (200) is ignored.
out=$(run 'type:N041' frames:120 mem:$LV,1 'type:N200' frames:60 mem:$LV,1)
check "N with a level number: 041 -> $(echo "$out" | byte $LV 1), then 200 ignored ($(echo "$out" | byte $LV 2))" \
      "[ $(echo "$out" | byte $LV 1) -eq 41 ] && [ $(echo "$out" | byte $LV 2) -eq 41 ]"

# 12a. Speed with four guards milling about, unable to reach the hero (on
#      level 53 at row 4, column 16, where four guards thinking in the same
#      frame used to miss frames): at most one frame missed in 240.
out=$(run poke:$DS,01 'type:N053' frames:120 poke:$JF,04 frames:2 poke:$JF,00 poke:$HR,0410 poke:$HERO,403C frames:200 mem:$DL,1 frames:240 mem:$DL,1)
l1=$(echo "$out" | byte $DL 1); l2=$(echo "$out" | byte $DL 2); loops=$(( (l2 - l1 + 256) % 256 ))
check "speed, guards milling on level 53: $loops game loops in 240 frames" "[ $loops -ge 239 ]"

# 12c. Speed with the hero walking back and forth and four guards chasing
#      (level 100, hero redrawn most frames): no frame missed in 240.
out=$(run poke:$DS,01 'type:N100' frames:120 poke:$JF,04 frames:60 mem:$DL,1 poke:$JF,08 frames:60 poke:$JF,04 frames:60 poke:$JF,08 frames:60 poke:$JF,04 frames:60 mem:$DL,1 mem:$NGUARD,1)
l1=$(echo "$out" | byte $DL 1); l2=$(echo "$out" | byte $DL 2); loops=$(( (l2 - l1 + 256) % 256 ))
check "speed, hero walking with $(echo "$out" | byte $NGUARD) guards on level 100: $loops game loops in 240 frames" "[ $loops -ge 240 ]"

# 12d. The frame tick never stalls under sound: 80 digs, the guards about
#      (the dig noise:
#      ~1,800 speaker events a second), the game's ticks counted against
#      the frames that pass (an interrupt set for a time already past used
#      to wait for the counter to come round: ~4 ticks lost each time).
FC=$(sym frame_count); digs=""
for i in $(seq 1 40); do digs="$digs poke:$JF,14 frames:1 poke:$JF,00 frames:16 poke:$JF,18 frames:1 poke:$JF,00 frames:16"; done
out=$(run poke:$DS,01 poke:$JF,04 frames:2 poke:$JF,00 frames:300 mem:$FC,1 $digs mem:$FC,1)
t1=$(echo "$out" | byte $FC 1); t2=$(echo "$out" | byte $FC 2); ticks=$(( (t2 - t1 + 256) % 256 )); want=$(( (40 * 34) % 256 ))
check "frame ticks under the dig noise: $ticks counted, $want due (mod 256)" "[ $ticks -eq $want ]"

# 13. BREAK gives up the level: a life lost, the level as it started (the
#     geode collected is back).
out=$(run mem:$GL,1 poke:$(cell 13 29),05 poke:$JF,04 frames:9 poke:$JF,00 frames:4 mem:$GL,1 break:3 frames:200 mem:$GL,1 mem:$LI,1 mem:$(cell 13 29),1)
check "BREAK: geodes $(echo "$out" | byte $GL 1) -> $(echo "$out" | byte $GL 2) -> $(echo "$out" | byte $GL 3), lives $(echo "$out" | byte $LI)" \
      "[ $(echo "$out" | byte $GL 3) -eq $(echo "$out" | byte $GL 1) ] && [ $(echo "$out" | byte $LI) -eq 2 ] && [ $(echo "$out" | byte $(cell 13 29)) -eq 0 ]"

# 14. The guards keep one pace on every level (14 frames a cell).
GW=$(sym gu_walk)
w1=$(run mem:$GW,1 | byte $GW); w2=$(run poke:$LV,96 poke:$HD,01 frames:150 mem:$GW,1 | byte $GW)
check "guard speed: $w1 frames a cell on level 1, $w2 on level 150 (one pace)" "[ $w1 -eq 14 ] && [ $w2 -eq 14 ]"

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

# 16b. A trapped guard kills too, touched from beside: a guard trapped in
#      the bottom floor at column 28, the hero digs the hole beside it
#      (column 29) and drops in: caught (the owner: he passed through him).
#      But a ladder past a trapped guard is safe: one trapped beside level
#      1's ladder at column 27 where it passes the floor (row 11), the hero
#      climbs past him.
out=$(run poke:$GUARDS,70B470B4 poke:$(off $GUARDS 8),0E1C00000000 poke:$G0ST,01C8 poke:$(cell 14 28),00 frames:4 poke:$JF,14 frames:1 poke:$JF,00 frames:24 poke:$JF,04 frames:12 poke:$JF,00 frames:240 mem:$LI,1)
check "dropping into the hole beside a trapped guard: caught (lives $(echo "$out" | byte $LI 1))" "[ $(echo "$out" | byte $LI 1) = 2 ]"
out=$(run poke:$GUARDS,70907090 poke:$(off $GUARDS 8),0B1C00000000 poke:$G0ST,01C8 poke:$(cell 11 28),00 poke:$JF,04 frames:24 poke:$JF,01 frames:40 poke:$JF,00 frames:30 mem:$HR,2 mem:$LI,1)
check "climbing a ladder past a trapped guard: safe (at $(echo "$out" | bytes $HR 1), lives $(echo "$out" | byte $LI 1))" "[ $(echo "$out" | bytes $HR 1) = 0A1B ] && [ $(echo "$out" | byte $LI 1) = 3 ]"

# 17. The hero can stand on a guard's head (a guard at (13, 20), the hero
#     put just above him), walk off unharmed, and dies pressing down.
HEAD="poke:$GUARDS,50A8 poke:$G0R,0D140000000000 poke:$HERO,509C poke:$HR,0C14"
out=$(run $HEAD frames:40 mem:$HR,2 mem:$LI,1 poke:$JF,08 frames:40 poke:$JF,00 frames:30 mem:$HR,2 mem:$LI,1)
check "on a guard's head: stands ($(echo "$out" | bytes $HR 1)), walks off and down ($(echo "$out" | bytes $HR 2)), unharmed (lives $(echo "$out" | byte $LI 2))" \
      "[ $(echo "$out" | bytes $HR 1) = 0C14 ] && [ $(echo "$out" | byte $LI 1) -eq 3 ] && [ $(echo "$out" | bytes $HR 2 | cut -c1-2) = 0D ] && [ $(echo "$out" | byte $LI 2) -eq 3 ]"
out=$(run $HEAD frames:40 poke:$JF,02 frames:4 poke:$JF,00 frames:150 mem:$LI,1)
check "pressing down on a guard's head: caught (lives $(echo "$out" | byte $LI))" "[ $(echo "$out" | byte $LI) -eq 2 ]"

# 18. Dropping past a guard on the ladder beside him is safe: the guard
#     doesn't step out into a falling hero (he did, seeing him "on his
#     row" for a moment).  The scene, on level 1: the floor under the hero
#     at (10, 24) opened, a ladder at column 25 (rows 11-13) with a guard
#     on it at (11, 25); the hero falls to (13, 24).
FALL="poke:$(cell 11 24),00 poke:$(cell 11 25),03 poke:$(cell 12 25),03 poke:$(cell 13 25),03 poke:$GUARDS,6490 poke:$G0R,0B190000000000 poke:$HERO,6084 poke:$HR,0A18"
samples=""; for i in $(seq 1 10); do samples="$samples frames:4 mem:$HR,2 mem:$LI,1"; done
out=$(run $FALL $samples)
rows=$(echo "$out" | grep "^mem $HR" | cut -d: -f2 | tr -d ' ' | tr '\n' ' ')
lost=$(echo "$out" | grep "^mem $LI" | awk '$3!="03"' | wc -l)
check "dropping past a guard on the next ladder: safe (cells $rows, lives lost $lost)" \
      "[ $lost -eq 0 ] && [ $(echo "$out" | bytes $HR 10) = 0D18 ]"

# 19. The release build assembles (no debug hooks).
make --no-print-directory -s DEBUG=0 build/geode.bin > $D/rel.log 2>&1; st=$?
check "the release build (DEBUG=0) assembles" "[ $st -eq 0 ]"
make --no-print-directory -s -B build/geode.bin > /dev/null 2>&1      # (back to the debug build)

rm -rf $D
echo "$pass passed, $fail failed"
[ $fail -eq 0 ]
