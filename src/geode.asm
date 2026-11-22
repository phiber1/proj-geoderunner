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
h_x             rmb     1               ; ... his pixel place,
h_y             rmb     1
h_ox            rmb     1               ; ... where he was drawn,
h_oy            rmb     1
h_t             rmb     1               ; ... frames left of the move,
h_dir           rmb     1               ; ... the move (D_*),
h_fall          rmb     1               ; ... nonzero while falling
hu_here         rmb     1               ; ... the cell he's on, the one below
hu_below        rmb     1
ca_c            rmb     1               ; cell_at
ca_p            rmb     2
rs_x            rmb     1               ; restore
rs_y            rmb     1
rs_c0           rmb     1
rs_c1           rmb     1
rs_c            rmb     1
rs_r            rmb     1
rs_r1           rmb     1

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
                jsr     hero_draw
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
                bsr     draw_cell
                pula
                pulb
                incb
                cmpb    #LV_COLS
                bne     ld_b2
                inca
                cmpa    #LV_ROWS
                bne     ld_b1
                rts

; draw_cell: A = row, B = column: draw that cell's tile
draw_cell:
                staa    dc_r
                stab    dc_c
                ldab    #LV_COLS        ; its map byte: lv_map + row*32 + col
                mul
                addb    dc_c
                adca    #0
                addd    #lv_map
                std     dc_m
                ldx     dc_m
                ldab    0,x
                cmpb    #C_BRICK
                beq     dc_brick
                ldx     #celltile       ; the tile for the cell's code
                abx
                ldaa    0,x
                bra     dc_tile
dc_brick:       ldaa    #T_BRICK_TOP    ; brick: on top of more brick,
                ldab    dc_r
                cmpb    #LV_ROWS-1
                beq     dc_b_f1
                ldab    LV_COLS,x
                cmpb    #C_BRICK
                beq     dc_tile
dc_b_f1:        ldaa    #T_BRICK_LOW    ; ... under brick,
                ldab    dc_r
                beq     dc_b_f2
                dex                     ; (the cell above: X - 32)
                ldab    #LV_COLS-1
dc_b_b1:        dex
                decb
                bne     dc_b_b1
                ldab    0,x
                cmpb    #C_BRICK
                beq     dc_tile
dc_b_f2:        ldaa    #T_BRICK        ; ... or on its own
dc_tile:        ldab    #12             ; its 12 bytes
                mul
                addd    #tiles
                std     dc_t
                ldx     #rowaddr        ; its place: the row's start + col
                ldab    dc_r
                aslb
                abx
                ldd     0,x
                addb    dc_c
                adca    #0
                std     dc_s
k               set     0
                rept    8               ; rows 0-7
                ldx     dc_t
                ldaa    k,x
                ldx     dc_s
                staa    k*ROW_BYTES,x
k               set     k+1
                endm
                ldd     dc_s            ; rows 8-11: 256 bytes on
                inca
                std     dc_s
                rept    4
                ldx     dc_t
                ldaa    k,x
                ldx     dc_s
                staa    (k-8)*ROW_BYTES,x
k               set     k+1
                endm
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

; the hero and the guards, at their start cells
actors_draw:
                bsr     guards_draw
                ldaa    h_x
                jsr     sprite_x
                ldab    h_y
                ldx     #hero_hr
                jmp     spr_art

guards_draw:
                ldaa    nguard
                staa    st_n
                ldx     #guard_rc
gd_b1:          tst     st_n
                beq     gd_r
                stx     dc_m
                ldd     0,x
                ldx     #guard_hr
                bsr     actor_at
                ldx     dc_m
                inx
                inx
                dec     st_n
                bra     gd_b1
gd_r:           rts

; actor_at: A = row, B = column, X = a sprite's draw table: draw it there
actor_at:
                inca                    ; y = (row + 1) * 12
                psha
                aslb                    ; x = column * 4, centered
                aslb
                tba
                jsr     sprite_x
                tab
                pula
                pshb
                ldab    #12
                mul                     ; B = y
                pula                    ; A = x
                jmp     spr_art

fx_step:        fcb     1, SND_NOISE    ; a footstep: a click
                fdb     700, 0
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
#include "gfx.asm"
#include "frame.asm"
#include "sound.asm"
#include "input.asm"
#include "text.asm"
#include "sprite.asm"
#include "geode_spr.inc"
#include "tiles.inc"
