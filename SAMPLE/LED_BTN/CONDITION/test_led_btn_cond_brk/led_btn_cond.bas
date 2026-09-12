
REM ========================================
REM Module : led_btn_cond
REM FPGA BASIC Program
REM ========================================

REM Write your FPGA BASIC code here.




REM LED3
PINMODE 26, OUTPUT
GPIOSET 26


REM LED2
PINMODE 27, OUTPUT
GPIOSET 27

REM LED1
PINMODE 23, OUTPUT
GPIOSET 23

COND = 0
while 1
    if BTN1 then
        print "test btn on"
        LED_02 = ON
        LED_01 = OFF
        if COND == 1 then
            COND = 0
        else
            COND = 1
        endif
        
        DELAY 100
        
        if COND == 0 then
            LED_03 = ON 
        else
            LED_03 = OFF
        endif
        DELAY 100
    else
        print "BTN1 off "
        LED_02 = OFF
        LED_01 = ON
        DELAY 200
        
    endif
wend