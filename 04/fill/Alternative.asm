// From http://github.com/mdm/tecs/blob/master/project%2004/fill/Fill.asm
// His solution is harder to follow due to lack of comments and named variables (addresses),
// but is more concise (27 instructions in CPU emulator, vs. my 33) and contains fewer label symbols
// (code sections).

(LOOP)
    @KBD
    D=M
    @DRAW
    D;JEQ
    D=0
    D=!D
(DRAW)
    @R0
    M=D
    @SCREEN
    D=A
    @8192
    D=D+A
    @R1
    M=D
(PIXELS)
    @SCREEN
    D=D-A
    @LOOP
    D;JEQ
    @R0
    D=M
    @R1
    M=M-1
    A=M
    M=D
    @R1
    D=M
    @PIXELS
    0;JMP
