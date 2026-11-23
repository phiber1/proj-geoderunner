; geode.asm: Geode Runner, a single-screen digging platformer for the
; MC-10 (8K RAM mod + MCX32-SD), in CG6 on a blue background.
;
; So far: a level is read from LEVELS.DAT on the SD card (tools/levelgen.py
; makes it: a 16-byte header, then 240 bytes a level, 4 bits a cell) and
; drawn, with the guards at their starting places; the hero runs, climbs,
; hangs and falls (W A S Z or the arrow keys), digs (SPACE, with A or S
; for a side) and collects the geodes (250 each); the last one makes the
; exit ladder grow, and climbing off the top finishes the level (1500 and
; a life).  Three lives, one more for each level finished.  The guards
; (guards.inc) chase him, fall into his holes (75), get buried (75) and
; come back at the top.  BREAK gives up the level (a life lost, the level
; as it started).  Debug builds: N shows the next level.

#define GFX_MODE GFX_CG6
#define GFX_BG CG_BLUE
#include "layout.inc"

BIOS_SEEK       equ     8               ; MCX BIOS 'P': set the file position
                                        ; (32 bits: PB_BUF high, PB_LEN low)
LV_FILE         equ     1               ; the file number LEVELS.DAT uses
NLEVELS         equ     150
LD_FANFARE      equ     40              ; level done: frames for the fanfare,
LD_STEPS        equ     150             ; ... the bonus count-up's steps (of 10),
LD_BOP          equ     4               ; ... frames between its bops,
LD_AFTER        equ     45              ; ... frames before the next level
LV_COLS         equ     32
LV_ROWS         equ     15
LV_CELLS        equ     LV_COLS*LV_ROWS
LV_RECORD       equ     LV_CELLS/2      ; bytes a level in the file
LV_HEADER       equ     16
MAX_GUARDS      equ     4

