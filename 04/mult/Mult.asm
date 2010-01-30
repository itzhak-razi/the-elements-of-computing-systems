  @INIT
  0;JMP

  @0
  D=A
  @R0
  M=D

  @2
  D=A
  @R1
  M=D

(INIT)
  @0
  D=A
  @R2
  M=D

(LOOP)
  @R0              // Break out of loop if R0 <= 0
  D=M
  @END
  D;JLE

  @R0              // R0--
  M=M-1

  @R1              // R2 += R1
  D=M
  @R2
  M=M+D

  @LOOP            // Repeat loop
  0;JMP

(END)
  @END
  0;JMP
