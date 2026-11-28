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

; frames to walk a cell, by level (the hero: 8); climbing takes 2 more
; (gu_walk, gu_climb, set by guards_speed).  One pace all through (owner:
; faster ones higher up were "like cockroaches", too fast for anyone):
; the challenge grows from more guards, harder levels and vaults instead
GSPEED_T:       fcb     255, 14
G_WALK          equ     14              ; (the slowest: for the poses' halves)
G_FALL          equ     14              ; ... fall one (the hero: 12)
TRAP_T          equ     210             ; frames stuck in a hole before climbing out
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
gs_acc          equ     gs+G_ACC

; guards_update: every guard, once a frame
guards_update:
                ldaa    #1              ; one guard may think a frame (thinking
                staa    gu_think        ; is costly: four at once missed a
                ldaa    frame_count     ; frame); this frame's half to redraw,
                staa    gu_par          ; fixed even if the frame runs late
                ldaa    nguard
                bne     gup_f0
                rts
; first every guard's move, always in the same order and never depending
; on the time (the game plays the same whatever the frame's timing: so a
; simulation of it, and a recorded solution, play out exactly)
gup_f0:         staa    gu_n
                ldx     #guards
gup_b1:         stx     gu_p
                ldaa    G_ST,x          ; in the middle of a move: the step,
                cmpa    #GS_TRAP        ; in place (most frames)
                beq     gup_s
                ldaa    G_T,x
                cmpa    #2
                bcs     gup_s
                PROF    $10
                jsr     gd_fast
                PROF    $11
                bra     gup_f1
gup_s:          jsr     gs_in           ; else the whole update
                PROF    $10
                jsr     guard_update
                PROF    $11
                ldx     gu_p
                jsr     gs_out
gup_f1:         ldx     gu_p
                ldab    #GD_SIZE
                abx
                dec     gu_n
                bne     gup_b1
