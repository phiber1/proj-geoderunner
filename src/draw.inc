; draw.inc: drawing the level's cells, and moving actors without flicker.
;
; An actor (the hero, a guard) is a record: A_X, A_Y its place (its
; cell's left pixel and top row when on a cell), A_OX, A_OY where it was
; last drawn, A_SPR its pose (a sprite's draw table: spritec NAME_hr),
; A_OSPR the pose last drawn.
;
; act_update redraws an actor that moved or changed pose without ever
; leaving it missing: the patch of screen around its old and new places
; (4 bytes across, whole cell rows down) is built off screen, in the
; shadow buffer (the same 32-byte rows as the screen): the cells' tiles,
; then every actor over the patch (guards, then the hero), then copied
; to the screen in one pass, every byte going straight from the old
; picture to the new one.

; (A_*, SH_* are defined in geode.asm, before the variables)
SH_TOP          equ     shadow+SH_MARGIN*ROW_BYTES

; cell_tile: A = row, B = column: A = that cell's tile (brick is worked out
; from its neighbours: on top of more brick, under brick, or alone)
cell_tile:
                staa    dc_r
                stab    dc_c
                ldab    #LV_COLS
                mul
                addb    dc_c
                adca    #0
                addd    #lv_map
                std     dc_m
                ldx     dc_m
                ldab    0,x
                cmpb    #C_BRICK
                beq     ct_brick
                ldx     #celltile
                abx
                ldaa    0,x
                rts
ct_brick:       ldaa    #T_BRICK_TOP    ; (the bottom row: solid to the
                ldab    dc_r            ; bottom, so a hole there is deep
                cmpb    #LV_ROWS-1      ; enough to stand in)
                beq     ct_r
                ldab    LV_COLS,x
                cmpb    #C_BRICK
                beq     ct_r
ct_f1:          ldaa    #T_BRICK_LOW
                ldab    dc_r
                beq     ct_f2
                pshb                    ; (the cell above: X - 32)
                stx     dc_m
                ldd     dc_m
                subd    #LV_COLS
                std     dc_m
                pulb
                ldx     dc_m
                ldab    0,x
                ldaa    #T_BRICK_LOW
                cmpb    #C_BRICK
                beq     ct_r
ct_f2:          ldaa    #T_BRICK
ct_r:           rts

; tile_put: A = a tile, X = where (32-byte rows): draw it there (each
; tile is a compiled routine: tools/mktiles.py)
tile_put:
                stx     dc_s
                asla
                tab
                ldx     #tilerout
                abx
                ldx     0,x
                stx     tp_jmp+1
                ldx     dc_s
tp_jmp:         jmp     tile_put        ; (patched)

; draw_cell: A = row, B = column: draw that cell on the screen (and note
; its tile in tmap, for act_update)
draw_cell:
                jsr     cell_tile       ; (leaves dc_r, dc_c)
                staa    dc_tl
                ldaa    dc_r            ; tmap + row * 32 + column (not dc_m:
                ldab    #LV_COLS        ; cell_tile may leave it on the cell
                mul                     ; above)
                addb    dc_c
                adca    #0
                addd    #tmap
                std     dc_m
                ldx     dc_m
                ldaa    dc_tl
                staa    0,x
                ldx     #rowaddr        ; the row's start + the column
                ldab    dc_r
                aslb
                abx
                ldd     0,x
                addb    dc_c
                adca    #0
                std     dc_s
                ldx     dc_s
                ldaa    dc_tl
                jmp     tile_put

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

div12:                                  ; A = A / 12 (uses B)
                clrb
d12_b1:         cmpa    #12
                bcs     d12_r
                suba    #12
                incb
                bra     d12_b1
d12_r:          tba
                rts

; act_draw: X = an actor: draw it straight onto the screen (a level's start)
act_draw:
                stx     cp_a
                ldaa    A_X,x
                jsr     sprite_x
                ldab    A_Y,x
                ldx     A_SPR,x
                jsr     spr_art
                ldx     cp_a
                ldd     A_X,x           ; (now drawn as it is)
                std     A_OX,x
                ldd     A_SPR,x
                std     A_OSPR,x
                rts

; act_update: X = an actor: if it moved or changed pose, redraw its patch
act_update:
                ldd     A_X,x
                subd    A_OX,x
                bne     au_go
                ldd     A_SPR,x
                subd    A_OSPR,x
                bne     au_go
                rts
au_go:          stx     cp_a
                ldaa    A_OY,x          ; moved further than a step (a
                suba    A_Y,x           ; respawn)?  Then erase the old place
                bpl     au_t1           ; by itself: the patch must stay
                nega                    ; within the shadow
au_t1:          cmpa    #12
                bhi     au_tele
                ldaa    A_OX,x
                suba    A_X,x
                bpl     au_t2
                nega
au_t2:          cmpa    #4
                bls     au_go2
au_tele:        jsr     act_erase
                ldx     cp_a
au_go2:         ldaa    A_OX,x          ; the patch: the bytes the two places
                bsr     sprite_x        ; cover (2 to 4 across)
                staa    cp_t
                ldx     cp_a
                ldaa    A_X,x
                jsr     sprite_x
                staa    cp_sx
                cmpa    cp_t            ; (the right edge: the larger + 5)
                bcc     au_f0
                ldaa    cp_t
au_f0:          adda    #5
                lsra
                lsra
                staa    cp_w
                ldaa    cp_sx           ; (the left: the smaller)
                cmpa    cp_t
                bls     au_f1
                ldaa    cp_t
au_f1:          lsra
                lsra
                staa    cp_c
                ldaa    cp_w            ; width = right - left + 1
                suba    cp_c
                inca
                staa    cp_w
                ldx     cp_a            ; ... the cell rows both cover
                ldaa    A_OY,x
                cmpa    A_Y,x
                bls     au_f3
                ldaa    A_Y,x
au_f3:          staa    cp_y0           ; (the first row either covers)
                jsr     div12
                deca
                staa    cp_r0
                ldx     cp_a
                ldaa    A_OY,x
                cmpa    A_Y,x
                bcc     au_f4
                ldaa    A_Y,x
au_f4:          adda    #11
                staa    cp_y1           ; (... and the last)
                jsr     div12
                deca
                cmpa    #LV_ROWS-1
                bls     au_f5
                ldaa    #LV_ROWS-1
au_f5:          staa    cp_r1
                ldaa    cp_r0           ; its top row and height
                inca
                ldab    #12
                mul
                stab    cp_top
                ldaa    cp_r1
                suba    cp_r0
                inca
                ldab    #12
                mul
                stab    cp_n
                ldaa    cp_top          ; shadow origin: SH_TOP - top * 32
                ldab    #ROW_BYTES
                mul
                std     cp_t2
                ldd     #SH_TOP
                subd    cp_t2
                std     cp_org
; the cells' tiles into the shadow (from tmap)
                ldaa    cp_r0
                staa    cp_rr
                ldab    #LV_COLS
                mul
                addd    #tmap
                addb    cp_c
                adca    #0
                std     cp_tp
                ldd     #SH_TOP
                std     cp_rowd
au_b1:          clr     cp_k
au_b2:          ldx     cp_tp
                ldab    cp_k
                abx
                ldaa    0,x
                ldx     cp_rowd         ; (the shadow's columns are the screen's)
                ldab    cp_k
                addb    cp_c
                abx
                jsr     tile_put
                inc     cp_k
                ldaa    cp_k
                cmpa    cp_w
                bne     au_b2
                ldd     cp_rowd
                addd    #12*ROW_BYTES
                std     cp_rowd
                ldd     cp_tp
                addd    #LV_COLS
                std     cp_tp
                inc     cp_rr
                ldaa    cp_rr
                cmpa    cp_r1
                bls     au_b1
; every actor over the patch: the guards, then the hero
                ldaa    nguard
                staa    cp_g
                ldx     #guards
au_b3:          tst     cp_g
                beq     au_f6
                stx     cp_gp
                jsr     cp_actor
                ldx     cp_gp
                ldab    #GD_SIZE
                abx
                dec     cp_g
                bra     au_b3
au_f6:          ldx     #hero_a
                jsr     cp_actor
; the patch onto the screen, a row at a time (4 bytes): only the rows the
; actor covers, then or now (the rest of the patch is unchanged)
                ldaa    cp_y0           ; shadow: SH_TOP + (y0 - top) * 32 + c
                suba    cp_top
                ldab    #ROW_BYTES
                mul
                addd    #SH_TOP
                addb    cp_c
                adca    #0
                std     cp_src
                ldaa    cp_y0           ; screen: SCREEN + y0 * 32 + c
                ldab    #ROW_BYTES
                mul
                addd    #SCREEN
                addb    cp_c
                adca    #0
                std     cp_dst
                ldaa    cp_y1           ; rows: y1 - y0 + 1 (kept on the screen)
                cmpa    #191
                bls     au_f7
                ldaa    #191
au_f7:          suba    cp_y0
                inca
                staa    cp_k
                ldaa    cp_w            ; (a loop for each width)
                cmpa    #3
                bcs     au_c2
                beq     au_c3
au_c4:          ldx     cp_src          ; 4 bytes
                ldd     2,x
                std     cp_t2
                ldd     0,x
                ldx     cp_dst
                std     0,x
                ldd     cp_t2
                std     2,x
                bsr     au_next
                bne     au_c4
                bra     au_done
au_c3:          ldx     cp_src          ; 3 bytes
                ldaa    2,x
                staa    cp_t2
                ldd     0,x
                ldx     cp_dst
                std     0,x
                ldaa    cp_t2
                staa    2,x
                bsr     au_next
                bne     au_c3
                bra     au_done
au_c2:          ldx     cp_src          ; 2 bytes
                ldd     0,x
                ldx     cp_dst
                std     0,x
                bsr     au_next
                bne     au_c2
                bra     au_done
au_next:        ldd     cp_src          ; the next row: Z set when done
                addd    #ROW_BYTES
                std     cp_src
                ldd     cp_dst
                addd    #ROW_BYTES
                std     cp_dst
                dec     cp_k
                rts
au_done:
                ldx     cp_a            ; drawn as it is now
                ldd     A_X,x
                std     A_OX,x
                ldd     A_SPR,x
                std     A_OSPR,x
                rts

; act_erase: X = an actor: redraw the cells under where it was last drawn
; (and have everyone redrawn over them), and call that its old place now
act_erase:
                stx     cp_b
                ldaa    A_OX,x          ; columns: (sx) / 4 .. (sx + 5) / 4
                jsr     sprite_x
                staa    cp_t
                lsra
                lsra
                staa    ae_c0
                ldaa    cp_t
                adda    #5
                lsra
                lsra
                staa    ae_c1
                ldx     cp_b            ; rows: oy / 12 - 1 .. (oy + 11) / 12 - 1
                ldaa    A_OY,x
                jsr     div12
                deca
                staa    ae_r
                ldx     cp_b
                ldaa    A_OY,x
                adda    #11
                jsr     div12
                deca
                cmpa    #LV_ROWS-1
                bls     ae_f1
                ldaa    #LV_ROWS-1
ae_f1:          staa    ae_r1
ae_b1:          ldaa    ae_c0
                staa    ae_c
ae_b2:          ldaa    ae_r
                bmi     ae_f2
                ldab    ae_c
                jsr     draw_cell
ae_f2:          inc     ae_c
                ldaa    ae_c
                cmpa    ae_c1
                bls     ae_b2
                inc     ae_r
                ldaa    ae_r
                cmpa    ae_r1
                ble     ae_b1
                ldx     cp_b            ; now its old place is where it is
                ldd     A_X,x
                std     A_OX,x
                ldd     #0              ; (and everyone drawn again)
                std     hero_a+A_OSPR
                ldx     #guards
                ldab    nguard
                beq     ae_r0
ae_b3:          ldaa    #0
                staa    A_OSPR,x
                staa    A_OSPR+1,x
                pshb
                ldab    #GD_SIZE
                abx
                pulb
                decb
                bne     ae_b3
ae_r0:          rts

; cp_actor: X = an actor: if it overlaps the patch, draw it into the shadow
cp_actor:
                stx     cp_b
                ldaa    A_Y,x           ; rows: y + 11 >= top, y < top + n
                adda    #11
                cmpa    cp_top
                bcs     cpa_r
                ldaa    cp_top
                adda    cp_n
                cmpa    A_Y,x
                bls     cpa_r
                ldaa    A_X,x           ; columns: sx + 5 >= c*4, sx <= c*4+15
                jsr     sprite_x
                staa    cp_sx
                adda    #5
                ldab    cp_c            ; (the patch: c*4 .. (c+w)*4-1)
                aslb
                aslb
                stab    cp_t
                cmpa    cp_t
                bcs     cpa_r
                ldab    cp_c
                addb    cp_w
                aslb
                aslb
                decb
                cmpb    cp_sx
                bcs     cpa_r
                ldaa    A_Y,x           ; where: origin + y * 32 + sx / 4
                ldab    #ROW_BYTES
                mul
                addd    cp_org
                std     cp_t2
                ldab    cp_sx
                lsrb
                lsrb
                ldx     cp_t2
                abx
                stx     cp_t2
                ldx     cp_b            ; the pose's routine for sx & 3
                ldx     A_SPR,x
                ldab    cp_sx
                andb    #3
                aslb
                abx
                ldx     0,x
                stx     cpa_jsr+1
                ldx     cp_t2
cpa_jsr:        jsr     cpa_r           ; (patched)
cpa_r:          rts
