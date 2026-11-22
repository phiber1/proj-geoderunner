; mockup.asm: shows a still screen made by mockups/plat.py (an early look
; at the game) in mono RG6 with CSS=0: green on black; or, built with
; MK_CG6 and MK_SCR, one made by mockups/plat_cg6.py in CG6.
;
;   make run-mockup              mono
;   make run-mockup_blue         CG6 on blue
;   make run-mockup_green        CG6 on green

#ifdef MK_CG6
#define MK_MODE (VDG_AG|VDG_GM2|VDG_GM1)
#else
#define MK_MODE VDG_RG6
#define MK_SCR "mockup_scr.inc"
#endif

#include "layout.inc"

                org     BSS
mk_src          rmb     2
mk_dst          rmb     2

                org     CODE
start:
                sei
                lds     #STACK_TOP
                ldaa    #MK_MODE        ; CSS=0
                staa    VDG
                ldx     #mk_scr
                stx     mk_src
                ldx     #SCREEN
mk_copy:        stx     mk_dst
                ldx     mk_src
                ldd     0,x
                inx
                inx
                stx     mk_src
                ldx     mk_dst
                std     0,x
                inx
                inx
                cpx     #SCREEN_END
                bne     mk_copy
                bra     *

mk_scr:
#include MK_SCR
