
REM ========================================
REM Module : led_btn
REM FPGA BASIC Program
REM ========================================

REM Write your FPGA BASIC code here.


REM LED2
PINMODE 27, OUTPUT
GPIOSET 27


while 1
    if BTN1 then
        print "test btn on"
        LED_02 = ON
        DELAY 200
    else
        print "BTN1 off "
        LED_02 = OFF
        DELAY 500
    endif
wend