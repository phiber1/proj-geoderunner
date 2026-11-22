; geode.asm: Geode Runner, a single-screen digging platformer for the
; MC-10 (8K RAM mod + MCX32-SD), in CG6 on a blue background.
;
; For now a skeleton: the screen, the status line, and the hero walking
; left and right (A / S or the arrow keys) past a thief and a geode.

#define GFX_MODE GFX_CG6
#define GFX_BG CG_BLUE
#include "layout.inc"

FLOOR_Y         equ     150             ; the hero's top row, for now

                org     CODE
start:
                sei
                lds     #STACK_TOP
                jsr     gfx_init
                ldaa    #COLOR_BYTE(CG_YELLOW)
                staa    txt_col
                ldx     #TXT_AT(2,0)
                ldd     #s_status
                jsr     txt_str
                ldx     #TXT_AT(80,10)
                ldd     #s_title
                jsr     txt_str2
                ldx     #objs
                stx     obj_first
                ldx     #objs_end
                stx     obj_end
                jsr     frame_init
loop:
                jsr     frame_wait
                jsr     snd_frame
                jsr     kbd_read
                jsr     hero_move
                jsr     thief_move
                jsr     spr_update_all
                bra     loop

; the hero walks at half a pixel a frame while A or S is held
hero_move:
                ldd     #0
                ldab    joy
                bitb    #J_LEFT
                beq     hm_f1
                ldd     #-$80
                bra     hm_f2
hm_f1:          bitb    #J_RIGHT
                beq     hm_f2
                ldd     #$80
hm_f2:          std     hero+O_DX
                ldd     hero+O_X        ; stay on the screen
                addd    hero+O_DX
                cmpa    #128-hero_W
                bcs     hm_r
                ldd     #0
                std     hero+O_DX
hm_r:           rts

; the thief paces back and forth
thief_move:
                ldd     thief+O_X
                addd    thief+O_DX
                cmpa    #128-thief_W
                bcs     tm_r
                ldd     #0
                subd    thief+O_DX
                std     thief+O_DX
tm_r:           rts

s_status:       fcc     "SCORE 000000  LEVEL 001  LIVES 3"
                fcb     0
s_title:        fcc     "GEODE RUNNER"
                fcb     0

; objects: x.frac, y.frac, dx, dy, descriptor (later ones in front)
objs:
                fcb     90, 0, FLOOR_Y+5, 0
                fdb     0, 0, geode_dsc
thief:          fcb     20, 0, FLOOR_Y-1, 0
                fdb     $40, 0, thief_dsc
hero:           fcb     60, 0, FLOOR_Y, 0
                fdb     0, 0, hero_dsc
objs_end:

#include "gfx.asm"
#include "frame.asm"
#include "sound.asm"
#include "input.asm"
#include "text.asm"
#include "sprite.asm"
#include "sprman.asm"
#include "geode_spr.inc"