; actor records and the shadow buffer (draw.inc)
A_X             equ     0               ; place
A_Y             equ     1
A_OX            equ     2               ; ... where last drawn
A_OY            equ     3
A_SPR           equ     4               ; pose (a sprite's draw table)
A_OSPR          equ     6               ; ... the pose last drawn
A_SIZE          equ     8
G_R             equ     8               ; a guard's record goes on (guards.inc):
G_C             equ     9               ; ... his cell,
G_T             equ     10              ; ... frames left of the move,
G_DIR           equ     11              ; ... the move,
G_FACE          equ     12              ; ... facing left (1),
G_ON            equ     13              ; ... on a ladder (1) or cable (2),
G_ST            equ     14              ; ... free or trapped,
G_TT            equ     15              ; ... frames left trapped,
G_CARRY         equ     16              ; ... carrying a geode,
G_CT            equ     17              ; ... frames left carrying it (2)
G_OUT           equ     19              ; ... just climbed out of a hole
G_ACC           equ     20              ; ... pixels owed in the move
GD_SIZE         equ     22              ; (even: copied two bytes at a time)
SH_MARGIN       equ     12              ; shadow rows above and below a patch,
SH_ROWS         equ     36              ; for actors partly outside it

; holes (holes.inc)
HOLES           equ     8               ; holes open at once, at most
O_R             equ     0               ; a hole's record: its cell,
O_C             equ     1
O_ST            equ     2               ; ... its state (0: a free record),
O_T             equ     3               ; ... frames left in the state
O_SIZE          equ     5

; cell codes, as in the level file
C_AIR           equ     0
C_BRICK         equ     1
C_STONE         equ     2
C_LADDER        equ     3
C_CABLE         equ     4
C_GEODE         equ     5
C_HERO          equ     6               ; (start places: air once read)
C_GUARD         equ     7
C_EXIT          equ     8               ; the hidden exit ladder
C_DIG1          equ     9               ; (holes.inc) brick being dug: solid
C_DIG2          equ     10
C_FILL1         equ     11              ; ... a hole filling: open
C_FILL2         equ     12

                org     LOW
lv_buf          rmb     LV_RECORD       ; a level as read
lv_map          rmb     LV_CELLS        ; ... and unpacked, a cell a byte
shadow          rmb     (SH_ROWS+2*SH_MARGIN)*ROW_BYTES ; draw.inc: patches built here
tmap            rmb     LV_CELLS        ; ... every cell's tile, as drawn

                org     BSS
level           rmb     1               ; 1..NLEVELS
lv_pb           rmb     PB_SIZE         ; the BIOS parameter block
up_s            rmb     2               ; unpacking: from, to
up_d            rmb     2
hero_r          rmb     1               ; the hero's start cell
hero_c          rmb     1
nguard          rmb     1               ; the guards' start cells (row, col)
guard_rc        rmb     2*MAX_GUARDS
dc_r            rmb     1               ; draw_cell: the cell,
dc_c            rmb     1
dc_m            rmb     2               ; ... its map byte,
dc_t            rmb     2               ; ... its tile's bytes,
dc_s            rmb     2               ; ... its place on the screen
key_was         rmb     1
started         rmb     1               ; the hero has moved: the guards go
brk_was         rmb     1               ; BREAK was down last frame
joy_force       rmb     1               ; debug builds: nonzero = held keys (tests)
dbg_safe        rmb     1               ; ... nonzero: guards can't catch him (tests)
dbg_loops       rmb     1               ; ... main loop passes (vs frame_count)
st_n            rmb     1               ; status: digits
h_r             rmb     1               ; hero.inc: the cell he's on or moving to
h_c             rmb     1
hero_a          rmb     A_SIZE          ; ... his actor record (draw.inc)
h_x             equ     hero_a+A_X      ; ... his pixel place,
h_y             equ     hero_a+A_Y
h_spr           equ     hero_a+A_SPR    ; ... his pose
h_face          rmb     1               ; ... 0 facing right, 1 left
h_on            rmb     1               ; ... 1 on a ladder, 2 on a cable
h_t             rmb     1               ; ... frames left of the move,
h_dir           rmb     1               ; ... the move (D_*),
h_fall          rmb     1               ; ... nonzero while falling
hu_here         rmb     1               ; ... the cell he's on, the one below
hu_below        rmb     1
ca_c            rmb     1               ; cell_at
ca_p            rmb     2
guards          rmb     GD_SIZE*MAX_GUARDS ; the guards' records
gs              rmb     GD_SIZE         ; guards.inc: the one being worked on
gu_n            rmb     1
gu_p            rmb     2
gu_q            rmb     2
gu_q2           rmb     2
gd_here         rmb     1
gd_below        rmb     1
gd_goal         rmb     1
gd_want         rmb     1
gd_l            rmb     1
gd_rr           rmb     1
gd_lok          rmb     1
gd_rok          rmb     1
gd_wc           rmb     1
gd_wh           rmb     1
gd_wb           rmb     1
gd_fr           rmb     2
gd_m            rmb     2
gd_rp           rmb     2
gd_n            rmb     1
gd_hr           rmb     1
gu_walk         rmb     1               ; this level's guard speeds
gu_climb        rmb     1
seed            rmb     2
h_dig           rmb     1               ; hero.inc: frames left digging
h_dlat          rmb     1               ; ... a SPACE press remembered: frames left,
h_ddir          rmb     1               ; ... and A/S held with it
h_head          rmb     1               ; ... standing on a guard's head
h_dead          rmb     1               ; ... nonzero: a hole filled on him
hu_dc           rmb     1               ; ... the side he digs (-1, 1)
holes           rmb     HOLES*O_SIZE    ; holes.inc
ho_rc           rmb     2
ho_m            rmb     2
ho_p            rmb     2
ho_n            rmb     1
dc_tl           rmb     1               ; draw.inc
cp_a            rmb     2               ; act_update: the actor,
cp_b            rmb     2               ; ... one being drawn into the shadow,
cp_t            rmb     1
cp_t2           rmb     2
cp_c            rmb     1               ; ... the patch: its left byte,
cp_r0           rmb     1               ; ... cell rows,
cp_r1           rmb     1
cp_top          rmb     1               ; ... top row and height,
cp_n            rmb     1
cp_org          rmb     2               ; ... the shadow's origin,
cp_rr           rmb     1
cp_k            rmb     1
cp_rowd         rmb     2
cp_g            rmb     1
cp_gp           rmb     2
cp_src          rmb     2               ; ... copying it to the screen
cp_dst          rmb     2
cp_sx           rmb     1
cp_w            rmb     1               ; ... its width in bytes
cp_tp           rmb     2               ; ... its tiles' row in tmap
cp_y0           rmb     1               ; ... the rows the actor covers
ae_c0           rmb     1               ; act_erase
ae_c1           rmb     1
ae_c            rmb     1
ae_r            rmb     1
ae_r1           rmb     1
cp_y1           rmb     1
score           rmb     3               ; BCD
lives           rmb     1
g_left          rmb     1               ; geodes still to collect
ex_col          rmb     1               ; the exit ladder's column,
ex_bot          rmb     1               ; ... its bottom row,
ex_state        rmb     1               ; ... 0 hidden, 1 growing, 2 there
ex_row          rmb     1               ; ... growing: the next row,
ex_t            rmb     1               ; ... frames to it
w_n             rmb     1               ; wait
ld_n            rmb     1               ; the level bonus count-up: steps,
ld_t            rmb     1               ; ... frames to the next bop

                org     CODE
start:
                sei
                lds     #STACK_TOP
                jsr     gfx_init
                clr     key_was
                clr     joy_force
                clr     dbg_safe
                jsr     frame_init
new_game:
                ldaa    #1
                staa    level
                ldaa    #3
                staa    lives
                clr     score
                clr     score+1
                clr     score+2
new_level:
                jsr     lv_load         ; the level from the SD card
                bcc     nl_f2
                jmp     no_file
nl_f2:
                jsr     lv_actors
                jsr     lv_scan
                jsr     guards_speed
                jsr     holes_init
                jsr     gfx_cls
                jsr     lv_draw
                jsr     status_draw
                jsr     hero_init
                jsr     actors_draw
                clr     started         ; (the guards wait for his first move)
loop:
                jsr     frame_wait
                if      DEBUG
                inc     dbg_loops
                endif
                jsr     snd_frame
                jsr     kbd_read
                if      DEBUG           ; (tests poke joy_force to hold keys)
                ldaa    joy_force
                beq     dbg_f1
                staa    joy
dbg_f1:
                endif
                jsr     hero_update
                jsr     hole_update
                jsr     exit_update
                jsr     hero_pose
                ldx     #hero_a
                jsr     act_update
                tst     started         ; the guards: once he's moved
                bne     lp_g1
                tst     h_t
                bne     lp_g0
                tst     h_dig
                beq     lp_g2
lp_g0:          inc     started
lp_g1:          jsr     guards_update
lp_g2:
                if      DEBUG
                tst     dbg_safe
                bne     lp_f0
                endif
                jsr     caught          ; a guard got him
                beq     lp_f0
                inc     h_dead
lp_f0:          ldaa    #$FF-$04        ; BREAK (column 2, row 6: port 2's
                staa    P1DAT           ; bit 1): give up the level, a life
                ldaa    P2DAT           ; lost, everything as it started
                ldab    #$FF
                stab    P1DAT
                coma
                anda    #$02
                tab
                eora    brk_was         ; (on the press)
                stab    brk_was
                anda    brk_was
                beq     lp_f00
                inc     h_dead
