; hero.inc: the hero, moving cell to cell.
;
; He is always on a cell or on his way to the next one.  On a cell he
; looks at the map and the keys: with nothing holding him up (no floor or
; ladder under him, not on a ladder or a cable) he falls; else UP climbs a
; ladder, DOWN climbs down one (or lets go of a ladder or cable over air),
; LEFT and RIGHT walk, hang along a cable or step off a ladder.  Falling
; past a cable catches it.  A move takes H_WALK frames (H_FALL falling);
; h_r, h_c are the cell he's on or moving to, h_x, h_y his pixel place
; (the cell's left pixel and top row when he's on it).

H_WALK          equ     8               ; frames to walk or climb a cell
H_FALL          equ     4               ; ... to fall one

D_NONE          equ     0               ; h_dir: the move under way
D_LEFT          equ     1
D_RIGHT         equ     2
D_UP            equ     3
D_DOWN          equ     4
D_FALL          equ     5

; cell_at: A = row, B = column (either may be off the level): A = the
; cell's code.  Off the sides and below: stone; above: air.  The hidden
; exit ladder is air until it appears.  Uses X.
cell_at:
                tsta
                bmi     ca_air
                cmpa    #LV_ROWS
                bcc     ca_stone
                tstb
                bmi     ca_stone
                cmpb    #LV_COLS
                bcc     ca_stone
                stab    ca_c
                ldab    #LV_COLS
                mul
                addb    ca_c
                adca    #0
                addd    #lv_map
                std     ca_p
                ldx     ca_p
                ldaa    0,x
                cmpa    #C_EXIT
                bne     ca_r
ca_air:         clra
ca_r:           rts
ca_stone:       ldaa    #C_STONE
                rts

; is_solid: A = a code: Z set if it can't be walked into (brick, stone)
is_solid:
                cmpa    #C_BRICK
                beq     is_r
                cmpa    #C_STONE
is_r:           rts

hero_init:
                ldd     hero_r          ; the start cell
                std     h_r
                clr     h_t
                clr     h_dir
                clr     h_fall
                ldaa    h_c             ; x = column * 4
                asla
                asla
                staa    h_x
                ldaa    h_r             ; y = (row + 1) * 12
                inca
                ldab    #12
                mul
                stab    h_y
                ldd     h_x
                std     h_ox
                rts

; hero_update: once a frame
hero_update:
                tst     h_t
                beq     hu_decide
                ldab    h_t             ; under way: a step of the move
                ldaa    h_dir
                cmpa    #D_LEFT
                bne     hu_f1
                bitb    #1              ; (a pixel every other frame)
                bne     hu_next
                dec     h_x
                bra     hu_next
hu_f1:          cmpa    #D_RIGHT
                bne     hu_f2
                bitb    #1
                bne     hu_next
                inc     h_x
                bra     hu_next
hu_f2:          ldx     #climbtab       ; (12 rows over 8 frames)
                abx
                cmpa    #D_UP
                bne     hu_f3
                ldaa    h_y
                suba    0,x
                staa    h_y
                bra     hu_next
hu_f3:          cmpa    #D_DOWN
                bne     hu_f4
                ldaa    h_y
                adda    0,x
                staa    h_y
                bra     hu_next
hu_f4:          ldaa    h_y             ; falling: 3 rows a frame
                adda    #12/H_FALL
                staa    h_y
hu_next:        dec     h_t
                beq     hu_decide       ; there: on to the next move at once
                rts

hu_decide:
                clr     h_dir
                ldaa    h_r             ; what's here, and under him
                ldab    h_c
                jsr     cell_at
                staa    hu_here
                ldaa    h_r
                inca
                ldab    h_c
                jsr     cell_at
                staa    hu_below
                ldaa    hu_here         ; held up?  on a ladder or cable,
                cmpa    #C_LADDER
                beq     hu_held
                cmpa    #C_CABLE
                beq     hu_held
                ldaa    hu_below        ; ... or floor or ladder below
                cmpa    #C_LADDER
                beq     hu_held
                jsr     is_solid
                beq     hu_held
                jmp     hu_dofall       ; no: he falls
hu_held:        tst     h_fall          ; landed?
                beq     hu_keys
                clr     h_fall
                ldx     #fx_land
                ldaa    #2
                jsr     snd_play
