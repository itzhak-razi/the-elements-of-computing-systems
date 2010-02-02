// This file is part of the materials accompanying the book 
// "The Elements of Computing Systems" by Nisan and Schocken, 
// MIT Press. Book site: www.idc.ac.il/tecs
// File name: projects/05/ComputerRect-external.tst

load Computer.hdl,
output-file ComputerRect-external.out,
compare-to ComputerRect-external.cmp,
output-list time%S1.4.1;

ROM32K load Rect.hack,

echo "A small rectangle should be drawn at the top left of the screen",


// draw a rectangle 16 pixels wide and 4 pixels long
set RAM16K[0] 4,
output;

repeat 63 {
    tick, tock, output;
}

