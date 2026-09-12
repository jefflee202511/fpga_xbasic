
REM ========================================
REM Module : led_blink_btn
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
COND2 = 0
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
            LED_02 = ON 
        else
            LED_02 = OFF
        endif
        DELAY 100
    else
        print "BTN1 off "
        LED_02 = OFF
        LED_01 = ON
        DELAY 200
        
        if COND2 == 1 then
            print "## LED 03 ON "
            LED_03 = ON
            COND2 = 0
        else
            print "##LED 03 OFF "
            LED_03 = OFF
            COND2 = 1
        endif
    
        
    endif
    


    
    
wend









