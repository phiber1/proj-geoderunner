; geode.asm: Geode Runner, a single-screen digging platformer for the
; MC-10 (8K RAM mod + MCX32-SD), in CG6 on a blue background.
;
; So far: a level is read from LEVELS.DAT on the SD card (tools/levelgen.py
; makes it: a 16-byte header, then 240 bytes a level, 4 bits a cell) and
; drawn, with the guards at their starting places; the hero runs, climbs,
; hangs and falls (W A S Z or the arrow keys).  SPACE shows the next level
; (for now).

#define GFX_MODE GFX_CG6
#define GFX_BG CG_BLUE
#include "layout.inc"

BIOS_SEEK       equ     8               ; MCX BIOS 'P': set the file position
                                        ; (32 bits: PB_BUF high, PB_LEN low)
LV_FILE         equ     1               ; the file number LEVELS.DAT uses
NLEVELS         equ     150
LV_COLS         equ     32
LV_ROWS         equ     15
LV_CELLS        equ     LV_COLS*LV_ROWS
LV_RECORD       equ     LV_CELLS/2      ; bytes a level in the file
LV_HEADER       equ     16
MAX_GUARDS      equ     5

; actor records and the shadow buffer (draw.inc)
A_X             equ     0               ; place
A_Y             equ     1
A_OX            equ     2               ; ... where last drawn
A_OY            equ     3
A_SPR           equ     4               ; pose (a sprite's draw table)
A_OSPR          equ     6               ; ... the pose last drawn
A_SIZE          equ     8
SH_MARGIN       equ     12              ; shadow rows above and below a patch,
SH_ROWS         equ     36              ; for actors partly outside it

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

                org     LOW
lv_buf          rmb     LV_RECORD       ; a level as read
lv_map          rmb     LV_CELLS        ; ... and unpacked, a cell a byte
shadow          rmb     (SH_ROWS+2*SH_MARGIN)*ROW_BYTES ; draw.inc: patches built here

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
joy_force       rmb     1               ; debug builds: nonzero = held keys (tests)
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
guards          rmb     A_SIZE*MAX_GUARDS ; the guards' actor records
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

                org     CODE
start:
                sei
                lds     #STACK_TOP
                jsr     gfx_init
                ldaa    #1
                staa    level
                clr     key_was
                clr     joy_force
                jsr     frame_init
new_level:
                jsr     lv_load         ; the level from the SD card
                bcs     no_file
                jsr     lv_actors
                jsr     gfx_cls
                jsr     lv_draw
                jsr     status_draw
                jsr     hero_init
                jsr     actors_draw
loop:
                jsr     frame_wait
                jsr     snd_frame
                jsr     kbd_read
                if      DEBUG           ; (tests poke joy_force to hold keys)
                ldaa    joy_force
                beq     dbg_f1
                staa    joy
dbg_f1:
                endif
                jsr     hero_update
                jsr     hero_pose
                ldx     #hero_a
                jsr     act_update
                ldaa    joy             ; SPACE: the next level
                anda    #J_FIRE
                tab
                eora    key_was         ; (on the press)
                stab    key_was
                anda    key_was
                beq     loop
                ldaa    level
                inca
                cmpa    #NLEVELS+1
                bcs     nl_f1
                ldaa    #1
nl_f1:          staa    level
                bra     new_level

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
                ldd     #s_score
                jsr     txt_str2
                ldaa    level           ; three digits
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
                ldd     #s_lives
                jmp     txt_str2

; the guards' records from their start cells, and everyone drawn
actors_draw:
                ldaa    nguard
                staa    st_n
                ldx     #guard_rc
                stx     up_s
                ldx     #guards
                stx     up_d
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
                jsr     act_draw
                ldx     up_s
                inx
                inx
                stx     up_s
                ldx     up_d
                ldab    #A_SIZE
                abx
                stx     up_d
                dec     st_n
                bra     ad_b1
ad_f1:          ldx     #hero_a
                jmp     act_draw

fx_step:        fcb     1, SND_TONE     ; a footstep: a low soft tick (~75 Hz)
                fdb     6000, 0
                fcb     0
fx_land:        fcb     3, SND_NOISE    ; landing: a thump
                fdb     1400, 200
                fcb     0

s_file:         fcc     "LEVELS.DAT"
S_FILE_LEN      equ     *-s_file
s_nofile:       fcc     "LEVELS.DAT NOT FOUND"
                fcb     0
s_score:        fcc     "SCORE 000000  LEVEL "
                fcb     0
s_lives:        fcc     "  LIVES 3"
                fcb     0

#include "hero.inc"
#include "draw.inc"
#include "gfx.asm"
#include "frame.asm"
#include "sound.asm"
#include "input.asm"
#include "text.asm"
#include "sprite.asm"
#include "geode_spr.inc"
#include "tiles.inc"
