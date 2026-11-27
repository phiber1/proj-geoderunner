; hero.inc: the hero, moving cell to cell.
;
; He is always on a cell or on his way to the next one.  On a cell he
; looks at the map and the keys: with nothing holding him up (no floor or
; ladder under him, not on a ladder or a cable) he falls; else UP climbs a
; ladder, DOWN climbs down one (or lets go of a ladder or cable over air),
; LEFT and RIGHT walk, hang along a cable or step off a ladder.  Falling
; past a cable catches it.  A move takes H_WALK frames (H_CLIMB on a
; ladder, H_FALL falling: a slow drift down); h_r, h_c are the cell he's on
; or moving to.  His actor record (draw.inc) is hero_a: h_x, h_y his pixel
; place, h_spr his pose, set by hero_pose from what he's doing.

H_WALK          equ     8               ; frames to walk a cell (1 pixel / 2)
H_CLIMB         equ     10              ; ... to climb one (climbtab)
H_FALL          equ     12              ; ... to fall one (a row a frame)
DIG_LATCH       equ     12              ; frames a SPACE tap is remembered
LAND_LEAD       equ     4               ; frames before touchdown the thud starts
                                        ; (sound reaches the ear a few frames late)

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

; is_solid: A = a code: Z set if it can't be walked into (brick, stone,
; brick being dug)
is_solid:
                cmpa    #C_BRICK
                beq     is_r
                cmpa    #C_STONE
                beq     is_r
                cmpa    #C_DIG1
                beq     is_r
                cmpa    #C_DIG2
is_r:           rts

