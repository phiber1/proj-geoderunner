; title.inc: the title screen and its jingle
;
; title: GEODE in brick, RUNNER in ladders, the hero, a geode and a guard
; on a strip of floor, PRESS SPACE and the best score; the jingle plays as
; it appears (A, A, then A and C together), then SPACE starts a game.

JG_A4           equ     1869            ; (phase steps: f * 65536 * 58 / 894886,
JG_C5           equ     2223            ; the two-voice loop being 58 cycles)
JG_Q            equ     7715            ; loops: a quarter note at 120 a minute,
JG_E            equ     3857            ; ... an eighth,
JG_W            equ     30858           ; ... a whole note,
JG_GAP          equ     617             ; ... the gap between notes

title:
                jsr     gfx_cls
                ldx     #title_px       ; the big letters
tt_b1:          ldd     0,x
                addd    #1              ; (fdb $FFFF ends them)
                beq     tt_f1
                addd    #SCREEN-1
                std     tt_s
                ldab    2,x
                stx     tt_p
                ldx     #title_pat
                abx
                stx     tt_q
                ldab    #TITLE_PX_ROWS
tt_b2:          ldx     tt_q
                ldaa    0,x
                inx
                stx     tt_q
                ldx     tt_s
                staa    0,x
                ldx     tt_s
                pshb
                ldab    #ROW_BYTES
                abx
                pulb
                stx     tt_s
                decb
                bne     tt_b2
                ldx     tt_p
                inx
                inx
                inx
                bra     tt_b1
tt_f1:          ldaa    #4              ; a strip of floor: columns 4-27
                staa    tt_c
tt_b3:          ldab    tt_c
                ldx     #TXT_AT(124,0)
                abx
                ldaa    #T_BRICK
                jsr     tile_put
                inc     tt_c
                ldaa    tt_c
                cmpa    #28
                bne     tt_b3
                ldx     #TXT_AT(112,15) ; a geode on it,
                ldaa    #T_GEODE
                jsr     tile_put
                ldx     #TXT_AT(112,8)  ; the hero,
                jsr     hero_r0_hr0
                ldx     #TXT_AT(112,22) ; and a guard
                jsr     guard_l0_hr0
                ldaa    #COLOR_BYTE(CG_YELLOW)
                staa    txt_col
                ldx     #TXT_AT(146,10)
                ldd     #s_press
                jsr     txt_str2
                ldx     #TXT_AT(168,10)
                ldd     #s_high
                jsr     txt_str2
                ldx     #TXT_AT(168,15)
                jsr     hi_put
                jsr     jingle
tt_w1:          jsr     frame_wait      ; SPACE: up first, then down
                jsr     snd_frame
                jsr     kbd_read
                ldaa    joy
                bita    #J_FIRE
                bne     tt_w1
tt_w2:          jsr     frame_wait
                jsr     snd_frame
                jsr     kbd_read
                ldaa    joy
                bita    #J_FIRE
                beq     tt_w2
tt_r:           rts

; hi_put: X = where: the best score's six digits
hi_put:
                ldaa    hiscore
                jsr     sp_byte
                ldaa    hiscore+1
                jsr     sp_byte
                ldaa    hiscore+2
                jmp     sp_byte

; hi_check: the score a new best?  Then it's the best
hi_check:
                ldaa    score
                cmpa    hiscore
                bhi     hc_new
                bcs     hc_r
                ldaa    score+1
                cmpa    hiscore+1
                bhi     hc_new
                bcs     hc_r
                ldaa    score+2
                cmpa    hiscore+2
                bls     hc_r
hc_new:         ldd     score
                std     hiscore
                ldaa    score+2
                staa    hiscore+2
hc_r:           rts

; jingle: the notes in jg_tab, two voices at once (interrupts off: the
; loop alone drives the speaker)
jingle:
                sei
                ldaa    vdg_shadow      ; the VDG mode, the speaker bit clear
                anda    #~VDG_SND&$FF
                staa    jg_v
                ldx     #jg_tab
jg_b1:          stx     jg_p
                ldd     4,x             ; (0 loops: the end)
                beq     jg_end
                std     jg_n
                ldd     0,x
                std     jg_i1
                ldd     2,x
                std     jg_i2
                ldd     #0
                std     jg_a1
                std     jg_a2
                ldx     jg_n
                bsr     tone2
                ldx     jg_p
                ldab    #6
                abx
                bra     jg_b1
jg_end:         jsr     snd_stop
                cli
                rts

; tone2: X = loops: two square waves (the top bits of two phase counters),
; the speaker taking each in turn, 58 cycles a loop
tone2:
                ldd     jg_a1           ; 5
                addd    jg_i1           ; 6
                std     jg_a1           ; 5
                anda    #VDG_SND        ; 2
                oraa    jg_v            ; 4
                staa    VDG             ; 4
                ldd     jg_a2           ; 5
                addd    jg_i2           ; 6
                std     jg_a2           ; 5
                anda    #VDG_SND        ; 2
                oraa    jg_v            ; 4
                staa    VDG             ; 4
                dex                     ; 3
                bne     tone2           ; 3
                rts

jg_tab:         fdb     JG_A4, JG_A4, JG_Q      ; A (a quarter)
                fdb     0, 0, JG_GAP
                fdb     JG_A4, JG_A4, JG_E      ; A (an eighth)
                fdb     0, 0, JG_GAP
                fdb     JG_A4, JG_C5, JG_W      ; A and C (a whole note)
                fdb     0, 0, 0

s_press:        fcc     "PRESS SPACE"
                fcb     0
s_high:         fcc     "HIGH"
                fcb     0