hu_keys:        ldab    joy
                bitb    #J_UP           ; UP: up a ladder
                beq     hu_k2
                ldaa    hu_here
                cmpa    #C_LADDER
                bne     hu_k2
                ldaa    h_r
                beq     hu_k2
                deca
                ldab    h_c
                jsr     cell_at
                jsr     is_solid
                beq     hu_k2
                dec     h_r
                ldaa    #D_UP
                bra     hu_go
hu_k2:          ldab    joy             ; DOWN: down a ladder, or let go
                bitb    #J_DOWN
                beq     hu_k3
                ldaa    hu_below
                cmpa    #C_LADDER
                beq     hu_down
                jsr     is_solid
                beq     hu_k3
                ldaa    hu_here
                cmpa    #C_LADDER
                beq     hu_dofall
                cmpa    #C_CABLE
                beq     hu_dofall
                bra     hu_k3
hu_down:        inc     h_r
                ldaa    #D_DOWN
                bra     hu_go
hu_k3:          ldab    joy             ; LEFT
                bitb    #J_LEFT
                beq     hu_k4
                ldab    h_c
                beq     hu_k4
                decb
                ldaa    h_r
                jsr     cell_at
                jsr     is_solid
                beq     hu_k4
                dec     h_c
                ldaa    #D_LEFT
                bra     hu_walk
hu_k4:          ldab    joy             ; RIGHT
                bitb    #J_RIGHT
                beq     hu_r
                ldab    h_c
                cmpb    #LV_COLS-1
                beq     hu_r
                incb
                ldaa    h_r
                jsr     cell_at
                jsr     is_solid
                beq     hu_r
                inc     h_c
                ldaa    #D_RIGHT
hu_walk:        psha                    ; (a footstep)
                ldx     #fx_step
                ldaa    #1
                jsr     snd_play
                pula
hu_go:          staa    h_dir
                ldaa    #H_WALK
                staa    h_t
hu_r:           rts
hu_dofall:      inc     h_r
                ldaa    #D_FALL
                staa    h_dir
                staa    h_fall          ; (nonzero: falling)
                ldaa    #H_FALL
                staa    h_t
                rts

climbtab:       fcb     0, 1, 2, 1, 2, 1, 2, 1, 2       ; by frames left: 12 rows

; ---------------------------------------------------------------- drawing

; sprite_x: A = an actor's x (its cell's left pixel): A = the sprite's x,
; centered (one pixel left), kept on the screen
sprite_x:
                tsta
                beq     sx_r
                deca
                cmpa    #128-6
                bls     sx_r
                ldaa    #128-6
sx_r:           rts

; hero_draw: if he moved, the tiles under where he was, the guards, him
hero_draw:
                ldd     h_x
                subd    h_ox
                beq     hd_r
                ldaa    h_ox
                bsr     sprite_x
                ldab    h_oy
                bsr     restore
                jsr     guards_draw
                ldaa    h_x
                bsr     sprite_x
                ldab    h_y
                ldx     #hero_hr
                jsr     spr_art
                ldd     h_x
                std     h_ox
hd_r:           rts

; restore: A = sprite x, B = y: redraw every cell under a sprite there
restore:
                staa    rs_x
                stab    rs_y
                lsra                    ; the columns it spans
                lsra
                staa    rs_c0
                ldaa    rs_x
                adda    #5
                lsra
                lsra
                staa    rs_c1
                ldaa    rs_y            ; the rows (level rows: screen row - 1)
                bsr     div12
                deca
                staa    rs_r
                ldaa    rs_y
                adda    #11
                bsr     div12
                deca
                cmpa    #LV_ROWS-1
                bls     rs_f1
                ldaa    #LV_ROWS-1
rs_f1:          staa    rs_r1
rs_b1:          ldaa    rs_c0
                staa    rs_c
rs_b2:          ldaa    rs_r
                bmi     rs_f2
                ldab    rs_c
                jsr     draw_cell
rs_f2:          inc     rs_c
                ldaa    rs_c
                cmpa    rs_c1
                bls     rs_b2
                inc     rs_r
                ldaa    rs_r
                cmpa    rs_r1
                ble     rs_b1
                rts

div12:                                  ; A = A / 12
                clrb
d12_b1:         cmpa    #12
                bcs     d12_r
                suba    #12
                incb
                bra     d12_b1
d12_r:          tba
                rts
