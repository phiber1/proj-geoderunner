; title.inc: the title screen and its jingle
;
; title: GEODE in brick, RUNNER in ladders, the hero, a geode and a guard
; on a strip of floor, PRESS SPACE and the best score; the jingle plays as
; it appears (A, A, then A and C together: quick, quicker, held), then
; SPACE starts a game.

JG_A4           equ     1869            ; (phase steps: f * 65536 * 58 / 894886,
JG_C5           equ     2223            ; the two-voice loop being 58 cycles)
JG_Q            equ     3857            ; loops (15,429 a second): the first A
JG_E            equ     1929            ; (0.25 s), the second (0.125 s), the
JG_W            equ     15429           ; chord (1 s: four beats of 0.25), the gap
JG_GAP          equ     463             ; between notes (0.03 s)

title:
                ldaa    #1              ; (a new game starts at level 1,
                staa    start_lv        ; unless MC10 and a level are typed)
                clr     chosen
                clr     ls_i
                ldaa    #$FF
                staa    ls_was
                jsr     gfx_cls
                ldx     #title_px       ; the big letters
tt_b1:          ldd     0,x
                addd    #1              ; (fdb $FFFF ends them)
                beq     tt_f1
                subd    #1
                std     tt_o
                ldab    2,x             ; (its pattern)
                stx     tt_p
                jsr     px_draw
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
                ldaa    #COLOR_BYTE(CG_RED)
                staa    txt_col
                ldx     #TXT_AT(184,9)  ; the maker, at the bottom
                ldd     #s_maker
                jsr     txt_str
                jsr     jingle
                clr     tw_on
                clr     tw_i
                ldaa    #TW_T
                staa    tw_t
tt_w1:          jsr     frame_wait      ; SPACE: up first, then down (the
                jsr     twinkle         ; geodes twinkling)
                jsr     ls_poll         ; (or MC10 and a level)
                bcs     tt_go
                jsr     kbd_read
                ldaa    joy
                bita    #J_FIRE
                bne     tt_w1
tt_w2:          jsr     frame_wait
                jsr     twinkle
                jsr     ls_poll
                bcs     tt_go
                jsr     kbd_read
                ldaa    joy
                bita    #J_FIRE
                beq     tt_w2
tt_go:          rts

; ls_poll: once a frame on the title: the keys M, C, 1, 0 typed in turn
; (the level select, the owner's hidden code) ask for a level, typed as
; three digits where PRESS SPACE was; C set: chosen (start_lv), the game
; starts there (and won't count for the best score)
ls_poll:
                bsr     ls_key
                cmpa    ls_was          ; (on the press)
                beq     lsp_no
                staa    ls_was
                cmpa    #$FF
                beq     lsp_no
                cmpa    ls_i            ; the next key of the code?
                bne     lsp_f1
                inc     ls_i
                ldab    ls_i
                cmpb    #4
                beq     lsp_sel
                bra     lsp_no
lsp_f1:          clr     ls_i            ; no: from the start (an M starts
                tsta                    ; it again)
                bne     lsp_no
                inc     ls_i
lsp_no:          clc
                rts
lsp_sel:         clr     ls_i
                ldaa    #COLOR_BYTE(CG_RED)
                staa    txt_col
                ldx     #TXT_AT(146,10)
                ldd     #s_level
                jsr     txt_str2
                ldx     #TXT_AT(146,16)
                jsr     read_level
                tstb
                beq     lsp_cancel
                stab    start_lv
                inc     chosen
                sec
                rts
lsp_cancel:      ldaa    #COLOR_BYTE(CG_YELLOW)
                staa    txt_col
                ldx     #TXT_AT(146,10)
                ldd     #s_press
                jsr     txt_str2
                ldaa    #$FF
                staa    ls_was
                clc
                rts

; ls_key: A = which of M, C, 1, 0 is down (0-3), $FF if none
ls_key:
                ldx     #ls_tab
                clrb
lk_b1:          ldaa    0,x             ; (its column, then its row)
                staa    P1DAT
                ldaa    KBD
                anda    1,x
                beq     lk_hit
                inx
                inx
                incb
                cmpb    #4
                bne     lk_b1
                ldab    #$FF
lk_hit:         ldaa    #$FF
                staa    P1DAT
                tba
                rts
ls_tab:         fcb     $FF-$20, $02    ; M: column 5, row 1
                fcb     $FF-$08, $01    ; C: column 3, row 0
                fcb     $FF-$02, $10    ; 1: column 1, row 4
                fcb     $FF-$01, $10    ; 0: column 0, row 4

; px_draw: a letter pixel: tt_o = its screen offset, B = its pattern's
; offset in title_pat
px_draw:
                ldx     #title_pat
                abx
                stx     tt_q
                ldd     tt_o
                addd    #SCREEN
                std     tt_s
                ldab    #TITLE_PX_ROWS
pd_b1:          ldx     tt_q
                ldaa    0,x
                inx
                stx     tt_q
                ldx     tt_s
                staa    0,x
                pshb
                ldab    #ROW_BYTES
                abx
                pulb
                stx     tt_s
                decb
                bne     pd_b1
                rts

; twinkle: once a frame on the title: every TW_T frames a geode in GEODE
; flashes, then the next (stepping on by 7 through them, so it moves about)
TW_T            equ     6
twinkle:
                dec     tw_t
                bne     tw_r
                ldaa    #TW_T
                staa    tw_t
                tst     tw_on
                beq     tw_f1
                clr     tw_on           ; the flash over: back to its geode
                bsr     tw_at
                ldab    2,x
                jmp     px_draw
tw_f1:          ldaa    tw_i            ; the next one flashes
                adda    #7
tw_b1:          cmpa    #TITLE_STUDS
                bcs     tw_f2
                suba    #TITLE_STUDS
                bra     tw_b1
tw_f2:          staa    tw_i
                inc     tw_on
                ldab    #TITLE_PX_ROWS*3
                bsr     tw_at
                ldab    #TITLE_PX_ROWS*3
                jmp     px_draw
tw_at:          ldx     #title_studs    ; X: the geode tw_i (3 bytes each),
                ldab    tw_i            ; tt_o: its screen offset
                abx
                abx
                abx
                ldd     0,x
                std     tt_o
tw_r:           rts

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
                tst     chosen          ; (a game from a chosen level: no)
                bne     hc_r
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
                ldx     #0              ; (no hook)
                stx     jg_hook
                ldx     #jg_tab
; jg_play: X = a tune (the voices' steps and loops a note), jg_hook a
; routine called after each note but the rests (the ending's dance)
jg_play:
                sei
                ldaa    vdg_shadow      ; the VDG mode, the speaker bit clear
                anda    #~VDG_SND&$FF
                staa    jg_v
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
                ldx     jg_hook
                beq     jg_f1
                ldd     jg_i1           ; (not after a rest)
                beq     jg_f1
                jsr     0,x
jg_f1:          ldx     jg_p
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

s_level:        fcc     "LEVEL      "   ; (as long as PRESS SPACE)
                fcb     0
s_press:        fcc     "PRESS SPACE"
                fcb     0
s_high:         fcc     "HIGH"
                fcb     0
s_maker:        fcc     "AN ABENE GAME"
                fcb     0