lp_f00:          tst     h_dead          ; (or a hole filled on him)
                beq     lp_f01
                jmp     died
lp_f01:         ldaa    ex_state        ; out at the top: the level is done
                cmpa    #2
                bne     lp_f1
                tst     h_r
                bne     lp_f1
                tst     h_t
                beq     level_done
lp_f1:
                if      DEBUG
                ldaa    #$FF-$40        ; N (column 6, row 1): the next level
                staa    P1DAT
                ldaa    KBD
                ldab    #$FF
                stab    P1DAT
                coma
                anda    #$02
                tab
                eora    key_was         ; (on the press)
                stab    key_was
                anda    key_was
                bne     lp_n1
                jmp     loop
lp_n1:          bra     next_level
                else
                jmp     loop
                endif

level_done:
                ldx     #fx_clear       ; the fanfare,
                ldaa    #8
                jsr     snd_play
                ldaa    #LD_FANFARE
                jsr     wait
                ldaa    #LD_STEPS       ; then 1500 points counted up by
                staa    ld_n            ; tens, a bop every LD_BOP frames
                ldaa    #1
                staa    ld_t
lb_b1:          jsr     frame_wait
                jsr     snd_frame
                dec     ld_t
                bne     lb_f1
                ldaa    #LD_BOP
                staa    ld_t
                ldx     #fx_bop
                ldaa    #8
                jsr     snd_play
