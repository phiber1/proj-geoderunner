; holes.inc: holes the hero digs in brick.
;
; A hole goes through: digging (the brick crumbles in two stages, still
; solid: DIG_T frames), open (air: OPEN_T frames), filling (two stages,
; open to walk and fall through: FILL_T frames), then brick again.  A hole
; that fills with the hero in it kills him.  The cells above and below are
; redrawn with it (brick on brick draws differently from brick alone).

; (HOLES, O_* are defined in geode.asm, before the variables)
HS_DIG          equ     1
HS_OPEN         equ     2
HS_FILL         equ     3

DIG_T           equ     12              ; frames to dig
OPEN_T          equ     300             ; ... a hole stays open (5 s)
FILL_T          equ     24              ; ... to fill

holes_init:
                ldx     #holes
                ldab    #HOLES*O_SIZE
hi_b1:          clr     0,x
                inx
                decb
                bne     hi_b1
                rts

; hole_start: A = row, B = column: start digging that brick.  Carry set if
; no record is free.
hole_start:
                std     ho_rc
                ldx     #holes
                ldab    #HOLES
hs_b1:          tst     O_ST,x
                beq     hs_f1
                pshb
                ldab    #O_SIZE
                abx
                pulb
                decb
                bne     hs_b1
                sec
                rts
hs_f1:          ldd     ho_rc
                std     O_R,x
                ldaa    #HS_DIG
                staa    O_ST,x
                ldd     #DIG_T
                std     O_T,x
                ldaa    #C_DIG1
                jsr     ho_set
                ldx     #fx_dig
                ldaa    #3
                jsr     snd_play
                clc
                rts

; hole_update: once a frame
hole_update:
                ldx     #holes
                stx     ho_p
                ldaa    #HOLES
                staa    ho_n
hu2_b1:         ldx     ho_p
                tst     O_ST,x
                beq     hu2_next
                ldd     O_R,x
                std     ho_rc
                ldd     O_T,x
                subd    #1
                std     O_T,x
                ldaa    O_ST,x
                cmpa    #HS_DIG
                bne     hu2_f2
                ldd     O_T,x           ; digging: half way, then open
                subd    #DIG_T/2
                bne     hu2_f1
                ldaa    #C_DIG2
                jsr     ho_set
                bra     hu2_next
hu2_f1:         ldd     O_T,x
                bne     hu2_next
                ldaa    #HS_OPEN
                staa    O_ST,x
                ldd     #OPEN_T
                std     O_T,x
                ldaa    #C_AIR
                jsr     ho_set
                bra     hu2_next
hu2_f2:         cmpa    #HS_OPEN
                bne     hu2_f3
                ldd     O_T,x           ; open: then it starts to fill
                bne     hu2_next
                ldaa    #HS_FILL
                staa    O_ST,x
                ldd     #FILL_T
                std     O_T,x
                ldaa    #C_FILL2
                jsr     ho_set
                bra     hu2_next
hu2_f3:         ldd     O_T,x           ; filling: half way, then brick
                subd    #FILL_T/2
                bne     hu2_f4
                ldaa    #C_FILL1
                jsr     ho_set
                bra     hu2_next
hu2_f4:         ldd     O_T,x
                bne     hu2_next
                clr     O_ST,x
                ldaa    #C_BRICK
                jsr     ho_set
                ldd     ho_rc           ; a guard trapped in it: buried
                jsr     guard_bury
                ldd     h_r             ; the hero in it?
                subd    ho_rc
                bne     hu2_next
                inc     h_dead
hu2_next:       ldx     ho_p
                ldab    #O_SIZE
                abx
                stx     ho_p
                dec     ho_n
                beq     hu2_r
                jmp     hu2_b1
hu2_r:          rts

; hole_open: Z set if the guard in gs (gs_r, gs_c) is in a hole that is
; open or filling (a hole being dug is still solid)
hole_open:
                ldx     #holes
                ldab    #HOLES
ho_b1:          ldaa    O_ST,x
                cmpa    #HS_OPEN
                bcs     ho_next
                ldaa    O_R,x
                cmpa    gs_r
                bne     ho_next
                ldaa    O_C,x
                cmpa    gs_c
                bne     ho_next
                clra                    ; (Z)
                rts
ho_next:        pshb
                ldab    #O_SIZE
                abx
                pulb
                decb
                bne     ho_b1
                ldaa    #1
                rts

; ho_set: A = a cell code: the hole's cell (ho_rc) becomes it; redraw it
; and the cells above and below, and have the hero redrawn over them
ho_set:
                psha
                ldaa    ho_rc
                ldab    #LV_COLS
                mul
                addb    ho_rc+1
                adca    #0
                addd    #lv_map
                std     ho_m
                ldx     ho_m
                pula
                staa    0,x
                ldd     ho_rc
                jsr     draw_cell
                ldaa    ho_rc
                beq     hs2_f1
                deca
                ldab    ho_rc+1
                jsr     draw_cell
hs2_f1:         ldaa    ho_rc
                cmpa    #LV_ROWS-1
                beq     hs2_f2
                inca
                ldab    ho_rc+1
                jsr     draw_cell
hs2_f2:         ldd     #0              ; (a pose no one has: redraw him)
                std     hero_a+A_OSPR
                rts
