; guards.inc: the guards.
;
; A guard's record is an actor record (draw.inc) followed by its own state
; (G_*: defined in geode.asm).  Each frame a guard either takes a step of
; the move under way or, on a cell, decides the next one:
;
;   - with nothing holding him up he falls;
;   - landing in (or walking over) a hole the hero dug, he's trapped: he
;     stays in it even if there's air below, drops any geode he carries
;     into the cell above him, and after TRAP_T frames climbs out (if it
;     fills first he's buried: he comes back at the top);
;   - else he tracks the hero: on the hero's row, straight at him; hero
;     above, up a ladder if he's on one, else to the nearest ladder up on
;     his floor; hero below, down a ladder or off the edge (or a cable) if
;     he can, else to the nearest way down; with no such way, under or over
;     the hero's column.  He freezes only when a wall or another guard is
;     in the way.
;
; He picks up a geode he passes over (no sign of it), and drops it after
; CARRY_T frames at the next place it can rest on something solid.
;
; The scratch copy: the guard being worked on is copied to gs (GD_SIZE
; bytes) and back, so the routines here can use X freely.

G_WALK          equ     10              ; frames to walk a cell (the hero: 8)
G_CLIMB         equ     12              ; ... climb one (a row a frame)
G_FALL          equ     12              ; ... fall one
TRAP_T          equ     150             ; frames stuck in a hole before climbing out
CARRY_T         equ     600             ; frames a geode is carried at most

GS_FREE         equ     0               ; G_ST: chasing,
GS_TRAP         equ     1               ; ... trapped in a hole

gs_x            equ     gs+A_X
gs_y            equ     gs+A_Y
gs_spr          equ     gs+A_SPR
gs_r            equ     gs+G_R
gs_c            equ     gs+G_C
gs_t            equ     gs+G_T
gs_dir          equ     gs+G_DIR
gs_face         equ     gs+G_FACE
gs_on           equ     gs+G_ON
gs_st           equ     gs+G_ST
gs_tt           equ     gs+G_TT
gs_carry        equ     gs+G_CARRY
gs_ct           equ     gs+G_CT
gs_climbed      equ     gs+G_OUT

; guards_update: every guard, once a frame
guards_update:
                ldaa    nguard
                beq     gup_r
                staa    gu_n
                ldx     #guards
gup_b1:         stx     gu_p
                jsr     gs_in
                jsr     guard_update
                jsr     guard_pose
                ldx     gu_p
                jsr     gs_out
                ldaa    gu_n            ; redraw him if he moved: each guard
                eora    frame_count     ; every other frame, half of them on
                lsra                    ; each (they move every frame)
                bcs     gup_f1
                ldx     gu_p
                jsr     act_update
gup_f1:
                ldx     gu_p
                ldab    #GD_SIZE
                abx
                dec     gu_n
                bne     gup_b1
gup_r:          rts

gs_in:                                  ; X = a guard: copy it to gs
k               set     0
                rept    GD_SIZE/2
                ldd     k,x
                std     gs+k
k               set     k+2
                endm
                rts

gs_out:                                 ; X = a guard: copy gs back to it
k               set     0
                rept    GD_SIZE/2
                ldd     gs+k
                std     k,x
k               set     k+2
                endm
                rts

; guard_update: the guard in gs, one frame
guard_update:
                ldaa    gs_st
                cmpa    #GS_TRAP
                bne     gd_f0
                dec     gs_tt           ; trapped: wait, then climb out
                bne     gd_r0
                ldaa    gs_r
                deca
                ldab    gs_c
                jsr     cell_at
                jsr     is_solid
                beq     gd_trapmore
                ldaa    gs_r
                deca
                ldab    gs_c
                jsr     guard_in        ; (another guard there: wait)
                bne     gd_trapmore
                clr     gs_st
                dec     gs_r
                inc     gs_climbed      ; (then a step off to the side)
                ldaa    #D_UP
                staa    gs_dir
                ldaa    #G_CLIMB
                staa    gs_t
gd_r0:          rts
gd_trapmore:    ldaa    #10
                staa    gs_tt
                rts
gd_f0:          tst     gs_carry        ; carrying: count down
                beq     gd_f00
                ldd     gs_ct
                beq     gd_f00
                subd    #1
                std     gs_ct
gd_f00:         tst     gs_t
                bne     gd_step
                jmp     gd_decide
gd_step:        ldab    gs_t            ; a step of the move
                ldaa    gs_dir
                beq     gd_snext        ; (standing: just waiting)
                cmpa    #D_LEFT
                bne     gd_s1
                ldx     #gwalktab
                abx
                ldaa    gs_x
                suba    0,x
                staa    gs_x
                bra     gd_snext
gd_s1:          cmpa    #D_RIGHT
                bne     gd_s2
                ldx     #gwalktab
                abx
                ldaa    gs_x
                adda    0,x
                staa    gs_x
                bra     gd_snext
gd_s2:          cmpa    #D_UP
                bne     gd_s3
                dec     gs_y
                bra     gd_snext
gd_s3:          inc     gs_y            ; down or falling: a row a frame
gd_snext:       dec     gs_t
                bne     gd_r1
                jmp     gd_decide       ; there: decide at once
gd_r1:          rts

gwalktab:       fcb     0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 0 ; by frames left: 4 pixels

; gd_decide: the guard is on a cell (gs_r, gs_c): his next move
gd_decide:
                clr     gs_dir
                clr     gs_on
                ldaa    gs_r            ; a geode here: his
                ldab    gs_c
                jsr     cell_at
                staa    gd_here
                cmpa    #C_GEODE
                bne     gd_f1
                tst     gs_carry
                bne     gd_f1
                jsr     gd_cellp
                clr     0,x
                ldaa    gs_r
                ldab    gs_c
                jsr     draw_cell
                jsr     gd_redraw
                inc     gs_carry
                ldd     #CARRY_T
                std     gs_ct
                clr     gd_here
gd_f1:          tst     gs_climbed      ; just out of a hole: step off it,
                beq     gd_f1b          ; toward the hero (or where he can)
                clr     gs_climbed
                ldaa    h_c
                cmpa    gs_c
                bne     gd_o1
                ldaa    gs_c            ; (the hero right above or below:
                inca                    ; either side)
gd_o1:          staa    gd_goal
                jsr     gd_toward
                tst     gs_dir
                bne     gd_o2
                ldaa    gs_c            ; that way's blocked: the other
                asla
                suba    gd_goal
                staa    gd_goal
                jsr     gd_toward
gd_o2:          rts
gd_f1b:         jsr     hole_open       ; in a hole the hero dug: trapped
                bne     gd_f2
                jmp     gd_trap
gd_f2:          ldaa    gd_here         ; held up?
                cmpa    #C_LADDER
                beq     gd_ladder
                cmpa    #C_CABLE
                beq     gd_cable
                ldaa    gs_r
                inca
                ldab    gs_c
                jsr     cell_at
                staa    gd_below
                cmpa    #C_LADDER
                beq     gd_held
                jsr     is_solid
                beq     gd_held
                ldaa    gs_r            ; (on a trapped guard's head)
                inca
                ldab    gs_c
                jsr     trapped_in
                beq     gd_held
                jmp     gd_fall
gd_ladder:      ldaa    #1
                bra     gd_on
gd_cable:       ldaa    #2
gd_on:          staa    gs_on
                ldaa    gs_r
                inca
                ldab    gs_c
                jsr     cell_at
                staa    gd_below
gd_held:        tst     gs_carry        ; carried long enough: put it down
                beq     gd_think        ; here if it can rest here
                ldd     gs_ct
                bne     gd_think
                tst     gs_on
                bne     gd_think
                ldaa    gd_here
                bne     gd_think
                jsr     gd_cellp
                ldaa    #C_GEODE
                staa    0,x
                ldaa    gs_r
                ldab    gs_c
                jsr     draw_cell
                jsr     gd_redraw
                clr     gs_carry
; tracking the hero
gd_think:       ldaa    h_r
                cmpa    gs_r
                beq     gd_level
                bcc     gd_below_h
; the hero is higher: up
                ldaa    gd_here         ; on a ladder going up: climb
                cmpa    #C_LADDER
                bne     gd_u1
                ldaa    gs_r
                deca
                ldab    gs_c
                jsr     gd_free
                bne     gd_u1
                jmp     gd_up
gd_u1:          ldaa    #1              ; the nearest ladder up on this floor
                jsr     gd_scan
                jmp     gd_toward
; the hero is lower: down
gd_below_h:     ldaa    gd_below        ; a ladder below: down it
                cmpa    #C_LADDER
                bne     gd_d1
                ldaa    gs_r
                inca
                ldab    gs_c
                jsr     gd_free
                bne     gd_d1
                jmp     gd_down
gd_d1:          tst     gs_on           ; on a ladder or cable over air: drop
                beq     gd_d2
                ldaa    gd_below
                jsr     is_solid
                beq     gd_d2
                ldaa    gs_r
                inca
                ldab    gs_c
                jsr     guard_in
                bne     gd_d2
                jmp     gd_fall
gd_d2:          ldaa    #2              ; the nearest way down on this floor
                jsr     gd_scan
                jmp     gd_toward
; the hero is on this row: straight at him
gd_level:       ldaa    h_c
                staa    gd_goal
; gd_toward: walk toward column gd_goal (if a step there is free)
gd_toward:      ldaa    gd_goal
                cmpa    gs_c
                beq     gd_stand
                bcs     gd_tl
                ldaa    gs_r            ; right
                ldab    gs_c
                incb
                jsr     gd_free
                bne     gd_stand
                inc     gs_c
                clr     gs_face
                ldaa    #D_RIGHT
                bra     gd_walk
gd_tl:          ldaa    gs_r            ; left
                ldab    gs_c
                decb
                jsr     gd_free
                bne     gd_stand
                dec     gs_c
                ldaa    #1
                staa    gs_face
                ldaa    #D_LEFT
gd_walk:        staa    gs_dir
                ldaa    #G_WALK
                staa    gs_t
                rts
gd_stand:       clr     gs_dir          ; nothing to do: think again in a
                ldaa    #6              ; few frames
                staa    gs_t
                rts
gd_up:          dec     gs_r
                ldaa    #D_UP
                bra     gd_climb
gd_down:        inc     gs_r
                ldaa    #D_DOWN
gd_climb:       staa    gs_dir
                ldaa    #G_CLIMB
                staa    gs_t
                rts
gd_fall:        ldaa    gs_r            ; (onto another guard: wait)
                inca
                ldab    gs_c
                jsr     guard_in
                bne     gd_stand
                inc     gs_r
                ldaa    #D_FALL
                staa    gs_dir
                ldaa    #G_FALL
                staa    gs_t
                rts

; trapped in a hole: stop; any geode he carries goes into the cell above
gd_trap:        ldaa    #GS_TRAP
                staa    gs_st
                ldaa    #TRAP_T
                staa    gs_tt
                ldx     #fx_trap
                ldaa    #4
                jsr     snd_play
                ldd     #$0075
                jsr     score_add
                jsr     status_score
                tst     gs_carry
                beq     gt2_r
                clr     gs_carry
                ldaa    gs_r
                beq     gt2_r
                deca
                ldab    gs_c
                jsr     cell_at
                tsta                    ; (only into air)
                bne     gt2_r
                dec     gs_r
                jsr     gd_cellp
                inc     gs_r
                ldaa    #C_GEODE
                staa    0,x
                ldaa    gs_r
                deca
                ldab    gs_c
                jsr     draw_cell
                jsr     gd_redraw
gt2_r:          rts

; gd_scan: A = 1 to look for a way up, 2 for a way down: gd_goal = the
; column of the nearest one along his floor (walking: no wall, no gap in
; between), ties going toward the hero; none: the hero's column
gd_scan:
                staa    gd_want
                ldaa    gs_r            ; (his row's map bytes, for gd_way)
                ldab    #LV_COLS
                mul
                addd    #lv_map
                std     gd_rp
                ldaa    h_c
                staa    gd_goal
                ldaa    gs_c
                staa    gd_l
                staa    gd_rr
                ldaa    #1
                staa    gd_lok          ; (still looking left, right)
                staa    gd_rok
gsc_b1:         tst     gd_lok
                beq     gsc_f2
                dec     gd_l            ; one more to the left
                bmi     gsc_lno
                ldab    gd_l
                jsr     gd_way
                bcs     gsc_lno         ; (a wall or a gap: stop)
                bne     gsc_f2
                ldaa    gd_l            ; a way: but is the right one as near?
                staa    gd_goal
                tst     gd_rok
                beq     gsc_r
                ldab    gd_rr
                incb
                cmpb    #LV_COLS
                bcc     gsc_r
                jsr     gd_way
                bcs     gsc_r
                bne     gsc_r
                ldaa    h_c             ; both as near: toward the hero
                cmpa    gs_c
                bls     gsc_r
                ldaa    gd_rr
                inca
                staa    gd_goal
                rts
gsc_lno:        clr     gd_lok
gsc_f2:         tst     gd_rok
                beq     gsc_f3
                inc     gd_rr
                ldab    gd_rr
                cmpb    #LV_COLS
                bcc     gsc_rno
                jsr     gd_way
                bcs     gsc_rno
                bne     gsc_f3
                ldaa    gd_rr
                staa    gd_goal
gsc_r:          rts
gsc_rno:        clr     gd_rok
gsc_f3:         ldaa    gd_lok
                oraa    gd_rok
                bne     gsc_b1
                rts

; gd_way: B = a column on his row: carry set if he can't walk there (a
; wall, or he'd have fallen before it); else Z set if it's the way he
; wants (gd_want 1: a ladder going up there; 2: a way down there: ladder
; below, or no floor)
gd_way:
                stab    gd_wc
                ldx     gd_rp           ; (straight from the map: quick)
                abx
                ldaa    0,x
                cmpa    #C_EXIT         ; (the hidden exit: air)
                bne     gw_f1
                clra
gw_f1:          jsr     is_solid
                beq     gw_wall
                staa    gd_wh
                ldaa    #C_STONE        ; below (the bottom row: stone under it)
                ldab    gs_r
                cmpb    #LV_ROWS-1
                beq     gw_f2
                ldaa    LV_COLS,x
                cmpa    #C_EXIT
                bne     gw_f2
                clra
gw_f2:          staa    gd_wb
                ldaa    gd_want
                cmpa    #1
                bne     gw_down
                ldaa    gd_wh           ; up: a ladder here, air above it
                cmpa    #C_LADDER
                bne     gw_upf
                ldaa    gs_r
                deca
                ldab    gd_wc
                jsr     cell_at
                jsr     is_solid
                beq     gw_upf
                clc
                clra                    ; (Z)
                rts
gw_upf:         bsr     gw_floor        ; not here: can he walk on past it?
                bcs     gw_r
                clc
                ldaa    #1              ; (NZ)
gw_r:           rts
gw_down:        ldaa    gd_wb           ; down: a ladder below, or no floor
                cmpa    #C_LADDER
                beq     gw_yes
                ldaa    gd_wh
                cmpa    #C_CABLE
                beq     gw_cab
                cmpa    #C_LADDER
                beq     gw_no
                ldaa    gd_wb
                jsr     is_solid
                bne     gw_yes          ; (no floor: he'd drop: a way down)
gw_no:          clc
                ldaa    #1
                rts
gw_cab:         ldaa    gd_wb           ; a cable over air: let go
                jsr     is_solid
                beq     gw_no
gw_yes:         clc
                clra
                rts
gw_wall:        sec
                rts
gw_floor:                               ; walkable past: floor, ladder or cable
                ldaa    gd_wh
                cmpa    #C_LADDER
                beq     gwf_ok
                cmpa    #C_CABLE
                beq     gwf_ok
                ldaa    gd_wb
                cmpa    #C_LADDER
                beq     gwf_ok
                jsr     is_solid
                beq     gwf_ok
                sec
                rts
gwf_ok:         clc
                rts

; gd_free: A = row, B = column: Z set if the guard can move there (not a
; wall, no other guard there)
gd_free:
                std     gd_fr
                jsr     cell_at
                jsr     is_solid
                beq     gf_no
                ldd     gd_fr
                jsr     guard_in
                bne     gf_no
                clra
                rts
gf_no:          ldaa    #1
                rts

; guard_in: A = row, B = column: Z clear if another guard (not the one in
; gs) is on that cell or moving to it
guard_in:
                std     gd_fr
                ldx     #guards
                ldab    nguard
                beq     gi_none
gi_b1:          cpx     gu_p            ; (not himself)
                beq     gi_next
                ldaa    G_R,x
                cmpa    gd_fr
                bne     gi_next
                ldaa    G_C,x
                cmpa    gd_fr+1
                bne     gi_next
                ldaa    #1              ; (Z clear)
                rts
gi_next:        pshb
                ldab    #GD_SIZE
                abx
                pulb
                decb
                bne     gi_b1
gi_none:        clra
                rts

; trapped_in: A = row, B = column: Z set if a trapped guard is there
trapped_in:
                std     gd_fr
                ldx     #guards
                ldab    nguard
                beq     ti_no
ti_b1:          ldaa    G_ST,x
                cmpa    #GS_TRAP
                bne     ti_next
                ldaa    G_R,x
                cmpa    gd_fr
                bne     ti_next
                ldaa    G_C,x
                cmpa    gd_fr+1
                bne     ti_next
                clra                    ; (Z)
                rts
ti_next:        pshb
                ldab    #GD_SIZE
                abx
                pulb
                decb
                bne     ti_b1
ti_no:          ldaa    #1
                rts

; gd_cellp: X = the map byte of the guard's cell
gd_cellp:
                ldaa    gs_r
                ldab    #LV_COLS
                mul
                addb    gs_c
                adca    #0
                addd    #lv_map
                std     gd_m
                ldx     gd_m
                rts

; gd_redraw: have everyone redrawn over a changed cell (their patches)
gd_redraw:
                ldd     #0
                std     hero_a+A_OSPR
                std     gs+A_OSPR
                rts

; guard_pose: the guard in gs: falling, climbing (or on a cable, or
; trapped), walking (stride, legs together, facing his way), standing
guard_pose:
                ldx     #guard_f_hr
                ldaa    gs_dir
                cmpa    #D_FALL
                beq     gp_set
                clrb                    ; pose 0 in the first half of a move
                ldaa    gs_t
                cmpa    #G_WALK/2
                bhi     gp_f1
                ldab    #2
gp_f1:          tst     gs_t
                bne     gp_f2
                ldab    #2
gp_f2:          ldaa    gs_st
                bne     gp_climb        ; (trapped)
                ldaa    gs_dir
                cmpa    #D_UP
                beq     gp_climb
                cmpa    #D_DOWN
                beq     gp_climb
                tst     gs_t
                bne     gp_walk
                tst     gs_on
                beq     gp_walk
gp_climb:       ldx     #guard_c0
                bra     gp_pick
gp_walk:        ldx     #guard_r0
                tst     gs_face
                beq     gp_pick
                ldx     #guard_l0
gp_pick:        abx
                ldx     0,x
gp_set:         stx     gs_spr
                rts

guard_r0:       fdb     guard_r0_hr, guard_r1_hr
guard_l0:       fdb     guard_l0_hr, guard_l1_hr
guard_c0:       fdb     guard_c0_hr, guard_c1_hr

; guard_bury: A = row, B = column (a hole that just filled): a guard
; trapped there is buried: 75 points, and he comes back at the top
guard_bury:
                std     gd_fr
                ldx     #guards
                ldab    nguard
                beq     gb_r
gb_b1:          ldaa    G_ST,x
                cmpa    #GS_TRAP
                bne     gb_next
                ldaa    G_R,x
                cmpa    gd_fr
                bne     gb_next
                ldaa    G_C,x
                cmpa    gd_fr+1
                bne     gb_next
                pshb
                stx     gu_q
                bsr     guard_respawn
                ldx     #fx_bury
                ldaa    #5
                jsr     snd_play
                ldd     #$0075
                jsr     score_add
                jsr     status_score
                ldx     gu_q
                pulb
gb_next:        pshb
                ldab    #GD_SIZE
                abx
                pulb
                decb
                bne     gb_b1
gb_r:           rts

; guard_respawn: X = a guard: back at the top, at a random column of air
guard_respawn:
                stx     gu_q2
gr_b1:          jsr     rnd
                andb    #LV_COLS-1
                stab    gd_wc
                clra
                jsr     cell_at
                tsta
                bne     gr_b1
                ldx     gu_q2
                clr     G_R,x
                ldaa    gd_wc
                staa    G_C,x
                asla
                asla
                staa    A_X,x
                ldaa    #12
                staa    A_Y,x
                clr     G_T,x
                clr     G_DIR,x
                clr     G_ST,x
                clr     G_CARRY,x
                clr     G_ON,x
                clr     G_OUT,x
                ldd     #guard_f_hr
                std     A_SPR,x
                ldd     #0              ; (redraw where he was: his old place)
                std     A_OSPR,x
                rts

; rnd: B = a random byte (a 16-bit LFSR)
rnd:
                ldd     seed
                lsrd
                bcc     rnd_f1
                eora    #$B4
rnd_f1:         std     seed
                rts

; caught: Z clear if a free guard touches the hero (within a cell's width
; across and most of its height down)
caught:
                ldx     #guards
                ldab    nguard
                beq     cg_no
cg_b1:          ldaa    G_ST,x
                bne     cg_next         ; (trapped guards don't)
                ldaa    A_X,x
                suba    h_x
                bpl     cg_f1
                nega
cg_f1:          cmpa    #3
                bhi     cg_next
                ldaa    A_Y,x
                suba    h_y
                bpl     cg_f2
                nega
cg_f2:          cmpa    #8
                bhi     cg_next
                ldaa    #1
                rts
cg_next:        pshb
                ldab    #GD_SIZE
                abx
                pulb
                decb
                bne     cg_b1
cg_no:          clra
                rts