lb_f1:          ldd     #$0010
                jsr     score_add
                ldaa    score+2         ; (a carry: all six digits, else
                bne     lb_f2           ; just the last two: in a frame)
                jsr     status_score
                bra     lb_f3
lb_f2:          ldaa    #COLOR_BYTE(CG_YELLOW)
                staa    txt_col
                ldx     #TXT_AT(1,10)
                ldaa    score+2
                jsr     sp_byte
lb_f3:
                dec     ld_n
                bne     lb_b1
                ldaa    lives           ; and a life (9 at most)
                cmpa    #9
                bcc     ld2_f1
                inc     lives
ld2_f1:         jsr     status_draw
                ldx     #fx_gem
                ldaa    #8
                jsr     snd_play
                ldaa    #LD_AFTER
                jsr     wait
next_level:
                ldaa    level
                inca
                cmpa    #NLEVELS+1
                bcc     congrats
                staa    level
                jmp     new_level

died:
                ldx     #fx_die
                ldaa    #9
                jsr     snd_play
                ldaa    #90             ; a moment
                jsr     wait
                dec     lives
                bne     dd_f1
                jsr     status_draw     ; the last one: game over
                ldaa    #COLOR_BYTE(CG_RED)
                staa    txt_col
                ldx     #TXT_AT(86,11)
                ldd     #s_over
                jsr     txt_str2
                ldaa    #240
                jsr     wait
                jmp     new_game
dd_f1:          jmp     new_level       ; the level again

; every level done: a congratulation (for now), then a new game
congrats:
                jsr     gfx_cls
                ldaa    #COLOR_BYTE(CG_YELLOW)
                staa    txt_col
                ldx     #TXT_AT(60,8)
                ldd     #s_congr1
                jsr     txt_str2
                ldx     #TXT_AT(84,5)
                ldd     #s_congr2
                jsr     txt_str2
                ldx     #TXT_AT(108,9)
                ldd     #s_congr3
                jsr     txt_str2
                ldx     #TXT_AT(108,19)
                jsr     score_put
                ldaa    #255
                jsr     wait
                ldaa    #255
                jsr     wait
                jmp     new_game

; wait: A frames (the sound going on)
wait:
                staa    w_n
wt_b1:          jsr     frame_wait
                jsr     snd_frame
                dec     w_n
                bne     wt_b1
                rts

; ---------------------------------------------------------------- geodes, exit

; lv_scan: count the geodes; find the exit ladder (its column, its bottom)
lv_scan:
                clr     g_left
                clr     ex_state
                clr     ex_bot
                clr     dc_r
                ldx     #lv_map
ls_b1:          clr     dc_c
ls_b2:          ldaa    0,x
                cmpa    #C_GEODE
                bne     ls_f1
                inc     g_left
ls_f1:          cmpa    #C_EXIT
                bne     ls_f2
                ldd     dc_r            ; (rows go down: the last is the bottom)
                staa    ex_bot
                stab    ex_col
ls_f2:          inx
                inc     dc_c
                ldaa    dc_c
                cmpa    #LV_COLS
                bne     ls_b2
                inc     dc_r
                ldaa    dc_r
                cmpa    #LV_ROWS
                bne     ls_b1
                rts

