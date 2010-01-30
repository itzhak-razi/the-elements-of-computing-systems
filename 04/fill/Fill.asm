(READ_KEYBOARD)
  @KBD                  // D = key pressed
  D=M
  
  @PAINT_BLACK          // Paint black if key != 0
  D;JNE
  @PAINT_WHITE          // Paint white if key == 0
  0;JMP

(PAINT_WHITE)
  @colour
  M=0                   // For white, @colour == 0
  @PAINT_LOOP
  0;JMP
(PAINT_BLACK)
  @colour
  M=-1                  // For black, @colour == -1

(PAINT_LOOP)
  @8192                 // @counter = number of screen words =
  D=A                   //          = (2^9 rows)(2^8 columns) * (1 word)/(2^4 pixels)
  @counter              //          = 2^13 = 8192
  M=D

(PAINT_LOOP_BODY)
  @counter              // @counter <= 0, so screen fully painted -- return to reading keyboard input
  D=M
  @READ_KEYBOARD
  D;JLE                 

  @counter              // @counter--
  M=M-1

  D=M                   // @address = address of current block of pixels = @counter + @SCREEN
  @SCREEN
  D=A+D
  @address
  M=D

  @colour               // D = @colour
  D=M

  @address              // Change colour of block of pixels to @colour
  A=M
  M=D

  @PAINT_LOOP_BODY      // Repeat paint loop
  0;JMP
