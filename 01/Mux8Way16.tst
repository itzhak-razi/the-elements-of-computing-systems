// This file is part of the materials accompanying the book 
// "The Elements of Computing Systems" by Nisan and Schocken, 
// MIT Press. Book site: www.idc.ac.il/tecs
// File name: projects/01/Mux8Way16.tst

load Mux8Way16.hdl,
output-file Mux8Way16.out,
compare-to Mux8Way16.cmp,
output-list a%B1.16.1 b%B1.16.1 c%B1.16.1 d%B1.16.1 e%B1.16.1 f%B1.16.1 g%B1.16.1 h%B1.16.1 sel%B1.3.1 out%B1.16.1;

set a %B0000000000000000,
set b %B0000000000000000,
set c %B0000000000000000,
set d %B0000000000000000,
set e %B0000000000000000,
set f %B0000000000000000,
set g %B0000000000000000,
set h %B0000000000000000,
set sel %B000,
eval,
output;

set sel %B001,
eval,
output;

set sel %B010,
eval,
output;

set sel %B011,
eval,
output;

set sel %B100,
eval,
output;

set sel %B101,
eval,
output;

set sel %B110,
eval,
output;

set sel %B111,
eval,
output;

set a %B0001001000110100,
set b %B0010001101000101,
set c %B0011010001010110,
set d %B0100010101100111,
set e %B0101011001111000,
set f %B0110011110001001,
set g %B0111100010011010,
set h %B1000100110101011,
set sel %B000,
eval,
output;

set sel %B001,
eval,
output;

set sel %B010,
eval,
output;

set sel %B011,
eval,
output;

set sel %B100,
eval,
output;

set sel %B101,
eval,
output;

set sel %B110,
eval,
output;

set sel %B111,
eval,
output;