; geode_take: the hero is on a geode's cell (h_r, h_c): collect it
geode_take:
                ldaa    h_r
                ldab    #LV_COLS
                mul
                addb    h_c
                adca    #0
                addd    #lv_map
                std     ho_m
                ldx     ho_m
                clr     0,x             ; (air)
                ldd     h_r
                jsr     draw_cell
                ldd     #0              ; (redraw him over it)
                std     hero_a+A_OSPR
                ldd     #$0250
                jsr     score_add
                jsr     status_score
                ldx     #fx_gem
                ldaa    #5
                jsr     snd_play
                dec     g_left
                bne     gt_r
                ldaa    #1              ; the last: the exit ladder grows,
                staa    ex_state        ; from its bottom up
                ldaa    ex_bot
                staa    ex_row
                ldaa    #1
                staa    ex_t
                ldx     #fx_exit
                ldaa    #6
                jsr     snd_play
gt_r:           rts

; exit_update: once a frame: the ladder growing, a rung every few frames
exit_update:
                ldaa    ex_state
                cmpa    #1
                bne     eu_r
                dec     ex_t
                bne     eu_r
                ldaa    #4
                staa    ex_t
                ldaa    ex_row          ; this cell becomes ladder
                ldab    #LV_COLS
                mul
                addb    ex_col
                adca    #0
                addd    #lv_map
                std     ho_m
                ldx     ho_m
                ldaa    #C_LADDER
                staa    0,x
                ldaa    ex_row
                ldab    ex_col
                jsr     draw_cell
                ldaa    ex_row          ; (and the one below: it may be brick
                cmpa    #LV_ROWS-1      ; drawn on brick)
                beq     eu_f1
                inca
                ldab    ex_col
                jsr     draw_cell
eu_f1:          ldd     #0
                std     hero_a+A_OSPR
                dec     ex_row
                bpl     eu_r
                ldaa    #2              ; all there
                staa    ex_state
eu_r:           rts

; score_add: D = BCD points, 4 digits (A thousands and hundreds, B tens
; and ones): add them to the score
score_add:
                psha
                tba
                adda    score+2
                daa
                staa    score+2
                pula
                adca    score+1
                daa
                staa    score+1
                ldaa    score
                adca    #0
                daa
                staa    score
                rts

no_file:
                jsr     gfx_cls
                ldaa    #COLOR_BYTE(CG_YELLOW)
                staa    txt_col
                ldx     #TXT_AT(90,6)
                ldd     #s_nofile
                jsr     txt_str
                bra     *

; ---------------------------------------------------------------- loading

; lv_load: read level `level` from LEVELS.DAT into lv_map.  Carry set if
; the file can't be read.
lv_load:
                ldaa    #LV_FILE        ; (close the handle first, as BASIC
                jsr     lv_pbinit       ; does; errors ignored)
                ldab    #BIOS_CLOSE
                jsr     lv_bios
                ldaa    #PB_IN|LV_FILE
                jsr     lv_pbinit
                ldab    #BIOS_OPEN
                jsr     lv_bios
                bcs     lv_load_r
                ldaa    level           ; seek: 16 + 240 * (level - 1)
                deca
                ldab    #LV_RECORD
                mul
                addd    #LV_HEADER
                std     lv_pb+PB_LEN
                ldd     #0
                std     lv_pb+PB_BUF
                ldaa    #LV_FILE
                staa    lv_pb+PB_MODE
                ldab    #BIOS_SEEK
                jsr     lv_bios
                bcs     lv_load_e
                ldd     #lv_buf         ; read the level's 240 bytes
                std     lv_pb+PB_BUF
                ldd     #LV_RECORD
                std     lv_pb+PB_LEN
                ldab    #BIOS_READ
                jsr     lv_bios
                bcs     lv_load_e
                ldd     lv_pb+PB_LEN    ; (all of them?)
                subd    #LV_RECORD
                bne     lv_load_e
                bsr     lv_close
                bsr     lv_unpack
                clc
lv_load_r:      rts
lv_load_e:      bsr     lv_close
                sec
                rts

lv_close:
                ldaa    #LV_FILE
                staa    lv_pb+PB_MODE
                ldab    #BIOS_CLOSE
                bra     lv_bios

lv_pbinit:                              ; zero the block; the name, A = mode
                ldx     #lv_pb
                ldab    #PB_SIZE
lv_pbinit_b1:   clr     0,x
                inx
                decb
                bne     lv_pbinit_b1
                staa    lv_pb+PB_MODE
                ldd     #s_file
                std     lv_pb+PB_NAME
                ldaa    #S_FILE_LEN
                staa    lv_pb+PB_NLEN
                rts