; floor_at: Z set if the cell below the hero's row in column B is floor
; (brick or stone; off the edge isn't)
floor_at:
                cmpb    #LV_COLS        ; (unsigned: -1 is off the edge too)
                bcc     fa_no
                ldaa    h_r
                inca
                jsr     cell_at
                jmp     is_solid
fa_no:          ldaa    #1              ; (clears Z)
                rts

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
                clr     h_face
                clr     h_on
                clr     h_dig
                clr     h_dlat
                clr     h_spw           ; (no press carried over)
                clr     h_dead
                jmp     hero_pose

; hero_update: once a frame
hero_update:
                ldab    joy             ; SPACE: one press, one hole.  The
                andb    #J_FIRE         ; press is remembered for a moment, so
                tba                     ; a quick tap mid-step still digs at
                eora    h_spw           ; the next cell; holding it does
                stab    h_spw           ; nothing more
                anda    h_spw
                beq     hu_l1
                ldab    joy             ; the way: A/S with the press, else
                andb    #J_LEFT|J_RIGHT ; the way he faces then (an arrow
                bne     hu_l0           ; pressed later doesn't turn it)
                ldab    #J_RIGHT
                tst     h_face
                beq     hu_l0
                ldab    #J_LEFT
hu_l0:          stab    h_ddir
                ldaa    #DIG_LATCH
                staa    h_dlat
                bra     hu_l2
hu_l1:          tst     h_dlat
                beq     hu_l2
                dec     h_dlat
hu_l2:
                tst     h_dig           ; digging: he stands and digs
                beq     hu_f0
                dec     h_dig
                rts
hu_f0:          tst     h_t
                bne     hu_f00
                jmp     hu_decide
hu_f00:
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
hu_f2:          ldx     #climbtab       ; (12 rows over H_CLIMB frames)
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
hu_f4:          inc     h_y             ; falling: a row a frame
hu_next:        dec     h_t
                bne     hu_n1
                jmp     hu_decide       ; there: on to the next move at once
hu_n1:          ldaa    h_t             ; just before landing: the thud
                cmpa    #LAND_LEAD
                bne     hu_nr
                ldaa    h_dir
                cmpa    #D_FALL
                bne     hu_nr
                jsr     lands
                bne     hu_nr
                clr     h_fall          ; (heard: not again on arrival)
                ldx     #fx_land
                ldaa    #2
                jsr     snd_play
                jsr     snd_frame       ; (to the speaker now, not next frame)
hu_nr:          rts

; lands: Z set if the cell he's moving to (h_r, h_c) will hold him up: a
; ladder or cable there, floor or ladder below
lands:
                ldaa    h_r
                ldab    h_c
                jsr     cell_at
                cmpa    #C_GEODE        ; (a geode there doesn't hold him)
                beq     ln_f1
                cmpa    #C_LADDER
                beq     ln_r
                cmpa    #C_CABLE
                beq     ln_r
ln_f1:          ldaa    h_r
                inca
                ldab    h_c
                jsr     cell_at
                cmpa    #C_LADDER
                beq     ln_r
                jsr     is_solid
ln_r:           rts

hu_decide:
                clr     h_dir
                clr     h_on
                clr     h_head
                ldaa    h_r             ; what's here, and under him
                ldab    h_c
                jsr     cell_at
                cmpa    #C_GEODE        ; (a geode: his)
                bne     hu_g1
                jsr     geode_take
                clra
hu_g1:          staa    hu_here
                ldaa    h_r
                inca
                ldab    h_c
                jsr     cell_at
                staa    hu_below
                ldaa    hu_here         ; held up?  on a ladder or cable,
                cmpa    #C_LADDER
                beq     hu_ladder
                cmpa    #C_CABLE
                beq     hu_cable
                ldaa    hu_below        ; ... or floor or ladder below
                cmpa    #C_LADDER
                beq     hu_held
                jsr     is_solid
                beq     hu_held
                ldaa    h_r             ; ... or a guard's head (trapped or not)
                inca
                ldab    h_c
                jsr     head_in
                bne     hu_nohead
                inc     h_head          ; (on a head: pressing down is death)
                bra     hu_held
hu_nohead:      jmp     hu_dofall       ; no: he falls
                bra     hu_held
hu_ladder:      ldaa    hu_below        ; a ladder's foot, on the floor, or
                jsr     is_solid        ; where it passes a floor (floor on
                beq     hu_held         ; either side below): he stands there
                ldab    h_c             ; and can dig beside it; UP or DOWN
                decb                    ; takes him on along the ladder
                jsr     floor_at
                beq     hu_held
                ldab    h_c
                incb
                jsr     floor_at
                beq     hu_held
                ldaa    #1              ; (h_on: 1 on a ladder, 2 on a cable)
                bra     hu_on
hu_cable:       ldaa    #2
hu_on:          staa    h_on
hu_held:        tst     h_fall          ; landed?
                beq     hu_keys
                clr     h_fall
                ldx     #fx_land
                ldaa    #2
                jsr     snd_play
hu_keys:        tst     h_dlat          ; SPACE (now or just now): dig, left
                beq     hu_k1           ; or right (or the way he faces)
                tst     h_on            ; (standing on a floor)
                bne     hu_nd1
                ldab    h_ddir          ; (the way, from the press)
                ldaa    #-1
                bitb    #J_LEFT
                bne     hu_dig
                ldaa    #1
                bitb    #J_RIGHT
                bne     hu_dig
                tst     h_face
                beq     hu_dig
                ldaa    #-1
hu_dig:         staa    hu_dc
                ldab    #1              ; (face that way)
                tsta
                bmi     hu_dg1
                clrb
hu_dg1:         stab    h_face
                ldab    h_c             ; beside him: open?
                addb    hu_dc
                ldaa    h_r
                jsr     cell_at
                cmpa    #C_AIR          ; (not under a geode or a ladder)
                bne     hu_nodig
                ldab    h_c             ; ... and brick below that?
                addb    hu_dc
                ldaa    h_r
                inca
                jsr     cell_at
                cmpa    #C_BRICK
                bne     hu_nodig
                ldab    h_c
                addb    hu_dc
                ldaa    h_r
                inca
                jsr     hole_start
                bcs     hu_nodig
                ldaa    #DIG_T
                staa    h_dig
                clr     h_dlat          ; (the press used)
hu_r0:          rts
hu_nodig:                               ; no dig there: the press is
hu_nd1:         clr     h_dlat          ; forgotten and he moves on
hu_k1:          ldab    joy
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
                bra     hu_climb
hu_k2:          ldab    joy             ; DOWN: down a ladder, or let go
                bitb    #J_DOWN
                beq     hu_k3
                tst     h_head          ; (onto the guard under him: caught)
                beq     hu_k20
                inc     h_dead
                rts
hu_k20:
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
hu_climb:       staa    h_dir
                ldaa    #H_CLIMB
                staa    h_t
                rts
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
                ldaa    #1              ; (facing left)
                staa    h_face
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
                clr     h_face
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

climbtab:       fcb     0, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1 ; by frames left: 12 rows

; hero_pose: his pose from what he's doing: falling, on a cable (hand
; over hand while moving), climbing (hands and feet alternating), walking
; (a stride, then legs together, facing his way), or standing
hero_pose:
                ldx     #hero_f_hr      ; falling
                ldaa    h_dir
                cmpa    #D_FALL
                beq     hp_set
                ldab    h_t             ; the first half of a move: pose 0,
                cmpb    #H_CLIMB/2      ; the second: pose 1 (b: 0 or 2)
                bhi     hp_f0
                ldab    #2
                bra     hp_f1
hp_f0:          clrb
hp_f1:          tst     h_t
                bne     hp_f2
                ldab    #2              ; (still: pose 1)
hp_f2:          ldaa    h_on
                cmpa    #2
                bne     hp_f3
                ldx     #hero_h0        ; on a cable
                tst     h_t
                bne     hp_pick
                ldab    #2
                bra     hp_pick
hp_f3:          ldaa    h_dir
                cmpa    #D_UP
                beq     hp_climb
                cmpa    #D_DOWN
                beq     hp_climb
                tst     h_t
                bne     hp_walk
                tst     h_on            ; still on a ladder
                beq     hp_walk
                clrb
hp_climb:       ldx     #hero_c0
                bra     hp_pick
hp_walk:        ldx     #hero_r0        ; walking or standing, facing his way
                tst     h_face
                beq     hp_pick
                ldx     #hero_l0
hp_pick:        abx                     ; (pose 0 or 1: the next table entry)
                ldx     0,x
hp_set:         stx     h_spr
                rts

; the poses' draw tables, in pairs (pose 0, pose 1)
hero_r0:        fdb     hero_r0_hr, hero_r1_hr
hero_l0:        fdb     hero_l0_hr, hero_l1_hr
hero_c0:        fdb     hero_c0_hr, hero_c1_hr
hero_h0:        fdb     hero_h0_hr, hero_h1_hr