; then the redraws (drawing changes nothing in the game): first those put
; off last frame (never twice: he'd jump when drawn at last), then each
; guard every other frame, half of them on each, while there's time
                ldaa    nguard
                staa    gu_n
                ldx     #guards
gup_a1:         ldaa    G_OWE,x
                beq     gup_a2
                stx     gu_p
                jsr     gup_draw
                ldx     gu_p
                ldaa    #2              ; (done this frame)
                staa    G_OWE,x
gup_a2:         ldab    #GD_SIZE
                abx
                dec     gu_n
                bne     gup_a1
                ldaa    nguard
                staa    gu_n
                ldx     #guards
gup_c1:         stx     gu_p
                ldaa    G_OWE,x
                beq     gup_c2
                clr     G_OWE,x         ; (drawn above)
                bra     gup_c4
gup_c2:         ldaa    gu_n
                eora    gu_par
                lsra
                bcs     gup_c4
                ldd     #FRAME_CYCLES-GU_DRAW_MAX ; time to draw him?  Else
                jsr     frame_left      ; first thing next frame
                ldx     gu_p
                bcs     gup_c3
                jsr     gup_draw
                bra     gup_c4
gup_c3:         ldaa    #1
                staa    G_OWE,x
gup_c4:         ldx     gu_p
                ldab    #GD_SIZE
                abx
                dec     gu_n
                bne     gup_c1
                rts

; gup_draw: X = gu_p = a guard: posed and redrawn
gup_draw:
                jsr     gs_in
                jsr     guard_pose
                ldx     gu_p
                jsr     gs_out
                PROF    $12
                ldx     gu_p
                jsr     act_update
                PROF    $13
                rts

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
                ldaa    gu_climb
                staa    gs_t
                clr     gs_acc
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
; a step of the move: the move's distance (4 pixels across, 12 rows down)
; spread evenly over its frames (an accumulator: a pixel whenever it
; passes the move's frame count)
gd_step:        ldaa    gs_dir
                beq     gd_snext        ; (standing: just waiting)
                cmpa    #D_LEFT
                beq     gd_sh
                cmpa    #D_RIGHT
                beq     gd_sh
                ldab    #G_FALL         ; up, down, falling: 12 rows (G_FALL frames)
                cmpa    #D_FALL
                beq     gd_sv
                ldab    gu_climb
gd_sv:          stab    gd_n
                ldaa    gs_acc
                adda    #12
                cmpa    gd_n
                bcs     gd_sk
                suba    gd_n
                staa    gs_acc
                ldaa    gs_dir
                cmpa    #D_UP
                bne     gd_s3
                dec     gs_y
                bra     gd_snext
gd_s3:          inc     gs_y
                bra     gd_snext
gd_sh:          ldaa    gs_acc          ; across: 4 pixels
                adda    #4
                cmpa    gu_walk
                bcs     gd_sk
                suba    gu_walk
                staa    gs_acc
                ldaa    gs_dir
                cmpa    #D_LEFT
                bne     gd_s1
                dec     gs_x
                bra     gd_snext
gd_s1:          inc     gs_x
                bra     gd_snext
gd_sk:          staa    gs_acc
gd_snext:       dec     gs_t
                bne     gd_r1
                jmp     gd_decide       ; there: decide at once
gd_r1:          rts

; frame_left: D = how far into the frame's work (cycles) something may
; start: carry set if it's later than that (the frame's work began at
; fr_t0; the rest of it, after the guards, is GU_TAIL)
GU_DRAW_MAX     equ     5000            ; (a guard's redraw, at most,
GU_TAIL         equ     900             ; ... the loop after the guards)
frame_left:
                subd    #GU_TAIL
                std     fl_lim
                ldd     FRC
                subd    fr_t0
                subd    fl_lim          ; elapsed - limit: a borrow, before it
                bcs     fl_ok
                sec
                rts
fl_ok:          clc
                rts

; gd_fast: X = a guard, free and two or more frames from the end of a
; move: this frame of it, in his record (as guard_update and gd_step do
; through gs, without the copying)
gd_fast:
                tst     G_CARRY,x       ; carrying: count down
                beq     gf_s
                ldd     G_CT,x
                beq     gf_s
                subd    #1
                std     G_CT,x
gf_s:           ldaa    G_DIR,x
                beq     gf_n            ; (standing: just waiting)
                cmpa    #D_LEFT
                beq     gf_h
                cmpa    #D_RIGHT
                beq     gf_h
                ldab    #G_FALL         ; up, down, falling: 12 rows (G_FALL frames)
                cmpa    #D_FALL
                beq     gf_v1
                ldab    gu_climb
gf_v1:          stab    gd_n
                ldaa    G_ACC,x
                adda    #12
                cmpa    gd_n
                bcs     gf_k
                suba    gd_n
                staa    G_ACC,x
                ldaa    G_DIR,x
                cmpa    #D_UP
                bne     gf_v2
                dec     A_Y,x
                bra     gf_n
gf_v2:          inc     A_Y,x
                bra     gf_n
gf_h:           ldaa    G_ACC,x         ; across: 4 pixels
                adda    #4
                cmpa    gu_walk
                bcs     gf_k
                suba    gu_walk
                staa    G_ACC,x
                ldaa    G_DIR,x
                cmpa    #D_LEFT
                bne     gf_h2
                dec     A_X,x
                bra     gf_n
gf_h2:          inc     A_X,x
                bra     gf_n
gf_k:           staa    G_ACC,x
gf_n:           dec     G_T,x
                rts

; guards_speed: this level's guard speeds
guards_speed:
                ldx     #GSPEED_T
gsp_b1:         ldaa    level
                cmpa    0,x
                bls     gsp_f1
                inx
                inx
                bra     gsp_b1
gsp_f1:         ldaa    1,x
                staa    gu_walk
                adda    #2
                staa    gu_climb
                rts

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
                jsr     guard_solid
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
gd_think:       tst     gu_think        ; another thought this frame: wait a
                bne     gd_th1          ; frame (still, at this cell)
                rts
gd_th1:         clr     gu_think
                jsr     gd_hrow         ; (a falling hero: where he'll land)
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
                jsr     guard_solid
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
                ldab    gs_c
                incb
                jsr     gd_inpath
                beq     gd_stand
                inc     gs_c
                clr     gs_face
                ldaa    #D_RIGHT
                bra     gd_walk
gd_tl:          ldaa    gs_r            ; left
                ldab    gs_c
                decb
                jsr     gd_free
                bne     gd_stand
                ldab    gs_c
                decb
                jsr     gd_inpath
                beq     gd_stand
                dec     gs_c
                ldaa    #1
                staa    gs_face
                ldaa    #D_LEFT
gd_walk:        staa    gs_dir
                ldaa    gu_walk
                staa    gs_t
                clr     gs_acc
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
                ldaa    gu_climb
                staa    gs_t
                clr     gs_acc
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
                clr     gs_acc
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

; gd_inpath: B = a column the guard would step into (on his row): Z set
; if the hero is falling down that column past the guard's row (from his
; row, a cell above, to where he'll land): a guard doesn't step out into a
; hero dropping past him
gd_inpath:
                ldaa    h_dir
                cmpa    #D_FALL
                bne     gip_no
                cmpb    h_c
                bne     gip_no
                ldaa    h_r             ; (h_r - 1) <= his row <= landing row
                deca
                cmpa    gs_r
                bgt     gip_no
                jsr     gd_hrow
                cmpa    gs_r
                blt     gip_no
                clra                    ; (Z)
                rts
gip_no:         ldaa    #1
                rts

; gd_hrow: A = the hero's row as the guards see it: his row, or while he
; falls the row he'll land on (so a guard doesn't step out at a hero
; dropping past him, as if he were on the guard's row for that moment)
gd_hrow:
                ldaa    h_r
                ldab    h_dir
                cmpb    #D_FALL
                bne     ghr_r
                staa    gd_hr
ghr_b1:         ldaa    gd_hr           ; held up here?  a ladder or cable,
                ldab    h_c
                jsr     cell_at
                cmpa    #C_LADDER
                beq     ghr_f1
                cmpa    #C_CABLE
                beq     ghr_f1
                ldaa    gd_hr           ; ... floor or ladder below
                inca
                ldab    h_c
                jsr     cell_at
                cmpa    #C_LADDER
                beq     ghr_f1
                jsr     is_solid
                beq     ghr_f1
                inc     gd_hr
                ldaa    gd_hr
                cmpa    #LV_ROWS-1
                bcs     ghr_b1
ghr_f1:         ldaa    gd_hr
ghr_r:          rts

; gd_scan: A = 1 to look for a way up, 2 for a way down: gd_goal = the
; column of the nearest one along his floor (walking: no wall, no gap in
; between), ties going toward the hero; none: the hero's column
gd_scan:
                staa    gd_want
                ldaa    gs_r            ; (his row in the way table, for gd_way)
                ldab    #LV_COLS
                mul
                addd    #waytab
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
                ldx     gd_rp           ; (from the way table: quick)
                abx
                ldaa    0,x
                bita    #W_WALL
                bne     gw_wall
                ldab    gd_want
                cmpb    #1
                bne     gw_down
                bita    #W_UP           ; up: a ladder here, air above it
                bne     gw_yes
                bita    #W_FLOOR        ; not here: can he walk on past it?
                beq     gw_wall
gw_no:          clc
                ldaa    #1              ; (NZ)
                rts
gw_down:        bita    #W_DOWN         ; down: a ladder below, or no floor
                beq     gw_no
gw_yes:         clc
                clra                    ; (Z)
                rts
gw_wall:        sec
                rts

; the way table (waytab: a byte a cell, kept by way_all and way_upd) for
; the guards' scans along a floor: W_WALL solid; W_UP a ladder with air
; above; W_FLOOR walkable past (floor, ladder or cable); W_DOWN a way
; down (a ladder below, a cable or nothing over air)
W_WALL          equ     1
W_UP            equ     2
W_FLOOR         equ     4
W_DOWN          equ     8

; way_all: the whole table (a level's start)
way_all:
                clr     wy_r
wa_b1:          clr     wy_c
wa_b2:          ldd     wy_r
                bsr     way_cell
                inc     wy_c
                ldaa    wy_c
                cmpa    #LV_COLS
                bne     wa_b2
                inc     wy_r
                ldaa    wy_r
                cmpa    #LV_ROWS
                bne     wa_b1
                rts

; way_upd: A = row, B = column: that cell changed: it and the ones above
; and below it again
way_upd:
                std     wy_r
                tsta
                beq     wu_f1
                deca
                bsr     way_cell
wu_f1:          ldd     wy_r
                bsr     way_cell
                ldd     wy_r
                inca
                cmpa    #LV_ROWS
                bcc     wu_r
                bsr     way_cell
wu_r:           rts

; way_cell: A = row, B = column: its entry
way_cell:
                std     wy_rc
                jsr     cell_at         ; here (the hidden exit: air)
                staa    wy_h
                ldaa    wy_rc           ; below (under the bottom row: stone)
                ldab    #C_STONE
                cmpa    #LV_ROWS-1
                beq     wc_f1
                inca
                ldab    wy_rc+1
                jsr     cell_at
                tab
wc_f1:          stab    wy_b
                clr     wy_v
                ldaa    wy_h
                jsr     is_solid
                bne     wc_f2
                ldaa    #W_WALL
                bra     wc_set
wc_f2:          ldaa    wy_h            ; W_UP: a ladder, air above
                cmpa    #C_LADDER
                bne     wc_f3
                ldaa    wy_rc
                deca
                ldab    wy_rc+1
                jsr     cell_at
                jsr     is_solid
                beq     wc_f3
                ldaa    #W_UP
                staa    wy_v
wc_f3:          ldaa    wy_h            ; W_FLOOR: a ladder or cable here, a
                cmpa    #C_LADDER       ; ladder below, or floor below
                beq     wc_fl
                cmpa    #C_CABLE
                beq     wc_fl
                ldaa    wy_b
                cmpa    #C_LADDER
                beq     wc_fl
                jsr     guard_solid
                bne     wc_f4
wc_fl:          ldaa    wy_v
                oraa    #W_FLOOR
                staa    wy_v
wc_f4:          ldaa    wy_b            ; W_DOWN: a ladder below; else on a
                cmpa    #C_LADDER       ; ladder no; else (a cable, or air)
                beq     wc_dn           ; nothing holding him up below
                ldaa    wy_h
                cmpa    #C_LADDER
                beq     wc_f5
                ldaa    wy_b
                jsr     guard_solid
                beq     wc_f5
wc_dn:          ldaa    wy_v
                oraa    #W_DOWN
                staa    wy_v
wc_f5:          ldaa    wy_v
wc_set:         psha
                ldaa    wy_rc
                ldab    #LV_COLS
                mul
                addb    wy_rc+1
                adca    #0
                addd    #waytab
                std     wy_p
                ldx     wy_p
                pula
                staa    0,x
                rts

; guard_solid: A = a code: Z set if it holds a guard up: as is_solid, and
; a hole that's closing (guards don't fall into one: they wait for it)
guard_solid:
                cmpa    #C_FILL1
                beq     gso_r
                cmpa    #C_FILL2
                beq     gso_r
                jmp     is_solid
gso_r:          rts

; gd_free: A = row, B = column: Z set if the guard can move there (not a
; wall, not over a closing hole, no other guard there)
gd_free:
                std     gd_fr
                jsr     cell_at
                jsr     is_solid
                beq     gf_no
                ldaa    gd_fr           ; (over a hole that's closing: he waits
                inca                    ; for it to close)
                ldab    gd_fr+1
                jsr     cell_at
                cmpa    #C_FILL1
                beq     gf_no
                cmpa    #C_FILL2
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

; head_in: A = row, B = column: Z set if a guard is there (on that cell,
; or moving to it): one the hero can stand on
head_in:
                std     gd_fr
                ldx     #guards
                ldab    nguard
                beq     hdi_no
hdi_b1:         ldaa    G_R,x
                cmpa    gd_fr
                bne     hdi_next
                ldaa    G_C,x
                cmpa    gd_fr+1
                bne     hdi_next
                clra                    ; (Z)
                rts
hdi_next:       pshb
                ldab    #GD_SIZE
                abx
                pulb
                decb
                bne     hdi_b1
hdi_no:         ldaa    #1
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

; gd_redraw: have them redrawn over the cell just drawn (draw_cell's
; dc_r, dc_c): the hero, and any guard over it or near it (a guard is wider
; than a cell: one standing still there, trapped in a pit say, was left
; with a strip of him wiped).  (Near: within a guard's width across, two
; rows up or down: a hole's cells above and below.)
gd_redraw:
                pshx
                ldd     #0
                std     hero_a+A_OSPR
                ldaa    dc_r            ; the cell's place, as an actor's
                inca
                ldab    #12
                mul
                stab    gr_y
                ldaa    dc_c
                lsla
                lsla
                staa    gr_x
                ldx     #gs
                bsr     gr_near
                ldx     #guards
                ldab    nguard
                beq     gdr_r
gdr_b:          pshb
                bsr     gr_near
                ldab    #GD_SIZE
                abx
                pulb
                decb
                bne     gdr_b
gdr_r:          pulx
                rts
gr_near:        ldaa    A_X,x
                suba    gr_x
                bpl     grn_f1
                nega
grn_f1:         cmpa    #9
                bcc     grn_r
                ldaa    A_Y,x
                suba    gr_y
                bpl     grn_f2
                nega
grn_f2:         cmpa    #25
                bcc     grn_r
                clr     A_OSPR,x        ; (a pose no one has: redraw him)
                clr     A_OSPR+1,x
grn_r:          rts

; guard_pose: the guard in gs: falling, on a cable (hand over hand),
; climbing (or trapped), walking (stride, legs together, facing his way), standing
guard_pose:
                ldx     #guard_f_hr
                ldaa    gs_dir
                cmpa    #D_FALL
                beq     gp_set
                clrb                    ; pose 0 in the first half of a move
                ldaa    gs_t            ; (the first half of the move)
                lsla
                cmpa    gu_walk
                bhi     gp_f1
                ldab    #2
gp_f1:          tst     gs_t
                bne     gp_f2
                ldab    #2
gp_f2:          ldaa    gs_st
                bne     gp_climb        ; (trapped)
                ldaa    gs_on           ; on a cable: hand over hand
                cmpa    #2
                bne     gp_f3
                ldx     #guard_h0
                bra     gp_pick
gp_f3:
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
guard_h0:       fdb     guard_h0_hr, guard_h1_hr

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

; caught: Z clear if a guard touches the hero (within a cell's width
; across and most of its height down)
caught:
                ldx     #guards
                ldab    nguard
                beq     cg_no
cg_b1:          ldaa    #3              ; (a trapped guard: in the hole beside
                tst     G_ST,x          ; his, a cell across, is touching him
                beq     cg_f0           ; too: the owner; standing on his head
                inca                    ; is a cell above, out of reach)
cg_f0:          staa    cg_lim
                ldaa    A_X,x
                suba    h_x
                bpl     cg_f1
                nega
cg_f1:          cmpa    cg_lim
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