lv_bios:                                ; B = function: call the BIOS (SD)
                clra
                ldx     #lv_pb
                jmp     MCX_BIOS

; two cells a byte (the left one in the high nibble) -> a cell a byte
lv_unpack:
                ldx     #lv_buf
                stx     up_s
                ldx     #lv_map
                stx     up_d
lv_unpack_b1:   ldx     up_s
                ldaa    0,x
                inx
                stx     up_s
                tab
                lsra
                lsra
                lsra
                lsra
                andb    #$0F
                ldx     up_d
                staa    0,x
                stab    1,x
                inx
                inx
                stx     up_d
                cpx     #lv_map+LV_CELLS
                bne     lv_unpack_b1
                rts

; the hero's and the guards' start cells: noted, and made air
lv_actors:
                clr     nguard
                clr     dc_r
                ldx     #lv_map
la_b1:          clr     dc_c
la_b2:          ldaa    0,x
                cmpa    #C_HERO
                bne     la_f1
                ldd     dc_r            ; (dc_r, dc_c)
                std     hero_r
                clr     0,x
                bra     la_f2
la_f1:          cmpa    #C_GUARD
                bne     la_f2
                ldab    nguard
                cmpb    #MAX_GUARDS
                bcc     la_f2
                stx     dc_m
                ldx     #guard_rc
                abx
                abx
                ldd     dc_r
                std     0,x
                inc     nguard
                ldx     dc_m
                clr     0,x
la_f2:          inx
                inc     dc_c
                ldaa    dc_c
                cmpa    #LV_COLS
                bne     la_b2
                inc     dc_r
                ldaa    dc_r
                cmpa    #LV_ROWS
                bne     la_b1
                rts

; ---------------------------------------------------------------- drawing

lv_draw:
                clra
ld_b1:          clrb
ld_b2:          pshb
                psha
                jsr     draw_cell
                pula
                pulb
                incb
                cmpb    #LV_COLS
                bne     ld_b2
                inca
                cmpa    #LV_ROWS
                bne     ld_b1
                rts

; a cell code's tile (brick is worked out from its neighbours)
celltile:       fcb     T_AIR, T_BRICK, T_STONE, T_LADDER, T_CABLE, T_GEODE
                fcb     T_AIR, T_AIR, T_AIR     ; hero, guard: sprites; the exit: hidden
                fcb     T_DIG1, T_DIG2, T_DIG1, T_DIG2  ; digging, filling

; the screen address of each level row (the status line is row 0)
rowaddr:
k               set     1
                rept    LV_ROWS
                fdb     SCREEN+k*12*ROW_BYTES
k               set     k+1
                endm

status_draw:                            ; (double height, as in the mock-up)
                ldaa    #COLOR_BYTE(CG_YELLOW)
                staa    txt_col
                ldx     #TXT_AT(1,0)
                ldd     #s_status
                jsr     txt_str2
                bsr     status_score
                ldx     #TXT_AT(1,20)   ; the level: three digits
                ldaa    level
                clrb
sd_b1:          cmpa    #100
                bcs     sd_f1
                suba    #100
                incb
                bra     sd_b1
sd_f1:          staa    st_n
                tba
                adda    #'0'
                jsr     txt_char2
                ldaa    st_n
                clrb
sd_b2:          cmpa    #10
                bcs     sd_f2
                suba    #10
                incb
                bra     sd_b2
sd_f2:          staa    st_n
                tba
                adda    #'0'
                jsr     txt_char2
                ldaa    st_n
                adda    #'0'
                jsr     txt_char2
                ldx     #TXT_AT(1,31)   ; the lives
                ldaa    lives
                adda    #'0'
                jmp     txt_char2

status_score:
                ldaa    #COLOR_BYTE(CG_YELLOW)
                staa    txt_col
                ldx     #TXT_AT(1,6)
score_put:                              ; X = where: the score's six digits
                ldaa    score
                bsr     sp_byte
                ldaa    score+1
                bsr     sp_byte
                ldaa    score+2
sp_byte:        psha                    ; A = two BCD digits
                lsra
                lsra
                lsra
                lsra
                adda    #'0'
                jsr     txt_char2
                pula
                anda    #$0F
                adda    #'0'
                jmp     txt_char2

; the guards' records from their start cells, and everyone drawn
actors_draw:
                ldaa    nguard
                staa    st_n
                ldx     #guard_rc
                stx     up_s
                ldx     #guards
                stx     up_d
                ldd     seed            ; (a seed for respawning: never 0)
                bne     ad_b0
                ldd     #$ACE1
                std     seed
ad_b0:
ad_b1:          tst     st_n
                beq     ad_f1
                ldx     up_s            ; x = column * 4, y = (row + 1) * 12
                ldaa    1,x
                asla
                asla
                ldx     up_d
                staa    A_X,x
                ldx     up_s
                ldaa    0,x
                inca
                ldab    #12
                mul
                ldx     up_d
                stab    A_Y,x
                ldd     #guard_r1_hr    ; standing
                std     A_SPR,x
                ldx     up_s            ; his cell, and a fresh start
                ldd     0,x
                ldx     up_d
                std     G_R,x
                clr     G_T,x
                clr     G_DIR,x
                clr     G_FACE,x
                clr     G_ON,x
                clr     G_ST,x
                clr     G_CARRY,x
                clr     G_OUT,x
                jsr     act_draw
                ldx     up_s
                inx
                inx
                stx     up_s
                ldx     up_d
                ldab    #GD_SIZE
                abx
                stx     up_d
                dec     st_n
                bra     ad_b1
ad_f1:          ldx     #hero_a
                jmp     act_draw

fx_step:        fcb     1, SND_TONE     ; a footstep: a faint low tick (~37 Hz)
                fdb     12000, 0
                fcb     0
fx_land:        fcb     LAND_LEAD, SND_TONE ; landing: a sharp low thud, loud at
                fdb     3000, 800       ; once, from just before touchdown to it
                fcb     0
fx_dig:         fcb     DIG_T, SND_NOISE ; digging: a crunch
                fdb     500, 60
                fcb     0
fx_die:         fcb     40, SND_TONE    ; caught in a hole: a falling whine
                fdb     N_C5, 12
                fcb     0
fx_trap:        fcb     6, SND_TONE     ; a guard falls into a hole: a bonk
                fdb     2400, -200
                fcb     0
fx_bury:        fcb     10, SND_NOISE   ; a hole closes on a guard: a crunch
                fdb     900, 60
                fcb     0
fx_gem:         fcb     3, SND_TONE     ; a geode: bling
                fdb     N_E5, 0
                fcb     6, SND_TONE
                fdb     N_B5, 0
                fcb     0
fx_exit:        fcb     40, SND_TONE    ; the exit ladder grows: a rising sweep
                fdb     N_C4, -20
                fcb     0
fx_bop:         fcb     1, SND_TONE     ; the bonus counting up: a soft bop
                fdb     N_C4, 0
                fcb     0
fx_clear:       fcb     6, SND_TONE     ; out: a little fanfare
                fdb     N_C5, 0
                fcb     6, SND_TONE
                fdb     N_E5, 0
                fcb     6, SND_TONE
                fdb     N_G5, 0
                fcb     18, SND_TONE
                fdb     N_C6, 0
                fcb     0

s_file:         fcc     "LEVELS.DAT"
S_FILE_LEN      equ     *-s_file
s_nofile:       fcc     "LEVELS.DAT NOT FOUND"
                fcb     0
s_status:       fcc     "SCORE         LEVEL      LIVES"
                fcb     0
s_over:         fcc     "GAME OVER"
                fcb     0
s_congr1:       fcc     "CONGRATULATIONS!"
                fcb     0
s_congr2:       fcc     "YOU ESCAPED THE MINE!"
                fcb     0
s_congr3:       fcc     "SCORE"
                fcb     0

#include "hero.inc"
#include "holes.inc"
#include "guards.inc"
#include "draw.inc"
#include "gfx.asm"
#include "frame.asm"
#include "sound.asm"
#include "input.asm"
#include "text.asm"
#include "sprite.asm"
#include "geode_spr.inc"
#include "tiles.inc"
