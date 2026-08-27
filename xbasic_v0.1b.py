import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import re
import json
import subprocess
import shutil
import math


# =========================================================
# ICON
# =========================================================

icon_path = os.path.join(
    os.path.dirname(__file__),
    "ASSET",
    "xbasic.ico"
)


# =========================================================
# UART TX IP
# =========================================================

UART_TX_IP_SOURCE = r'''
// ========================================================
// xBASIC UART TX IP
// ========================================================
//
// Simple 8-bit UART transmitter
//
// Clock : parameter
// Baud  : parameter
//
// Format:
//   8 data bits
//   No parity
//   1 stop bit
//
// TX idle state = HIGH
//
// ========================================================

module uart_tx #(
    parameter integer CLK_FREQ  = 12000000,
    parameter integer BAUD_RATE = 115200
)(
    input  wire       clk,
    input  wire       rst,

    input  wire       start,
    input  wire [7:0] data,

    output reg        tx,
    output reg        busy
);

    localparam integer CLKS_PER_BIT =
        CLK_FREQ / BAUD_RATE;

    reg [31:0] clk_count;
    reg [3:0]  bit_index;
    reg [9:0]  tx_shift;

    always @(posedge clk) begin

        if (rst) begin

            tx        <= 1'b1;
            busy      <= 1'b0;
            clk_count <= 0;
            bit_index <= 0;
            tx_shift  <= 10'b1111111111;

        end else begin

            if (!busy) begin

                tx <= 1'b1;

                if (start) begin

                    tx_shift <= {
                        1'b1,
                        data,
                        1'b0
                    };

                    busy      <= 1'b1;
                    clk_count <= 0;
                    bit_index <= 0;

                    tx <= 1'b0;
                end

            end else begin

                if (clk_count >= CLKS_PER_BIT - 1) begin

                    clk_count <= 0;

                    if (bit_index == 9) begin

                        busy <= 1'b0;
                        tx   <= 1'b1;

                    end else begin

                        bit_index <= bit_index + 1'b1;

                        tx <= tx_shift[
                            bit_index + 1'b1
                        ];

                    end

                end else begin

                    clk_count <= clk_count + 1'b1;

                end
            end
        end
    end

endmodule
'''


# =========================================================
# IPLIB
# =========================================================

def ensure_uart_tx_ip(project_dir):

    iplib_dir = os.path.join(
        project_dir,
        "IPLIB"
    )

    os.makedirs(
        iplib_dir,
        exist_ok=True
    )

    uart_tx_file = os.path.join(
        iplib_dir,
        "uart_tx.v"
    )

    if os.path.isfile(uart_tx_file):
        return uart_tx_file

    with open(
        uart_tx_file,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            UART_TX_IP_SOURCE
        )

    return uart_tx_file


# =========================================================
# Project Source List
# =========================================================

def build_project_sources(
    project_dir,
    module_name,
    include_uart=True
):

    sources = [
        module_name + ".v"
    ]

    if include_uart:

        uart_file = os.path.join(
            project_dir,
            "IPLIB",
            "uart_tx.v"
        )

        if os.path.isfile(uart_file):

            sources.append(
                "IPLIB/uart_tx.v"
            )

    return sources


# =========================================================
# Verilog Name
# =========================================================

def to_verilog_name_static(name):

    name = re.sub(
        r'[^a-zA-Z0-9_]',
        '_',
        name
    )

    if name and name[0].isdigit():

        name = "_" + name

    return name


# =========================================================
# Condition Conversion
# =========================================================

def convert_condition_to_verilog(
    condition,
    button_symbols,
    active_low
):

    condition = condition.strip()

    # -----------------------------------------------------
    # Constant TRUE
    # -----------------------------------------------------

    if condition == "1":

        return "1'b1"

    # -----------------------------------------------------
    # Constant FALSE
    # -----------------------------------------------------

    if condition == "0":

        return "1'b0"

    # -----------------------------------------------------
    # BUTTON / BTN
    # -----------------------------------------------------

    if condition.upper() in (
        "BUTTON",
        "BTN"
    ):

        if "BUTTON" not in button_symbols:

            raise ValueError(
                "BUTTON/BTN 핀 정보가 없습니다."
            )

        if active_low:

            return "!BUTTON"

        return "BUTTON"

    # -----------------------------------------------------
    # BTN_01 / BTN_02 / BTN1 / BTN2
    #
    # NOTE:
    # SW[0]~SW[3] 자동 alias는 사용하지 않는다.
    # -----------------------------------------------------

    match = re.fullmatch(
        r"BTN[_\s]*0*(\d+)",
        condition,
        re.IGNORECASE
    )

    if match:

        number = int(
            match.group(1)
        )

        symbol = (
            f"BTN_{number:02d}"
        )

        if symbol.upper() not in button_symbols:

            raise ValueError(
                f"버튼 정보가 없습니다: {symbol}"
            )

        verilog_name = to_verilog_name_static(
            symbol
        )

        if active_low:

            return f"!{verilog_name}"

        return verilog_name

    raise ValueError(
        f"지원하지 않는 IF 조건입니다: {condition}"
    )


# =========================================================
# Generate Verilog / PCF
# =========================================================

# =========================================================
# BASIC expression helpers
#
# normalize_basic_operators : MOD/AND/OR/XOR/NOT -> % & | ^ ~
# fold_constant_expression  : evaluate a fully-constant
#                             expression at COMPILE TIME so that
#                             no divider / multiplier logic is
#                             emitted for it at all.
#
# Semantics are matched to the generated hardware:
#   - 32-bit signed wrap-around
#   - '/' and '%' truncate toward zero
#   - divide / modulo by zero yields 0 (same as the RTL divider)
# =========================================================


def wrap_int32(value):

    value &= 0xFFFFFFFF

    if value & 0x80000000:
        value -= 0x100000000

    return value


def normalize_basic_operators(expression):

    # XOR must be replaced before OR.
    replacements = (
        (r'\bMOD\b', ' % '),
        (r'\bAND\b', ' & '),
        (r'\bXOR\b', ' ^ '),
        (r'\bOR\b',  ' | '),
        (r'\bNOT\b', ' ~ '),
    )

    for pattern, symbol in replacements:

        expression = re.sub(
            pattern,
            symbol,
            expression,
            flags=re.IGNORECASE
        )

    return re.sub(r'\s+', ' ', expression).strip()


def fold_constant_expression(expression):
    """Return an int when every operand is a literal, else None."""

    tokens = re.findall(
        r'\d+|[()+\-*/%&^|~]',
        expression
    )

    if not tokens:
        return None

    # Any leftover character means an identifier is involved,
    # so the expression is not constant and must stay in RTL.
    if "".join(tokens) != re.sub(r'\s+', '', expression):
        return None

    position = [0]

    def peek():
        if position[0] < len(tokens):
            return tokens[position[0]]
        return None

    def take():
        token = tokens[position[0]]
        position[0] += 1
        return token

    def parse_unary():

        token = peek()

        if token == '-':
            take()
            return wrap_int32(-parse_unary())

        if token == '+':
            take()
            return parse_unary()

        if token == '~':
            take()
            return wrap_int32(~parse_unary())

        if token == '(':
            take()
            value = parse_or()
            if peek() != ')':
                raise ValueError("괄호가 닫히지 않았습니다.")
            take()
            return value

        if token is not None and token.isdigit():
            return wrap_int32(int(take()))

        raise ValueError("수식을 해석할 수 없습니다.")

    def parse_mul():

        value = parse_unary()

        while peek() in ('*', '/', '%'):

            operator = take()
            right = parse_unary()

            if operator == '*':
                value = wrap_int32(value * right)

            elif operator == '/':

                if right == 0:
                    value = 0
                else:
                    quotient = abs(value) // abs(right)
                    if (value < 0) != (right < 0):
                        quotient = -quotient
                    value = wrap_int32(quotient)

            else:

                if right == 0:
                    value = 0
                else:
                    remainder = abs(value) % abs(right)
                    if value < 0:
                        remainder = -remainder
                    value = wrap_int32(remainder)

        return value

    def parse_add():

        value = parse_mul()

        while peek() in ('+', '-'):
            operator = take()
            right = parse_mul()
            if operator == '+':
                value = wrap_int32(value + right)
            else:
                value = wrap_int32(value - right)

        return value

    def parse_and():

        value = parse_add()

        while peek() == '&':
            take()
            value = wrap_int32(value & parse_add())

        return value

    def parse_xor():

        value = parse_and()

        while peek() == '^':
            take()
            value = wrap_int32(value ^ parse_and())

        return value

    def parse_or():

        value = parse_xor()

        while peek() == '|':
            take()
            value = wrap_int32(value | parse_xor())

        return value

    result = parse_or()

    if position[0] != len(tokens):
        raise ValueError("수식을 해석할 수 없습니다.")

    return result


def generate_verilog_and_pcf(
    bas_file,
    board_name,
    BOARD_PINMAP,
    project_dir,
    project_name
):

    if board_name not in BOARD_PINMAP:

        raise ValueError(
            f"Unknown board: {board_name}"
        )

    board_map = BOARD_PINMAP[
        board_name
    ]

    # =====================================================
    # Active Low
    # =====================================================

    active_low = (
        "icesugar"
        in board_name.lower()
    )

    # =====================================================
    # BASIC
    # =====================================================

    with open(
        bas_file,
        "r",
        encoding="utf-8"
    ) as f:

        basic_code = f.read()

    # =====================================================
    # Reverse Pin Map
    # =====================================================

    reverse_pin_map = {}

    for category, pins in board_map.items():

        if not isinstance(pins, dict):
            continue

        for signal_name, pin_number in pins.items():

            if not isinstance(pin_number, int):
                continue

            if pin_number not in reverse_pin_map:

                reverse_pin_map[
                    pin_number
                ] = signal_name

    # =====================================================
    # Signal Name
    # =====================================================

    def get_signal_name(
        rem_text,
        pin_number
    ):

        if rem_text:

            led_match = re.search(
                r'\bLED\s*[_\s]*0*(\d+)\b',
                rem_text,
                re.IGNORECASE
            )

            if led_match:

                led_number = int(
                    led_match.group(1)
                )

                return (
                    f"LED_{led_number:02d}"
                )

        if pin_number in reverse_pin_map:

            signal_name = reverse_pin_map[
                pin_number
            ]

            return signal_name

        return (
            f"PIN_{pin_number}"
        )

    # =====================================================
    # Find Pin By Signal
    # =====================================================

    def find_pin_by_signal(
        signal_name
    ):

        target = signal_name.upper()

        # -------------------------------------------------
        # Existing parsed information first
        # -------------------------------------------------

        for pin_number, info in pin_info.items():

            if (
                info["signal_name"].upper()
                == target
            ):

                return pin_number

            if (
                info["verilog_name"].upper()
                == target
            ):

                return pin_number

        # -------------------------------------------------
        # BOARD PINMAP
        # -------------------------------------------------

        for category, pins in board_map.items():

            if not isinstance(pins, dict):
                continue

            for name, pin_number in pins.items():

                if name.upper() == target:

                    return pin_number

        return None

    # =====================================================
    # Resolve Button
    #
    # IMPORTANT:
    # SW[0]~SW[3] -> BTN1~BTN4
    # 자동 alias 제거
    # =====================================================

    def resolve_button(
        button_name
    ):

        name = (
            button_name.upper().strip()
        )

        # -------------------------------------------------
        # BUTTON / BTN
        # -------------------------------------------------

        if name in (
            "BUTTON",
            "BTN"
        ):

            pin = find_pin_by_signal(
                "BTN"
            )

            if pin is not None:
                return pin

            pin = find_pin_by_signal(
                "BUTTON"
            )

            if pin is not None:
                return pin

            return None

        # -------------------------------------------------
        # Numbered button
        #
        # SW[] fallback 제거
        # -------------------------------------------------

        match = re.fullmatch(
            r"BTN[_\s]*0*(\d+)",
            name,
            re.IGNORECASE
        )

        if not match:

            return None

        number = int(
            match.group(1)
        )

        candidates = [
            f"BTN{number}",
            f"BTN_{number:02d}",
        ]

        for candidate in candidates:

            pin = find_pin_by_signal(
                candidate
            )

            if pin is not None:

                return pin

        return None

    # =====================================================
    # Resolve LED
    # =====================================================

    def resolve_led(
        led_name
    ):

        target = led_name.upper().strip()

        # -------------------------------------------------
        # Exact existing information
        # -------------------------------------------------

        for pin_number, info in pin_info.items():

            signal_name = (
                info["signal_name"].upper()
            )

            verilog_name = (
                info["verilog_name"].upper()
            )

            if signal_name == target:

                return pin_number

            if verilog_name == target:

                return pin_number

        # -------------------------------------------------
        # LED number
        # -------------------------------------------------

        match = re.fullmatch(
            r"LED[_\s]*0*(\d+)",
            target,
            re.IGNORECASE
        )

        if not match:

            return None

        led_number = int(
            match.group(1)
        )

        expected = (
            f"LED_{led_number:02d}"
        )

        # -------------------------------------------------
        # Existing pin_info
        # -------------------------------------------------

        for pin_number, info in pin_info.items():

            if (
                info["verilog_name"].upper()
                == expected
            ):

                return pin_number

            if (
                info["signal_name"].upper()
                == expected
            ):

                return pin_number

        return None

    # =====================================================
    # BASIC Analysis
    # =====================================================

    pin_info = {}

    print_messages = []

    # Numeric BASIC variables used by arithmetic expressions.
    basic_variables = set()

    control_logic = []

    used_button_pins = {}

    used_led_pins = {}

    current_rem = None

    while_depth = 0
    if_depth = 0

    # -----------------------------------------------------
    # IF context
    #
    # PRINT가 어떤 IF 안에 있는지 기록한다.
    # -----------------------------------------------------

    if_context_stack = []  # stack entries: {"condition": str, "branch": "THEN"|"ELSE"}

    # =====================================================
    # First Pass
    # =====================================================

    for original_line in basic_code.splitlines():

        original_line = (
            original_line.strip()
        )

        if not original_line:
            continue

        # -------------------------------------------------
        # REM
        # -------------------------------------------------

        rem_match = re.match(
            r'^REM\s+(.*)',
            original_line,
            re.IGNORECASE
        )

        if rem_match:

            current_rem = (
                rem_match.group(1).strip()
            )

            continue

        # -------------------------------------------------
        # Inline REM
        # -------------------------------------------------

        line = re.split(
            r'\bREM\b',
            original_line,
            flags=re.IGNORECASE
        )[0].strip()

        if not line:
            continue

        # -------------------------------------------------
        # PRINT
        #
        # 버튼 IF 내부에 있는 PRINT는
        # 해당 버튼의 Rising Edge에서만 실행된다.
        # -------------------------------------------------

        match = re.match(
            r'^PRINT\s+"([^"]*)"\s*$',
            line,
            re.IGNORECASE
        )

        if match:

            message = match.group(1)

            print_messages.append(
                message
            )

            trigger_condition = None
            trigger_branch = None

            if if_context_stack:
                ctx = if_context_stack[-1]
                trigger_condition = ctx["condition"]
                trigger_branch = ctx["branch"]

            control_logic.append({
                "type": "PRINT",
                "message": message,
                "message_id": len(print_messages) - 1,
                "trigger_condition": trigger_condition,
                "trigger_branch": trigger_branch
            })

            current_rem = None

            continue

        # -------------------------------------------------
        # PRINT Numeric Variable
        #
        # Example:
        #   PRINT A
        # -------------------------------------------------

        match = re.match(
            r'^PRINT\s+([A-Za-z_][A-Za-z0-9_]*)\s*$',
            line,
            re.IGNORECASE
        )

        if match:

            variable_name = match.group(1)

            basic_variables.add(variable_name.upper())

            trigger_condition = None
            trigger_branch = None

            if if_context_stack:
                ctx = if_context_stack[-1]
                trigger_condition = ctx["condition"]
                trigger_branch = ctx["branch"]

            control_logic.append({
                "type": "PRINT_VALUE",
                "variable": variable_name,
                "trigger_condition": trigger_condition,
                "trigger_branch": trigger_branch
            })

            current_rem = None

            continue

        # -------------------------------------------------
        # Numeric Assignment / Arithmetic
        #
        # Examples:
        #   A = 10
        #   A = 10 + 20
        #   A = B - 5
        #   A = A * B
        #   A = A / 2
        # -------------------------------------------------

        match = re.match(
            r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$',
            line,
            re.IGNORECASE
        )

        if match:

            target = match.group(1)
            expression = match.group(2).strip()

            # Do not consume existing hardware ON/OFF assignments.
            if not re.fullmatch(r'(ON|OFF)', expression, re.IGNORECASE):

                # Numbers, identifiers, whitespace and
                # + - * / % ( ) & | ^ ~  plus the BASIC word
                # operators MOD / AND / OR / XOR / NOT.
                if re.fullmatch(
                    r'[A-Za-z0-9_\s+\-*/%()&|^~]+',
                    expression
                ):

                    # MOD/AND/OR/XOR/NOT -> % & | ^ ~
                    # Verilog operator precedence already matches
                    # BASIC here: * / % > + - > & > ^ > |
                    expression = normalize_basic_operators(
                        expression
                    )

                    identifiers = re.findall(
                        r'[A-Za-z_][A-Za-z0-9_]*',
                        expression
                    )

                    # Numeric BASIC variables cannot contain BASIC keywords.
                    invalid = [
                        name for name in identifiers
                        if name.upper() in ("ON", "OFF")
                    ]

                    if not invalid:

                        # -------------------------------------------
                        # Division
                        #
                        # A 32-bit divide cannot settle inside one
                        # clock, so it is not emitted inline. It runs
                        # on the sequential shift-subtract divider and
                        # the FSM waits for the result.
                        #
                        # Only a whole-expression divide is accepted:
                        #   C = A / B
                        #   C = A / 4
                        # Anything else (A / B + 1, A / B / C) would
                        # need a temporary, so it is rejected loudly
                        # instead of generating logic that fails
                        # timing.
                        # -------------------------------------------

                        divide_operands = None

                        # -------------------------------------------
                        # Constant folding
                        #
                        # 'C = 10 / 20 OR 20 / 10' has no variables,
                        # so it is computed here and becomes a plain
                        # literal. No divider, no multiplier and no
                        # timing risk is emitted for it.
                        # -------------------------------------------

                        folded = fold_constant_expression(
                            expression
                        )

                        if folded is not None:
                            expression = str(folded)

                        if "/" in expression:

                            divide_match = re.fullmatch(
                                r'\s*([A-Za-z_][A-Za-z0-9_]*|\d+)'
                                r'\s*/\s*'
                                r'([A-Za-z_][A-Za-z0-9_]*|\d+)\s*',
                                expression
                            )

                            if not divide_match:

                                raise ValueError(
                                    f"나눗셈은 '변수 = 값 / 값' 형태만 "
                                    f"지원합니다: {target} = {expression}\n\n"
                                    f"나눗셈은 순차 divider에서 32클럭에 "
                                    f"걸쳐 계산되므로\n"
                                    f"다른 연산과 한 줄에 섞을 수 없습니다.\n\n"
                                    f"예) T = A / B\n"
                                    f"    C = T + 1"
                                )

                            divide_operands = (
                                divide_match.group(1),
                                divide_match.group(2)
                            )

                        basic_variables.add(target.upper())

                        for name in identifiers:
                            basic_variables.add(name.upper())

                        control_logic.append({
                            "type": "CALC_ASSIGN",
                            "target": target,
                            "expression": expression,
                            "divide": divide_operands
                        })

                        current_rem = None

                        continue

        # -------------------------------------------------
        # PINMODE
        # -------------------------------------------------

        match = re.match(
            r'^PINMODE\s+(\d+)\s*,\s*(OUTPUT|INPUT)\s*$',
            line,
            re.IGNORECASE
        )

        if match:

            pin_number = int(
                match.group(1)
            )

            mode = (
                match.group(2).upper()
            )

            signal_name = get_signal_name(
                current_rem,
                pin_number
            )

            verilog_name = (
                to_verilog_name_static(
                    signal_name
                )
            )

            pin_info[
                pin_number
            ] = {

                "signal_name":
                    signal_name,

                "verilog_name":
                    verilog_name,

                "mode":
                    mode,

                "state":
                    None
            }

            current_rem = None

            continue

        # -------------------------------------------------
        # GPIOSET
        # -------------------------------------------------

        match = re.match(
            r'^GPIOSET\s+(\d+)',
            line,
            re.IGNORECASE
        )

        if match:

            pin_number = int(
                match.group(1)
            )

            if pin_number in pin_info:

                pin_info[
                    pin_number
                ]["state"] = "SET"

            continue

        # -------------------------------------------------
        # GPIOCLR
        # -------------------------------------------------

        match = re.match(
            r'^GPIOCLR\s+(\d+)',
            line,
            re.IGNORECASE
        )

        if match:

            pin_number = int(
                match.group(1)
            )

            if pin_number in pin_info:

                pin_info[
                    pin_number
                ]["state"] = "CLR"

            continue

        # -------------------------------------------------
        # WHILE
        # -------------------------------------------------

        match = re.match(
            r'^WHILE\s+(.+)$',
            line,
            re.IGNORECASE
        )

        if match:

            condition = (
                match.group(1).strip()
            )

            if condition != "1":

                raise ValueError(
                    "현재 WHILE은 WHILE 1만 지원합니다."
                )

            control_logic.append({
                "type":
                    "WHILE",

                "condition":
                    condition
            })

            while_depth += 1

            current_rem = None

            continue

        # -------------------------------------------------
        # WEND
        # -------------------------------------------------

        if re.match(
            r'^WEND\b',
            line,
            re.IGNORECASE
        ):

            if while_depth <= 0:

                raise ValueError(
                    "WEND에 대응하는 WHILE이 없습니다."
                )

            control_logic.append({
                "type":
                    "WEND"
            })

            while_depth -= 1

            current_rem = None

            continue

        # -------------------------------------------------
        # IF
        # -------------------------------------------------

        match = re.match(
            r'^IF\s+(.+?)\s+THEN$',
            line,
            re.IGNORECASE
        )

        if match:

            condition = (
                match.group(1).strip()
            )

            # ---------------------------------------------
            # Button detection
            # ---------------------------------------------

            button_match = re.fullmatch(
                r'(BUTTON|BTN|BTN[_\s]*0*\d+)',
                condition,
                re.IGNORECASE
            )

            if button_match:

                button_name = (
                    button_match.group(1)
                )

                button_pin = resolve_button(
                    button_name
                )

                if button_pin is None:

                    raise ValueError(
                        f"버튼 핀맵을 찾을 수 없습니다: "
                        f"{button_name}\n\n"
                        f"BOARD_PINMAP에 해당 버튼을 추가하세요."
                    )

                if button_name.upper() in (
                    "BUTTON",
                    "BTN"
                ):

                    used_button_pins[
                        "BUTTON"
                    ] = button_pin

                else:

                    match_number = re.fullmatch(
                        r'BTN[_\s]*0*(\d+)',
                        button_name,
                        re.IGNORECASE
                    )

                    if match_number:

                        number = int(
                            match_number.group(1)
                        )

                        symbol = (
                            f"BTN_{number:02d}"
                        )

                        used_button_pins[
                            symbol.upper()
                        ] = button_pin

            control_logic.append({
                "type":
                    "IF",

                "condition":
                    condition
            })

            if_context_stack.append({
                "condition": condition,
                "branch": "THEN"
            })

            if_depth += 1

            current_rem = None

            continue

        # -------------------------------------------------
        # ELSE
        # -------------------------------------------------

        if re.match(
            r'^ELSE\b',
            line,
            re.IGNORECASE
        ):

            if if_depth <= 0:

                raise ValueError(
                    "ELSE에 대응하는 IF가 없습니다."
                )

            control_logic.append({
                "type":
                    "ELSE"
            })

            if if_context_stack:
                if_context_stack[-1]["branch"] = "ELSE"

            current_rem = None

            continue

        # -------------------------------------------------
        # ENDIF
        # -------------------------------------------------

        if re.match(
            r'^ENDIF\b',
            line,
            re.IGNORECASE
        ):

            if if_depth <= 0:

                raise ValueError(
                    "ENDIF에 대응하는 IF가 없습니다."
                )

            control_logic.append({
                "type":
                    "ENDIF"
            })

            if if_context_stack:

                if_context_stack.pop()

            if_depth -= 1

            current_rem = None

            continue

        # -------------------------------------------------
        # Hardware Assignment
        #
        # LED_02 = ON
        # LED_02 = OFF
        # -------------------------------------------------

        match = re.match(
            r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(ON|OFF)$',
            line,
            re.IGNORECASE
        )

        if match:

            target = (
                match.group(1)
            )

            value = (
                match.group(2).upper()
            )

            control_logic.append({
                "type":
                    "ASSIGN",

                "target":
                    target,

                "value":
                    value,

                "pin":
                    None
            })

            current_rem = None

            continue

    # =====================================================
    # Control Validation
    # =====================================================

    if while_depth != 0:

        raise ValueError(
            "WHILE과 WEND의 개수가 맞지 않습니다."
        )

    if if_depth != 0:

        raise ValueError(
            "IF와 ENDIF의 개수가 맞지 않습니다."
        )

    # =====================================================
    # Resolve LED Assignments
    # =====================================================

    for item in control_logic:

        if item["type"] != "ASSIGN":
            continue

        target = item["target"]

        led_pin = resolve_led(
            target
        )

        if led_pin is None:

            raise ValueError(
                f"LED 정보를 찾을 수 없습니다: {target}\n\n"
                f"먼저 다음과 같이 LED를 정의하세요.\n\n"
                f"REM {target}\n"
                f"PINMODE <GPIO>, OUTPUT"
            )

        item["pin"] = led_pin

        used_led_pins[
            target.upper()
        ] = led_pin

    # =====================================================
    # Project Directory
    # =====================================================

    os.makedirs(
        project_dir,
        exist_ok=True
    )

    # =====================================================
    # UART IP
    # =====================================================

    uart_tx_file = ensure_uart_tx_ip(
        project_dir
    )

    # =====================================================
    # Clock
    # =====================================================

    clock_info = board_map.get(
        "clock",
        {}
    )

    clock_pin = clock_info.get(
        "clk"
    )

    clock_freq = clock_info.get(
        "freq",
        12_000_000
    )

    # =====================================================
    # UART
    # =====================================================

    uart_info = board_map.get(
        "uart",
        {}
    )

    uart_tx_pin = uart_info.get(
        "TX"
    )

    has_print = (
        any(
            item["type"] in ("PRINT", "PRINT_VALUE")
            for item in control_logic
        )
        and uart_tx_pin is not None
    )

    # =====================================================
    # Divider
    #
    # The sequential divider is only instantiated when the
    # BASIC source actually divides.
    # =====================================================

    has_divider = any(
        item["type"] == "CALC_ASSIGN"
        and item.get("divide")
        for item in control_logic
    )

    # =====================================================
    # FSM Analysis
    # =====================================================

    # One extra terminal state prevents top-level programs from
    # wrapping back to STATE_0 after the final statement.
    state_count = max(
        1,
        len(control_logic) + 1
    )

    state_width = max(
        1,
        math.ceil(
            math.log2(
                max(2, state_count)
            )
        )
    )

    # -----------------------------------------------------
    # Matching structures
    # -----------------------------------------------------

    if_stack = []
    while_stack = []

    if_else_target = {}
    if_end_target = {}
    else_end_target = {}

    while_wend_target = {}
    wend_while_target = {}

    for index, item in enumerate(
        control_logic
    ):

        item_type = item["type"]

        if item_type == "IF":

            if_stack.append(
                index
            )

        elif item_type == "ELSE":

            if not if_stack:

                raise ValueError(
                    "FSM 분석 중 ELSE 오류"
                )

            if_index = if_stack[-1]

            if_else_target[
                if_index
            ] = index + 1

        elif item_type == "ENDIF":

            if not if_stack:

                raise ValueError(
                    "FSM 분석 중 ENDIF 오류"
                )

            if_index = if_stack.pop()

            if_end_target[
                if_index
            ] = index + 1

            for backward in range(
                index - 1,
                if_index,
                -1
            ):

                if (
                    control_logic[
                        backward
                    ]["type"]
                    == "ELSE"
                ):

                    else_end_target[
                        backward
                    ] = index + 1

                    break

        elif item_type == "WHILE":

            while_stack.append(
                index
            )

        elif item_type == "WEND":

            if not while_stack:

                raise ValueError(
                    "FSM 분석 중 WEND 오류"
                )

            while_index = while_stack.pop()

            while_wend_target[
                while_index
            ] = index

            wend_while_target[
                index
            ] = while_index

    if if_stack:

        raise ValueError(
            "FSM IF stack 오류"
        )

    if while_stack:

        raise ValueError(
            "FSM WHILE stack 오류"
        )

    # =====================================================
    # Determine WHILE context for each PRINT
    # =====================================================

    print_in_while = {}
    _while_depth = 0
    for _index, _item in enumerate(control_logic):
        if _item["type"] == "WHILE":
            _while_depth += 1
        elif _item["type"] == "WEND":
            _while_depth = max(0, _while_depth - 1)
        elif _item["type"] in ("PRINT", "PRINT_VALUE"):
            print_in_while[_index] = (_while_depth > 0)

    # =====================================================
    # Determine PRINT button triggers
    # =====================================================

    print_button_conditions = {}

    for index, item in enumerate(control_logic):
        if item["type"] != "PRINT":
            continue

        condition = item.get("trigger_condition")
        branch = item.get("trigger_branch")
        if not condition or branch != "THEN":
            continue

        button_match = re.fullmatch(
            r'(BUTTON|BTN|BTN[_\s]*0*\d+)',
            condition,
            re.IGNORECASE
        )

        if button_match:
            button_name = button_match.group(1)
            if button_name.upper() in ("BUTTON", "BTN"):
                key = "BUTTON"
            else:
                number_match = re.fullmatch(
                    r'BTN[_\s]*0*(\d+)', button_name, re.IGNORECASE
                )
                key = (f"BTN_{int(number_match.group(1)):02d}"
                       if number_match else None)
            if key:
                print_button_conditions[index] = key

    # =====================================================
    # Verilog
    # =====================================================

    verilog = []

    verilog.append(
        "// ========================================================"
    )

    verilog.append(
        f"// xBASIC Generated Verilog : {project_name}"
    )

    verilog.append(
        "// ========================================================"
    )

    verilog.append("")

    verilog.append(
        "// Generated from xBASIC source."
    )

    verilog.append(
        "// Control flow is implemented as a hardware FSM."
    )

    verilog.append(
        "// PRINT executes only on a button Pressed Rising Edge."
    )

    verilog.append("")

    # =====================================================
    # Module
    # =====================================================

    verilog.append(
        f"module {project_name} ("
    )

    ports = []
    port_names = set()

    def add_port(
        text,
        name
    ):

        if name in port_names:
            return

        port_names.add(
            name
        )

        ports.append(
            text
        )

    # -----------------------------------------------------
    # Clock
    # -----------------------------------------------------

    if clock_pin is not None:

        add_port(
            "    input wire clk",
            "clk"
        )

    # -----------------------------------------------------
    # UART
    # -----------------------------------------------------

    if has_print:

        add_port(
            "    output wire UART_TX",
            "UART_TX"
        )

    # -----------------------------------------------------
    # Existing PINMODE ports
    # -----------------------------------------------------

    controlled_led_names = {
        name.upper()
        for name in used_led_pins.keys()
    }

    for pin_number, info in pin_info.items():

        name = info[
            "verilog_name"
        ]

        mode = info[
            "mode"
        ]

        if name == "UART_TX":
            continue

        if name == "clk":
            continue

        if mode == "OUTPUT":

            if (
                name.upper()
                in controlled_led_names
            ):

                add_port(
                    f"    output reg {name}",
                    name
                )

            else:

                add_port(
                    f"    output wire {name}",
                    name
                )

        elif mode == "INPUT":

            add_port(
                f"    input wire {name}",
                name
            )

    # -----------------------------------------------------
    # Automatic Button Ports
    # -----------------------------------------------------

    if "BUTTON" in used_button_pins:

        add_port(
            "    input wire BUTTON",
            "BUTTON"
        )

    for button_name in used_button_pins:

        if button_name == "BUTTON":
            continue

        verilog_button_name = (
            to_verilog_name_static(
                button_name
            )
        )

        add_port(
            f"    input wire {verilog_button_name}",
            verilog_button_name
        )

    # -----------------------------------------------------
    # Automatic LED Ports
    # -----------------------------------------------------

    for led_name in used_led_pins:

        verilog_led_name = (
            to_verilog_name_static(
                led_name
            )
        )

        add_port(
            f"    output reg {verilog_led_name}",
            verilog_led_name
        )

    verilog.append(
        ",\n".join(ports)
    )

    verilog.append(
        ");"
    )

    verilog.append("")

    # =====================================================
    # Button Rising Edge Detection
    # =====================================================

    if used_button_pins:

        verilog.append(
            "// ========================================================"
        )

        verilog.append(
            "// Button Pressed Rising Edge Detection"
        )

        verilog.append(
            "// ========================================================"
        )

        verilog.append("")

        for button_name in used_button_pins:

            verilog_name = (
                "BUTTON"
                if button_name == "BUTTON"
                else to_verilog_name_static(
                    button_name
                )
            )

            pressed_name = (
                f"{verilog_name}_pressed"
            )

            prev_name = (
                f"{verilog_name}_pressed_prev"
            )

            rise_name = (
                f"{verilog_name}_pressed_rise"
            )

            if active_low:

                verilog.append(
                    f"wire {pressed_name} = "
                    f"!{verilog_name};"
                )

            else:

                verilog.append(
                    f"wire {pressed_name} = "
                    f"{verilog_name};"
                )

            verilog.append(
                f"reg {prev_name};"
            )

            verilog.append(
                f"wire {rise_name} = "
                f"{pressed_name} && "
                f"!{prev_name};"
            )

            verilog.append("")

        verilog.append(
            "initial begin"
        )

        for button_name in used_button_pins:

            verilog_name = (
                "BUTTON"
                if button_name == "BUTTON"
                else to_verilog_name_static(
                    button_name
                )
            )

            verilog.append(
                f"    {verilog_name}_pressed_prev = "
                f"1'b0;"
            )

        verilog.append(
            "end"
        )

        verilog.append("")

    # =====================================================
    # Initial LED State
    # =====================================================

    if used_led_pins:

        verilog.append(
            "// ========================================================"
        )

        verilog.append(
            "// Initial LED State"
        )

        verilog.append(
            "// ========================================================"
        )

        verilog.append("")

        verilog.append(
            "initial begin"
        )

        for led_name in used_led_pins:

            verilog_name = (
                to_verilog_name_static(
                    led_name
                )
            )

            if active_low:

                initial_value = "1'b1"

            else:

                initial_value = "1'b0"

            verilog.append(
                f"    {verilog_name} = "
                f"{initial_value};"
            )

        verilog.append(
            "end"
        )

        verilog.append("")

    # =====================================================
    # BASIC Numeric Variables
    # =====================================================

    if basic_variables:

        verilog.append(
            "// ========================================================"
        )

        verilog.append(
            "// xBASIC Numeric Variables"
        )

        verilog.append(
            "// ========================================================"
        )

        verilog.append("")

        for variable_name in sorted(basic_variables):

            verilog.append(
                f"reg signed [31:0] {to_verilog_name_static(variable_name)};"
            )

        verilog.append("")

        verilog.append("initial begin")

        for variable_name in sorted(basic_variables):

            verilog.append(
                f"    {to_verilog_name_static(variable_name)} = 32'd0;"
            )

        verilog.append("end")

        verilog.append("")

    # =====================================================
    # Sequential Divider
    # =====================================================

    if has_divider:

        for line_text in [
            "// ========================================================",
            "// xBASIC Sequential Divider",
            "// ========================================================",
            "//",
            "// A combinational 32-bit divide cannot settle inside one",
            "// clock period, so division is NOT inlined into the FSM.",
            "// This unit walks the quotient one bit per clock",
            "// (shift-subtract / restoring division) and the BASIC FSM",
            "// waits on div_valid. 32 clocks per divide.",
            "//",
            "// Semantics : truncation toward zero (BASIC / C).",
            "// Divide by zero : result is 0.",
            "",
            "reg               div_start;",
            "reg signed [31:0] div_dividend;",
            "reg signed [31:0] div_divisor;",
            "reg signed [31:0] div_result;",
            "reg               div_valid;",
            "reg               div_run;",
            "reg               div_neg;",
            "reg        [31:0] div_num;    // |dividend|, shifted out MSB first",
            "reg        [31:0] div_den;    // |divisor|",
            "reg        [31:0] div_rem;",
            "reg        [31:0] div_quo;",
            "reg        [5:0]  div_count;",
            "",
            "// One restoring-division step, combinational.",
            "wire [31:0] div_rem_next = {div_rem[30:0], div_num[31]};",
            "wire        div_bit      = (div_rem_next >= div_den);",
            "wire [31:0] div_quo_next = {div_quo[30:0], div_bit};",
            "",
            "initial begin",
            "    div_start    = 1'b0;",
            "    div_dividend = 32'd0;",
            "    div_divisor  = 32'd0;",
            "    div_result   = 32'd0;",
            "    div_valid    = 1'b0;",
            "    div_run      = 1'b0;",
            "    div_neg      = 1'b0;",
            "    div_num      = 32'd0;",
            "    div_den      = 32'd0;",
            "    div_rem      = 32'd0;",
            "    div_quo      = 32'd0;",
            "    div_count    = 6'd0;",
            "end",
            "",
        ]:
            verilog.append(line_text)

    # =====================================================
    # UART IP
    # =====================================================

    if has_print:

        verilog.append(
            "// ========================================================"
        )

        verilog.append(
            "// UART TX IP"
        )

        verilog.append(
            "// ========================================================"
        )

        verilog.append("")

        verilog.append(
            "reg        uart_start;"
        )

        verilog.append(
            "reg [7:0]  uart_data;"
        )

        verilog.append(
            "wire       uart_busy;"
        )

        verilog.append("")

        verilog.append(
            "uart_tx #("
        )

        verilog.append(
            f"    .CLK_FREQ({clock_freq}),"
        )

        verilog.append(
            "    .BAUD_RATE(115200)"
        )

        verilog.append(
            ") uart_tx_inst ("
        )

        verilog.append(
            "    .clk(clk),"
        )

        verilog.append(
            "    .rst(1'b0),"
        )

        verilog.append(
            "    .start(uart_start),"
        )

        verilog.append(
            "    .data(uart_data),"
        )

        verilog.append(
            "    .tx(UART_TX),"
        )

        verilog.append(
            "    .busy(uart_busy)"
        )

        verilog.append(
            ");"
        )

        verilog.append("")

        # -------------------------------------------------
        # PRINT ROM
        # -------------------------------------------------

        verilog.append(
            "// ========================================================"
        )

        verilog.append(
            "// xBASIC PRINT ROM"
        )

        verilog.append(
            "// ========================================================"
        )

        verilog.append("")

        for message_id, message in enumerate(
            print_messages
        ):

            message_bytes = [
                ord(c) & 0xff
                for c in message
            ]

            message_bytes.append(0)

            verilog.append(
                f"reg [7:0] print_rom_{message_id} "
                f"[0:{len(message_bytes) - 1}];"
            )

        verilog.append("")

        verilog.append(
            "initial begin"
        )

        for message_id, message in enumerate(
            print_messages
        ):

            message_bytes = [
                ord(c) & 0xff
                for c in message
            ]

            message_bytes.append(0)

            for index, value in enumerate(
                message_bytes
            ):

                verilog.append(
                    f"    print_rom_{message_id}"
                    f"[{index}] = "
                    f"8'h{value:02X};"
                )

        verilog.append(
            "end"
        )

        verilog.append("")

        verilog.append(
            "reg [7:0] print_id;"
        )

        verilog.append(
            "reg [15:0] print_index;"
        )

        verilog.append(
            "reg print_active;"
        )

        verilog.append(
            "reg print_wait_busy;"
        )

        verilog.append(
            "reg print_wait_busy_high;"
        )

        verilog.append(
            "reg print_finished;"
        )

        verilog.append(
            "reg [7:0] print_byte;"
        )

        # -------------------------------------------------
        # Print request
        # -------------------------------------------------

        verilog.append(
            "reg [7:0] print_request;"
        )

        verilog.append(
            "reg print_request_valid;"
        )

        # -------------------------------------------------
        # Numeric PRINT request / decimal buffer
        # -------------------------------------------------

        verilog.append(
            "reg print_value_request_valid;"
        )

        verilog.append(
            "reg signed [31:0] print_value_request;"
        )

        verilog.append(
            "reg signed [31:0] print_value;"
        )

        verilog.append(
            "reg [3:0] print_num_length;"
        )

        verilog.append(
            "reg print_num_negative;"
        )

        verilog.append(
            "reg [31:0] print_num_abs;"
        )

        verilog.append(
            "reg [7:0] print_num_rom [0:10];"
        )

        verilog.append("")

        # -------------------------------------------------
        # Sequential binary -> BCD (double dabble)
        #
        # The old code built the decimal digits with ten
        # combinational 32-bit divides in a single clock. On
        # iCE40 that is a ~700 ns path, which is why nextpnr
        # reported "Max frequency 1.42 MHz (FAIL at 12.00 MHz)".
        #
        # Double dabble replaces all of it with 32 clocks of a
        # shift plus ten 4-bit "add 3 if >= 5" adjusters, so the
        # longest combinational path is only a few nanoseconds.
        # -------------------------------------------------

        verilog.append(
            "// Binary -> BCD (double dabble), 32 clocks."
        )

        verilog.append(
            "reg [39:0] bcd_digits;   // 10 decimal digits, 4 bits each"
        )

        verilog.append(
            "reg [31:0] bcd_shift;    // |value|, shifted out MSB first"
        )

        verilog.append(
            "reg [5:0]  bcd_count;"
        )

        verilog.append(
            "reg        bcd_busy;"
        )

        verilog.append("")

        for digit in range(10):

            high = digit * 4 + 3
            low = digit * 4

            verilog.append(
                f"wire [3:0] bcd_adj{digit} = "
                f"(bcd_digits[{high}:{low}] >= 4'd5) ? "
                f"(bcd_digits[{high}:{low}] + 4'd3) : "
                f"bcd_digits[{high}:{low}];"
            )

        verilog.append(
            "wire [39:0] bcd_adj = {"
            + ", ".join(
                f"bcd_adj{digit}"
                for digit in range(9, -1, -1)
            )
            + "};"
        )

        verilog.append(
            "wire [39:0] bcd_next = {bcd_adj[38:0], bcd_shift[31]};"
        )

        verilog.append("")

        # Decimal length = position of the most significant
        # non-zero BCD digit. Cheap priority mux, no comparators
        # against 32-bit constants.

        verilog.append(
            "wire [3:0] bcd_length ="
        )

        for digit in range(9, 0, -1):

            high = digit * 4 + 3
            low = digit * 4

            verilog.append(
                f"    (bcd_digits[{high}:{low}] != 4'd0) ? "
                f"4'd{digit + 1} :"
            )

        verilog.append(
            "    4'd1;"
        )

        verilog.append("")

        # -------------------------------------------------
        # Absolute value of the pending numeric PRINT request.
        # Two's complement negate, evaluated as UNSIGNED so that
        # the decimal division / modulo below is unsigned.
        # (-2147483648 also works: abs = 32'h80000000 = 2147483648.)
        # -------------------------------------------------

        verilog.append(
            "wire [31:0] print_value_abs = "
            "print_value_request[31] ? "
            "(~print_value_request + 32'd1) : print_value_request;"
        )

        verilog.append("")

        # -------------------------------------------------
        # The old comparator-chain decimal_length() helper is gone.
        # Digit count now falls out of the BCD result (bcd_length).
        # -------------------------------------------------


        # -------------------------------------------------
        # PRINT byte selector
        # -------------------------------------------------

        verilog.append(
            "always @(*) begin"
        )

        verilog.append(
            "    print_byte = 8'h00;"
        )

        verilog.append("")

        verilog.append(
            "    if (print_id == 8'd255) begin"
        )

        verilog.append(
            "        if (print_num_negative && print_index == 16'd0)"
        )

        verilog.append(
            "            print_byte = 8'd45;   // '-' sign"
        )

        verilog.append(
            "        else if (print_index < print_num_length)"
        )

        verilog.append(
            "            print_byte = print_num_rom[11 - print_num_length + print_index];"
        )

        verilog.append(
            "        else"
        )

        verilog.append(
            "            print_byte = 8'h00;"
        )

        verilog.append(
            "    end else begin"
        )

        verilog.append(
            "        case (print_id)"
        )

        for message_id in range(
            len(print_messages)
        ):

            verilog.append(
                f"        8'd{message_id}: "
                f"print_byte = "
                f"print_rom_{message_id}[print_index];"
            )

        verilog.append(
            "        default: "
            "print_byte = 8'h00;"
        )

        verilog.append(
            "        endcase"
        )

        verilog.append(
            "    end"
        )

        verilog.append(
            "end"
        )

        verilog.append("")

    # =====================================================
    # FSM
    # =====================================================

    if control_logic:

        verilog.append(
            "// ========================================================"
        )

        verilog.append(
            "// xBASIC Hardware FSM"
        )

        verilog.append(
            "// ========================================================"
        )

        verilog.append("")

        verilog.append(
            f"localparam integer FSM_STATE_WIDTH = "
            f"{state_width};"
        )

        verilog.append("")

        for index, item in enumerate(
            control_logic
        ):

            verilog.append(
                f"localparam [{state_width - 1}:0] "
                f"STATE_{index} = "
                f"{state_width}'d{index};"
            )

        verilog.append("")

        # Terminal state used when BASIC source finishes outside WHILE/WEND.
        verilog.append(
            f"localparam [{state_width - 1}:0] STATE_DONE = "
            f"{state_width}'d{len(control_logic)};"
        )

        verilog.append(
            f"reg [{state_width - 1}:0] fsm_state;"
        )

        verilog.append("")

        verilog.append(
            "initial begin"
        )

        verilog.append(
            "    fsm_state = STATE_0;"
        )

        if basic_variables:

            for variable_name in sorted(basic_variables):

                verilog.append(
                    f"    {to_verilog_name_static(variable_name)} = 32'd0;"
                )

        if has_print:

            verilog.append(
                "    uart_start = 1'b0;"
            )

            verilog.append(
                "    uart_data = 8'h00;"
            )

            verilog.append(
                "    print_id = 8'h00;"
            )

            verilog.append(
                "    print_index = 16'd0;"
            )

            verilog.append(
                "    print_active = 1'b0;"
            )

            verilog.append(
                "    print_wait_busy = 1'b0;"
            )

            verilog.append(
                "    print_wait_busy_high = 1'b0;"
            )

            verilog.append(
                "    print_finished = 1'b0;"
            )

            verilog.append(
                "    print_request = 8'h00;"
            )

            verilog.append(
                "    print_request_valid = 1'b0;"
            )

            verilog.append(
                "    print_value_request_valid = 1'b0;"
            )

            verilog.append(
                "    print_value_request = 32'd0;"
            )

            verilog.append(
                "    print_value = 32'd0;"
            )

            verilog.append(
                "    print_num_length = 4'd1;"
            )

            verilog.append(
                "    print_num_negative = 1'b0;"
            )

            verilog.append(
                "    print_num_abs = 32'd0;"
            )

            verilog.append(
                "    bcd_digits = 40'd0;"
            )

            verilog.append(
                "    bcd_shift = 32'd0;"
            )

            verilog.append(
                "    bcd_count = 6'd0;"
            )

            verilog.append(
                "    bcd_busy = 1'b0;"
            )

        verilog.append(
            "end"
        )

        verilog.append("")

        verilog.append(
            "always @(posedge clk) begin"
        )

        # -------------------------------------------------
        # Button previous-state update
        # -------------------------------------------------

        if used_button_pins:

            verilog.append(
                "    // Update button previous states"
            )

            for button_name in used_button_pins:

                verilog_name = (
                    "BUTTON"
                    if button_name == "BUTTON"
                    else to_verilog_name_static(
                        button_name
                    )
                )

                verilog.append(
                    f"    {verilog_name}_pressed_prev "
                    f"<= {verilog_name}_pressed;"
                )

            verilog.append("")

        # -------------------------------------------------
        # Sequential divider engine
        #
        # Placed before the BASIC FSM so that div_start works
        # as a one-clock pulse: the FSM raises it later in the
        # same always block and that assignment wins.
        # -------------------------------------------------

        if has_divider:

            for line_text in [
                "    // ---------------------------------------------",
                "    // Sequential divider : 1 quotient bit per clock",
                "    // ---------------------------------------------",
                "    div_start <= 1'b0;   // one-clock pulse",
                "",
                "    if (div_start) begin",
                "",
                "        if (div_divisor == 32'sd0) begin",
                "            // Division by zero yields 0.",
                "            div_result <= 32'sd0;",
                "            div_valid  <= 1'b1;",
                "            div_run    <= 1'b0;",
                "",
                "        end else begin",
                "            // Divide the magnitudes, remember the result sign.",
                "            div_num   <= div_dividend[31] ? "
                "(~div_dividend + 32'd1) : div_dividend;",
                "            div_den   <= div_divisor[31]  ? "
                "(~div_divisor  + 32'd1) : div_divisor;",
                "            div_neg   <= div_dividend[31] ^ div_divisor[31];",
                "            div_rem   <= 32'd0;",
                "            div_quo   <= 32'd0;",
                "            div_count <= 6'd32;",
                "            div_run   <= 1'b1;",
                "            div_valid <= 1'b0;",
                "        end",
                "",
                "    end else if (div_run) begin",
                "",
                "        div_num   <= {div_num[30:0], 1'b0};",
                "        div_quo   <= div_quo_next;",
                "        div_rem   <= div_bit ? "
                "(div_rem_next - div_den) : div_rem_next;",
                "        div_count <= div_count - 6'd1;",
                "",
                "        if (div_count == 6'd1) begin",
                "            div_run    <= 1'b0;",
                "            div_valid  <= 1'b1;",
                "            div_result <= div_neg ? "
                "(~div_quo_next + 32'd1) : div_quo_next;",
                "        end",
                "",
                "    end",
                "",
            ]:
                verilog.append(line_text)

        if has_print:

            verilog.append(
                "    // UART start is a one-clock pulse"
            )

            verilog.append(
                "    uart_start <= 1'b0;"
            )

            verilog.append("")

            # ---------------------------------------------
            # Capture button PRINT requests
            #
            # Rising Edge에서 message ID를 latch
            # ---------------------------------------------

            for state_index, button_key in (
                print_button_conditions.items()
            ):

                message_id = control_logic[
                    state_index
                ]["message_id"]

                verilog_name = (
                    "BUTTON"
                    if button_key == "BUTTON"
                    else to_verilog_name_static(
                        button_key
                    )
                )

                rise_signal = (
                    f"{verilog_name}_pressed_rise"
                )

                verilog.append(
                    f"    if ({rise_signal}) begin"
                )

                verilog.append(
                    f"        print_request <= "
                    f"8'd{message_id};"
                )

                verilog.append(
                    "        print_request_valid <= 1'b1;"
                )

                verilog.append(
                    "    end"
                )

            if print_button_conditions:

                verilog.append("")

            # ---------------------------------------------
            # PRINT engine
            # ---------------------------------------------

            verilog.append(
                "    // ---------------------------------------------"
            )

            verilog.append(
                "    // PRINT UART FSM"
            )

            verilog.append(
                "    // ---------------------------------------------"
            )

            verilog.append(
                "    if (print_active) begin"
            )

            verilog.append("")

            verilog.append(
                "        if (!print_wait_busy) begin"
            )

            verilog.append("")

            verilog.append(
                "            if (print_byte != 8'h00) begin"
            )

            verilog.append(
                "                uart_data <= print_byte;"
            )

            verilog.append(
                "                uart_start <= 1'b1;"
            )

            verilog.append(
                "                print_wait_busy <= 1'b1;"
            )

            verilog.append(
                "                print_wait_busy_high <= 1'b0;"
            )

            verilog.append("")

            verilog.append(
                "            end else begin"
            )

            verilog.append(
                "                print_active <= 1'b0;"
            )

            verilog.append(
                "                print_finished <= 1'b1;"
            )

            verilog.append(
                "            end"
            )

            verilog.append("")

            verilog.append(
                "        end else begin"
            )

            verilog.append(
                "            // Wait for UART BUSY rising edge, then BUSY falling edge."
            )

            verilog.append(
                "            if (!print_wait_busy_high) begin"
            )

            verilog.append(
                "                if (uart_busy) begin"
            )

            verilog.append(
                "                    print_wait_busy_high <= 1'b1;"
            )

            verilog.append(
                "                end"
            )

            verilog.append(
                "            end else if (!uart_busy) begin"
            )

            verilog.append(
                "                print_wait_busy <= 1'b0;"
            )

            verilog.append(
                "                print_wait_busy_high <= 1'b0;"
            )

            verilog.append(
                "                print_index <= print_index + 1'b1;"
            )

            verilog.append(
                "            end"
            )

            verilog.append(
                "        end"
            )

            verilog.append("")

            verilog.append(
                "    end"
            )

            verilog.append("")

            # ---------------------------------------------
            # Start pending Numeric PRINT request
            # ---------------------------------------------

            verilog.append(
                "    // Numeric PRINT : start binary -> BCD conversion."
            )

            verilog.append(
                "    if (!print_active && !bcd_busy && "
                "print_value_request_valid) begin"
            )

            verilog.append(
                "        print_value        <= print_value_request;"
            )

            verilog.append(
                "        print_num_negative <= print_value_request[31];"
            )

            verilog.append(
                "        print_num_abs      <= print_value_abs;"
            )

            verilog.append(
                "        bcd_shift          <= print_value_abs;"
            )

            verilog.append(
                "        bcd_digits         <= 40'd0;"
            )

            verilog.append(
                "        bcd_count          <= 6'd32;"
            )

            verilog.append(
                "        bcd_busy           <= 1'b1;"
            )

            verilog.append(
                "        print_value_request_valid <= 1'b0;"
            )

            verilog.append(
                "    end else if (bcd_busy) begin"
            )

            verilog.append(
                "        if (bcd_count != 6'd0) begin"
            )

            verilog.append(
                "            // One double-dabble step per clock."
            )

            verilog.append(
                "            bcd_digits <= bcd_next;"
            )

            verilog.append(
                "            bcd_shift  <= {bcd_shift[30:0], 1'b0};"
            )

            verilog.append(
                "            bcd_count  <= bcd_count - 6'd1;"
            )

            verilog.append(
                "        end else begin"
            )

            verilog.append(
                "            bcd_busy <= 1'b0;"
            )

            verilog.append("")

            verilog.append(
                "            // print_num_rom[0] is never selected by the "
                "read mux"
            )

            verilog.append(
                "            // (index 0 is always the '-' column). Drive it "
                "anyway"
            )

            verilog.append(
                "            // so synthesis does not report an undriven wire."
            )

            verilog.append(
                "            print_num_rom[0] <= 8'h00;"
            )

            verilog.append("")

            verilog.append(
                "            // Digits come from the ABSOLUTE value. The '-' "
                "sign is"
            )

            verilog.append(
                "            // emitted by the print_byte mux, never stored "
                "here."
            )

            for index_rom in range(1, 11):

                digit = 10 - index_rom
                high = digit * 4 + 3
                low = digit * 4

                verilog.append(
                    f"            print_num_rom[{index_rom}] <= "
                    f"8'd48 + bcd_digits[{high}:{low}];"
                )

            verilog.append("")

            verilog.append(
                "            // total length = digits (+ 1 column for '-')"
            )

            verilog.append(
                "            print_num_length <= print_num_negative ? "
                "(bcd_length + 4'd1) : bcd_length;"
            )

            verilog.append("")

            verilog.append(
                "            print_id             <= 8'd255;"
            )

            verilog.append(
                "            print_index          <= 16'd0;"
            )

            verilog.append(
                "            print_active         <= 1'b1;"
            )

            verilog.append(
                "            print_finished       <= 1'b0;"
            )

            verilog.append(
                "            print_wait_busy      <= 1'b0;"
            )

            verilog.append(
                "            print_wait_busy_high <= 1'b0;"
            )

            verilog.append(
                "        end"
            )

            verilog.append(
                "    end"
            )

            verilog.append("")

            # ---------------------------------------------
            # Start pending PRINT request
            # ---------------------------------------------

            verilog.append(
                "    if (!print_active && !bcd_busy && "
                "print_request_valid) begin"
            )

            verilog.append(
                "        print_id <= print_request;"
            )

            verilog.append(
                "        print_index <= 16'd0;"
            )

            verilog.append(
                "        print_active <= 1'b1;"
            )

            verilog.append(
                "        print_finished <= 1'b0;"
            )

            verilog.append(
                "        print_wait_busy <= 1'b0;"
            )

            verilog.append(
                "        print_wait_busy_high <= 1'b0;"
            )

            verilog.append(
                "        print_request_valid <= 1'b0;"
            )

            verilog.append(
                "    end"
            )

            verilog.append("")

        # ---------------------------------------------
        # BASIC FSM
        # ---------------------------------------------

        verilog.append(
            "    // ---------------------------------------------"
        )

        verilog.append(
            "    // BASIC FSM"
        )

        verilog.append(
            "    // ---------------------------------------------"
        )

        verilog.append("")

        verilog.append(
            "    case (fsm_state)"
        )

        for index, item in enumerate(
            control_logic
        ):

            item_type = item["type"]

            verilog.append("")

            verilog.append(
                f"        STATE_{index}: begin"
            )

            # -----------------------------------------
            # WHILE
            # -----------------------------------------

            if item_type == "WHILE":

                next_state = index + 1

                if next_state >= len(
                    control_logic
                ):

                    next_state = 0

                verilog.append(
                    "            // WHILE 1"
                )

                verilog.append(
                    f"            fsm_state <= "
                    f"STATE_{next_state};"
                )

            # -----------------------------------------
            # WEND
            # -----------------------------------------

            elif item_type == "WEND":

                target_state = (
                    wend_while_target.get(
                        index,
                        0
                    )
                )

                verilog.append(
                    "            // WEND -> WHILE"
                )

                verilog.append(
                    f"            fsm_state <= "
                    f"STATE_{target_state};"
                )

            # -----------------------------------------
            # IF
            # -----------------------------------------

            elif item_type == "IF":

                condition = item[
                    "condition"
                ]

                condition_verilog = (
                    convert_condition_to_verilog(
                        condition,
                        used_button_pins,
                        active_low
                    )
                )

                true_state = index + 1

                if true_state >= len(
                    control_logic
                ):

                    true_state = 0

                false_state = if_end_target.get(
                    index,
                    true_state
                )

                if index in if_else_target:

                    false_state = (
                        if_else_target[index]
                    )

                verilog.append(
                    f"            // IF {condition}"
                )

                verilog.append(
                    f"            if "
                    f"({condition_verilog}) begin"
                )

                verilog.append(
                    f"                fsm_state <= "
                    f"STATE_{true_state};"
                )

                verilog.append(
                    "            end else begin"
                )

                verilog.append(
                    f"                fsm_state <= "
                    f"STATE_{false_state};"
                )

                verilog.append(
                    "            end"
                )

            # -----------------------------------------
            # ELSE
            # -----------------------------------------

            elif item_type == "ELSE":

                target_state = (
                    else_end_target.get(
                        index,
                        index + 1
                    )
                )

                if target_state >= len(
                    control_logic
                ):

                    target_state = 0

                verilog.append(
                    "            // ELSE"
                )

                verilog.append(
                    f"            fsm_state <= "
                    f"STATE_{target_state};"
                )

            # -----------------------------------------
            # ENDIF
            # -----------------------------------------

            elif item_type == "ENDIF":

                next_state = index + 1

                if next_state >= len(
                    control_logic
                ):

                    next_state = 0

                verilog.append(
                    "            // ENDIF"
                )

                verilog.append(
                    f"            fsm_state <= "
                    f"STATE_{next_state};"
                )

            # -----------------------------------------
            # CALC_ASSIGN
            # -----------------------------------------

            elif item_type == "CALC_ASSIGN":

                target = to_verilog_name_static(
                    item["target"].upper()
                )

                expression = item["expression"]

                # Convert BASIC identifiers to Verilog variable names.
                def _calc_identifier_replace(match):
                    token = match.group(0)
                    if token.isdigit():
                        return token
                    return to_verilog_name_static(token.upper())

                expression_verilog = re.sub(
                    r'[A-Za-z_][A-Za-z0-9_]*',
                    _calc_identifier_replace,
                    expression
                )

                next_state = index + 1

                if next_state >= len(control_logic):

                    next_state = "DONE"

                next_label = (
                    "STATE_DONE"
                    if next_state == "DONE"
                    else f"STATE_{next_state}"
                )

                verilog.append(
                    f"            // {item['target']} = {expression}"
                )

                divide_operands = item.get("divide")

                if divide_operands:

                    # -------------------------------------
                    # Division runs on the sequential
                    # divider. This state issues the request,
                    # holds until div_valid, then stores the
                    # result. ~33 clocks.
                    # -------------------------------------

                    dividend, divisor = divide_operands

                    dividend_verilog = (
                        dividend
                        if dividend.isdigit()
                        else to_verilog_name_static(dividend.upper())
                    )

                    divisor_verilog = (
                        divisor
                        if divisor.isdigit()
                        else to_verilog_name_static(divisor.upper())
                    )

                    verilog.append(
                        "            // 32-clock sequential divide "
                        "(too wide for one clock)"
                    )

                    verilog.append(
                        "            if (div_valid) begin"
                    )

                    verilog.append(
                        f"                {target} <= div_result;"
                    )

                    verilog.append(
                        "                div_valid <= 1'b0;"
                    )

                    verilog.append(
                        f"                fsm_state <= {next_label};"
                    )

                    verilog.append(
                        "            end else if (!div_run && !div_start) begin"
                    )

                    verilog.append(
                        f"                div_dividend <= {dividend_verilog};"
                    )

                    verilog.append(
                        f"                div_divisor  <= {divisor_verilog};"
                    )

                    verilog.append(
                        "                div_start    <= 1'b1;"
                    )

                    verilog.append(
                        f"                fsm_state <= STATE_{index};"
                    )

                    verilog.append(
                        "            end else begin"
                    )

                    verilog.append(
                        "                // divider busy: hold this statement"
                    )

                    verilog.append(
                        f"                fsm_state <= STATE_{index};"
                    )

                    verilog.append(
                        "            end"
                    )

                else:

                    verilog.append(
                        f"            {target} <= {expression_verilog};"
                    )

                    verilog.append(
                        f"            fsm_state <= {next_label};"
                    )

            # -----------------------------------------
            # ASSIGN
            # -----------------------------------------

            elif item_type == "ASSIGN":

                target = to_verilog_name_static(
                    item["target"]
                )

                value = item[
                    "value"
                ]

                if active_low:

                    if value == "ON":

                        verilog_value = "1'b0"

                    else:

                        verilog_value = "1'b1"

                else:

                    if value == "ON":

                        verilog_value = "1'b1"

                    else:

                        verilog_value = "1'b0"

                next_state = index + 1

                if next_state >= len(
                    control_logic
                ):

                    next_state = 0

                verilog.append(
                    f"            // "
                    f"{item['target']} = {value}"
                )

                verilog.append(
                    f"            {target} <= "
                    f"{verilog_value};"
                )

                verilog.append(
                    f"            fsm_state <= "
                    f"STATE_{next_state};"
                )

            # -----------------------------------------
            # PRINT_VALUE
            # -----------------------------------------

            elif item_type == "PRINT_VALUE":

                variable_name = to_verilog_name_static(
                    item["variable"].upper()
                )

                next_state = index + 1

                if next_state >= len(control_logic):

                    next_state = "DONE"

                verilog.append(
                    f"            // PRINT {item['variable']}"
                )

                if print_in_while.get(index, False):

                    verilog.append(
                        "            if (print_finished) begin"
                    )

                    verilog.append(
                        "                print_finished <= 1'b0;"
                    )

                    verilog.append(
                        f"                fsm_state <= STATE_{next_state};"
                    )

                    verilog.append(
                        "            end else if (!print_active && !bcd_busy && "
                        "!print_value_request_valid) begin"
                    )

                    verilog.append(
                        f"                print_value_request <= {variable_name};"
                    )

                    verilog.append(
                        "                print_value_request_valid <= 1'b1;"
                    )

                    verilog.append(
                        f"                fsm_state <= STATE_{index};"
                    )

                    verilog.append(
                        "            end else begin"
                    )

                    verilog.append(
                        f"                fsm_state <= STATE_{index};"
                    )

                    verilog.append(
                        "            end"
                    )

                else:

                    verilog.append(
                        "            if (!print_active && !bcd_busy && "
                        "!print_value_request_valid) begin"
                    )

                    verilog.append(
                        f"                print_value_request <= {variable_name};"
                    )

                    verilog.append(
                        "                print_value_request_valid <= 1'b1;"
                    )

                    verilog.append(
                        f"                fsm_state <= STATE_DONE;" if next_state == "DONE" else f"                fsm_state <= STATE_{next_state};"
                    )

                    verilog.append(
                        "            end else begin"
                    )

                    verilog.append(
                        f"                fsm_state <= STATE_{index};"
                    )

                    verilog.append(
                        "            end"
                    )

            # -----------------------------------------
            # PRINT
            # -----------------------------------------

            elif item_type == "PRINT":

                message_id = item[
                    "message_id"
                ]

                next_state = index + 1

                # A PRINT at the end of a program must execute once and
                # then stop. Do not wrap to STATE_0 unless WEND explicitly
                # created the loop transition.
                if next_state >= len(
                    control_logic
                ):

                    next_state = "DONE"

                trigger_condition = item.get(
                    "trigger_condition"
                )

                verilog.append(
                    f"            // "
                    f'PRINT "{item["message"]}"'
                )

                # -------------------------------------------------
                # IMPORTANT:
                # PRINT must never hold the BASIC/LED control FSM
                # until the UART string transfer has finished.
                #
                # Button PRINT requests are already captured above
                # by the independent rising-edge request logic.
                # Therefore this state simply advances.
                # -------------------------------------------------
                if trigger_condition and item.get("trigger_branch") == "THEN":

                    verilog.append(
                        "            // Button PRINT request is handled by the independent UART engine"
                    )

                    verilog.append(
                        f"            fsm_state <= STATE_DONE;" if next_state == "DONE" else f"            fsm_state <= STATE_{next_state};"
                    )

                else:

                    # -------------------------------------------------
                    # PRINT request handling
                    # -------------------------------------------------
                    # PRINT outside WHILE keeps the previous non-blocking
                    # behavior. PRINT inside WHILE must not lap the UART
                    # engine; it waits for one complete message before WEND
                    # returns to the same PRINT statement.
                    if print_in_while.get(index, False):

                        verilog.append(
                            "            if (print_finished) begin"
                        )

                        verilog.append(
                            "                // One loop PRINT completed: acknowledge and continue to WEND"
                        )

                        verilog.append(
                            "                print_finished <= 1'b0;"
                        )

                        verilog.append(
                            f"                fsm_state <= STATE_{next_state};"
                        )

                        verilog.append(
                            "            end else if (!print_active && !bcd_busy && "
                            "!print_request_valid) begin"
                        )

                        verilog.append(
                            f"                print_request <= 8'd{message_id};"
                        )

                        verilog.append(
                            "                print_request_valid <= 1'b1;"
                        )

                        verilog.append(
                            "                // Stay here until the UART engine completes this message"
                        )

                        verilog.append(
                            f"                fsm_state <= STATE_{index};"
                        )

                        verilog.append(
                            "            end else begin"
                        )

                        verilog.append(
                            f"                fsm_state <= STATE_{index};"
                        )

                        verilog.append(
                            "            end"
                        )

                    else:

                        # Top-level/non-loop PRINT: enqueue once, then continue.
                        verilog.append(
                            "            if (!print_active && !bcd_busy && "
                            "!print_request_valid) begin"
                        )

                        verilog.append(
                            f"                print_request <= 8'd{message_id};"
                        )

                        verilog.append(
                            "                print_request_valid <= 1'b1;"
                        )

                        verilog.append(
                            "                print_finished <= 1'b0;"
                        )

                        verilog.append(
                            f"                fsm_state <= STATE_DONE;" if next_state == "DONE" else f"                fsm_state <= STATE_{next_state};"
                        )

                        verilog.append(
                            "            end else begin"
                        )

                        verilog.append(
                            f"                fsm_state <= STATE_{index};"
                        )

                        verilog.append(
                            "            end"
                        )

            verilog.append(
                "        end"
            )

        verilog.append("")

        verilog.append(
            "        STATE_DONE: begin"
        )

        verilog.append(
            "            // Program completed: hold here (do not restart)."
        )

        verilog.append(
            "            fsm_state <= STATE_DONE;"
        )

        verilog.append(
            "        end"
        )

        verilog.append(
            "        default: begin"
        )

        verilog.append(
            "            fsm_state <= STATE_0;"
        )

        verilog.append(
            "        end"
        )

        verilog.append("")

        verilog.append(
            "    endcase"
        )

        verilog.append("")

        verilog.append(
            "end"
        )

        verilog.append("")

    # =====================================================
    # Existing GPIO
    # =====================================================

    controlled_pin_numbers = set(
        used_led_pins.values()
    )

    for pin_number, info in pin_info.items():

        if info["mode"] != "OUTPUT":
            continue

        if pin_number in controlled_pin_numbers:

            continue

        state = info[
            "state"
        ]

        if state is None:
            continue

        name = info[
            "verilog_name"
        ]

        if state == "SET":

            value = (
                "1'b0"
                if active_low
                else "1'b1"
            )

        elif state == "CLR":

            value = (
                "1'b1"
                if active_low
                else "1'b0"
            )

        else:

            continue

        verilog.append(
            f"assign {name} = {value};"
        )

    verilog.append("")

    verilog.append(
        "endmodule"
    )

    verilog_code = "\n".join(
        verilog
    )

    # =====================================================
    # PCF
    # =====================================================

    pcf = []

    # -----------------------------------------------------
    # Clock
    # -----------------------------------------------------

    if clock_pin is not None:

        pcf.append(
            f"set_io clk {clock_pin}"
        )

    # -----------------------------------------------------
    # UART
    # -----------------------------------------------------

    if has_print:

        pcf.append(
            f"set_io UART_TX {uart_tx_pin}"
        )

    # -----------------------------------------------------
    # Existing PINMODE
    # -----------------------------------------------------

    for pin_number, info in pin_info.items():

        verilog_name = info[
            "verilog_name"
        ]

        if verilog_name == "UART_TX":
            continue

        if verilog_name == "clk":
            continue

        pcf.append(
            f"set_io "
            f"{verilog_name} "
            f"{pin_number}"
        )

    # -----------------------------------------------------
    # Automatic Button PCF
    # -----------------------------------------------------

    for button_name, pin_number in used_button_pins.items():

        verilog_button_name = (
            "BUTTON"
            if button_name == "BUTTON"
            else to_verilog_name_static(
                button_name
            )
        )

        pcf_line = (
            f"set_io "
            f"{verilog_button_name} "
            f"{pin_number}"
        )

        if pcf_line not in pcf:

            pcf.append(
                pcf_line
            )

    # -----------------------------------------------------
    # Automatic LED PCF
    # -----------------------------------------------------

    for led_name, pin_number in used_led_pins.items():

        verilog_led_name = (
            to_verilog_name_static(
                led_name
            )
        )

        pcf_line = (
            f"set_io "
            f"{verilog_led_name} "
            f"{pin_number}"
        )

        if pcf_line not in pcf:

            pcf.append(
                pcf_line
            )

    pcf_code = "\n".join(
        pcf
    )

    # =====================================================
    # Save Verilog
    # =====================================================

    verilog_file = os.path.join(
        project_dir,
        f"{project_name}.v"
    )

    with open(
        verilog_file,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            verilog_code
        )

    # =====================================================
    # Save PCF
    # =====================================================

    pcf_file = os.path.join(
        project_dir,
        f"{project_name}.pcf"
    )

    with open(
        pcf_file,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            pcf_code
        )

    # =====================================================
    # Result
    # =====================================================

    return {

        "verilog_code":
            verilog_code,

        "pcf_code":
            pcf_code,

        "pin_info":
            pin_info,

        "button_pins":
            used_button_pins,

        "led_pins":
            used_led_pins,

        "control_logic":
            control_logic,

        "verilog_file":
            verilog_file,

        "pcf_file":
            pcf_file,

        "uart_tx_file":
            uart_tx_file,

        "has_uart_ip":
            has_print,

        "print_messages":
            print_messages
    }


# =========================================================
# BOARD PIN MAP
# =========================================================

BOARD_PINMAP = {

    "iCESugar_1.5": {

        "led": {
            "LED_G": 41,
            "LED_R": 40,
            "LED_B": 39,
        },

        "switch": {
            "SW[0]": 18,
            "SW[1]": 19,
            "SW[2]": 20,
            "SW[3]": 21,
        },

        # -------------------------------------------------
        # IMPORTANT
        #
        # BTN alias 제거.
        #
        # SW[0]~SW[3]는 더 이상
        # BTN1~BTN4로 자동 사용되지 않는다.
        # -------------------------------------------------

        "clock": {
            "clk": 35,
            "freq": 12_000_000
        },

        "uart": {
            "RX": 4,
            "TX": 6,
        },

        "usb": {
            "USB_DP": 10,
            "USB_DN": 9,
            "USB_PULLUP": 11,
        },

        "pmod": {
            "PMOD1_1": 10,
            "PMOD1_2": 6,
            "PMOD1_3": 3,
            "PMOD1_4": 48,
            "PMOD1_9": 47,
            "PMOD1_10": 2,
            "PMOD1_11": 4,
            "PMOD1_12": 9,

            "PMOD2_1": 46,
            "PMOD2_2": 44,
            "PMOD2_3": 42,
            "PMOD2_4": 37,
            "PMOD2_9": 36,
            "PMOD2_10": 38,
            "PMOD2_11": 43,
            "PMOD2_12": 45,
        }
    },

    "iCEBreaker": {

        "led": {
            "LED": 11,
            "LED_R": 39,
            "LED_G": 40,
            "LED_B": 41,

            "LED1": 26,
            "LED2": 27,
            "LED3": 25,
            "LED4": 23,
            "LED5": 21,
        },

        "button": {
            "BTN": 10,
            "BTN1": 20,
            "BTN2": 19,
            "BTN3": 18,
        },

        "clock": {
            "clk": 35,
            "freq": 12_000_000
        },

        "uart": {
            "RX": 6,
            "TX": 9,
        }
    },

    "Tiny Tape FPGA": {

        "led": {
            "LED": 11,
            "LED_R": 39,
            "LED_G": 40,
            "LED_B": 41,

            "LED1": 26,
            "LED2": 27,
            "LED3": 25,
            "LED4": 23,
            "LED5": 21,
        },

        "button": {
            "BTN": 10,
            "BTN1": 20,
            "BTN2": 19,
            "BTN3": 18,
        },

        "clock": {
            "clk": 35,
            "freq": 12_000_000
        },

        "uart": {
            "RX": 4,
            "TX": 6,
        }
    }
}


# =========================================================
# Application
# =========================================================

class App(tk.Tk):

    def __init__(self):

        super().__init__()

        self.title(
            "FPGA xBASIC v0.2b"
        )

        if os.path.isfile(icon_path):

            try:

                self.iconbitmap(
                    icon_path
                )

                print(
                    f"[ICON] Loaded: {icon_path}"
                )

            except Exception as e:

                print(
                    f"[ICON] Failed to load: {e}"
                )

        else:

            print(
                f"[ICON] File not found: {icon_path}"
            )

        self.geometry(
            "1000x700"
        )

        self.minsize(
            900,
            600
        )

        # =================================================
        # Project State
        # =================================================

        self.current_project_dir = None
        self.current_module = None
        self.current_board = None
        self.basic_file = None
        self.project_json = None
        self.xbprj_file = None
        self.current_project_name = None

        self.editor_dirty = False

        # =================================================
        # Menu
        # =================================================

        menubar = tk.Menu(
            self
        )

        file_menu = tk.Menu(
            menubar,
            tearoff=0
        )

        file_menu.add_command(
            label="New Project",
            command=self.show_project_page
        )

        file_menu.add_command(
            label="Open Project",
            command=self.open_project
        )

        file_menu.add_command(
            label="Save Project As...",
            command=self.save_project_as
        )

        file_menu.add_separator()

        file_menu.add_command(
            label="Project Settings",
            command=self.show_project_page
        )

        file_menu.add_command(
            label="Go to Edit",
            command=self.go_to_project
        )

        file_menu.add_separator()

        file_menu.add_command(
            label="Save",
            command=self.save_basic
        )

        file_menu.add_command(
            label="Build",
            command=self.build_project
        )

        file_menu.add_separator()

        file_menu.add_command(
            label="Exit",
            command=self.destroy
        )

        menubar.add_cascade(
            label="File",
            menu=file_menu
        )

        self.config(
            menu=menubar
        )

        self.bind_all(
            "<Control-s>",
            self.save_basic_event
        )

        self.bind_all(
            "<F5>",
            self.build_project_event
        )

        # =================================================
        # Main Container
        # =================================================

        self.container = ttk.Frame(
            self
        )

        self.container.pack(
            fill="both",
            expand=True
        )

        # =================================================
        # Pages
        # =================================================

        self.project_frame = ttk.Frame(
            self.container,
            padding=15
        )

        self.editor_frame = ttk.Frame(
            self.container
        )

        self.create_project_page()
        self.create_editor_page()

        self.show_project_page()

    # =====================================================
    # Project Page
    # =====================================================

    def create_project_page(self):

        main = self.project_frame

        ttk.Label(
            main,
            text="FPGA xBASIC - Project Settings",
            font=("Arial", 16, "bold")
        ).pack(
            anchor="w",
            pady=(0, 15)
        )

        setting = ttk.LabelFrame(
            main,
            text="Project Settings",
            padding=10
        )

        setting.pack(
            fill="x"
        )

        ttk.Label(
            setting,
            text="Project Name:"
        ).grid(
            row=0,
            column=0,
            padx=5,
            pady=5,
            sticky="w"
        )

        self.project_name = ttk.Entry(
            setting,
            width=35
        )

        self.project_name.grid(
            row=0,
            column=1,
            padx=5,
            pady=5,
            sticky="w"
        )

        ttk.Label(
            setting,
            text="Module Name:"
        ).grid(
            row=1,
            column=0,
            padx=5,
            pady=5,
            sticky="w"
        )

        self.module_name = ttk.Entry(
            setting,
            width=35
        )

        self.module_name.grid(
            row=1,
            column=1,
            padx=5,
            pady=5,
            sticky="w"
        )

        ttk.Label(
            setting,
            text="Board:"
        ).grid(
            row=2,
            column=0,
            padx=5,
            pady=5,
            sticky="w"
        )

        self.board = ttk.Combobox(
            setting,
            width=32,
            state="readonly",
            values=list(
                BOARD_PINMAP.keys()
            )
        )

        self.board.current(0)

        self.board.grid(
            row=2,
            column=1,
            padx=5,
            pady=5,
            sticky="w"
        )

        button_frame = ttk.Frame(
            main
        )

        button_frame.pack(
            fill="x",
            pady=15
        )

        ttk.Button(
            button_frame,
            text="Create Project",
            command=self.create_project
        ).pack(
            side="left",
            padx=5
        )

        self.goto_project_button = ttk.Button(
            button_frame,
            text="Go to Edit",
            command=self.go_to_project,
            state="disabled"
        )

        self.goto_project_button.pack(
            side="left",
            padx=5
        )

        ttk.Button(
            button_frame,
            text="Reset",
            command=self.reset
        ).pack(
            side="left",
            padx=5
        )

        output_frame = ttk.LabelFrame(
            main,
            text="Current Project",
            padding=10
        )

        output_frame.pack(
            fill="x",
            pady=(0, 10)
        )

        self.output_path = ttk.Label(
            output_frame,
            text="-",
            anchor="w"
        )

        self.output_path.pack(
            fill="x"
        )

        self.status = ttk.Label(
            main,
            text="Status: Ready",
            relief="sunken",
            anchor="w",
            padding=5
        )

        self.status.pack(
            fill="x",
            side="bottom"
        )

    # =====================================================
    # Editor Page
    # =====================================================

    def create_editor_page(self):

        top = ttk.Frame(
            self.editor_frame,
            padding=10
        )

        top.pack(
            fill="x"
        )

        self.editor_title = ttk.Label(
            top,
            text="Module Editor",
            font=("Arial", 15, "bold")
        )

        self.editor_title.pack(
            side="left"
        )

        ttk.Button(
            top,
            text="Project Settings",
            command=self.show_project_page
        ).pack(
            side="right",
            padx=5
        )

        ttk.Button(
            top,
            text="Save",
            command=self.save_basic
        ).pack(
            side="right",
            padx=5
        )

        ttk.Button(
            top,
            text="Build",
            command=self.build_project
        ).pack(
            side="right",
            padx=5
        )

        main_area = ttk.Frame(
            self.editor_frame
        )

        main_area.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10)
        )

        left_area = ttk.Frame(
            main_area
        )

        left_area.pack(
            side="left",
            fill="both",
            expand=True
        )

        editor_container = ttk.Frame(
            left_area
        )

        editor_container.pack(
            fill="both",
            expand=True
        )

        self.line_numbers = tk.Text(
            editor_container,
            width=4,
            padx=5,
            takefocus=0,
            border=0,
            background="skyblue",
            foreground="white",
            state="disabled",
            font=("Consolas", 12)
        )

        self.line_numbers.pack(
            side="left",
            fill="y"
        )

        text_frame = ttk.Frame(
            editor_container
        )

        text_frame.pack(
            side="left",
            fill="both",
            expand=True
        )

        self.editor = tk.Text(
            text_frame,
            wrap="none",
            undo=True,
            font=("Consolas", 12),
            background="#1122ee",
            foreground="yellow",
            insertbackground="white",
            tabs=("4c")
        )

        self.editor.pack(
            side="left",
            fill="both",
            expand=True
        )

        scrollbar_y = ttk.Scrollbar(
            text_frame,
            orient="vertical",
            command=self.editor.yview
        )

        scrollbar_y.pack(
            side="right",
            fill="y"
        )

        self.editor.config(
            yscrollcommand=self.on_editor_scroll
        )

        scrollbar_x = ttk.Scrollbar(
            left_area,
            orient="horizontal",
            command=self.editor.xview
        )

        scrollbar_x.pack(
            fill="x"
        )

        self.editor.config(
            xscrollcommand=scrollbar_x.set
        )

        self.create_hardware_panel(
            main_area
        )

        self.editor_status = ttk.Label(
            self.editor_frame,
            text="Ready",
            relief="sunken",
            anchor="w",
            padding=5
        )

        self.editor_status.pack(
            fill="x"
        )

        self.editor.tag_configure(
            "keyword",
            foreground="#569cd6"
        )

        self.editor.tag_configure(
            "gpio",
            foreground="#4ec9b0"
        )

        self.editor.tag_configure(
            "number",
            foreground="#b5cea8"
        )

        self.editor.tag_configure(
            "string",
            foreground="#ce9178"
        )

        self.editor.tag_configure(
            "comment",
            foreground="#6a9955"
        )

        self.editor.bind(
            "<KeyRelease>",
            self.on_editor_changed
        )

        self.editor.bind(
            "<ButtonRelease-1>",
            self.update_line_numbers
        )

        self.editor.bind(
            "<MouseWheel>",
            self.update_line_numbers
        )

    # =====================================================
    # Hardware Panel
    # =====================================================

    def create_hardware_panel(
        self,
        parent
    ):

        panel = ttk.LabelFrame(
            parent,
            text="Hardware create",
            padding=10,
            width=250
        )

        panel.pack(
            side="right",
            fill="y",
            padx=(10, 0)
        )

        panel.pack_propagate(False)

        ttk.Label(
            panel,
            text="Type"
        ).pack(
            anchor="w"
        )

        self.hardware_type = ttk.Combobox(
            panel,
            state="readonly",
            values=["LED"]
        )

        self.hardware_type.current(0)

        self.hardware_type.pack(
            fill="x",
            pady=(0, 15)
        )

        ttk.Label(
            panel,
            text="LED names"
        ).pack(
            anchor="w"
        )

        self.led_index = ttk.Combobox(
            panel,
            state="readonly",
            values=[
                "LED0",
                "LED1",
                "LED2",
                "LED3"
            ]
        )

        self.led_index.current(0)

        self.led_index.pack(
            fill="x",
            pady=(0, 15)
        )

        ttk.Label(
            panel,
            text="(GPIO) Pin"
        ).pack(
            anchor="w"
        )

        self.gpio_pin = ttk.Entry(
            panel
        )

        self.gpio_pin.insert(
            0,
            "0"
        )

        self.gpio_pin.pack(
            fill="x",
            pady=(0, 15)
        )

        ttk.Label(
            panel,
            text="Action"
        ).pack(
            anchor="w"
        )

        self.led_action = ttk.Combobox(
            panel,
            state="readonly",
            values=[
                "ON",
                "OFF",
                "BLINK",
                "TOGGLE"
            ]
        )

        self.led_action.current(0)

        self.led_action.pack(
            fill="x",
            pady=(0, 15)
        )

        ttk.Label(
            panel,
            text="Period (ms)"
        ).pack(
            anchor="w"
        )

        self.led_period = ttk.Entry(
            panel
        )

        self.led_period.insert(
            0,
            "500"
        )

        self.led_period.pack(
            fill="x",
            pady=(0, 20)
        )

        ttk.Button(
            panel,
            text="Gen codes",
            command=self.apply_hardware
        ).pack(
            fill="x"
        )

    # =====================================================
    # Hardware
    # =====================================================

    def apply_hardware(self):

        if self.hardware_type.get() == "LED":

            self.apply_led()

    def apply_led(self):

        led = self.led_index.get()
        pin = self.gpio_pin.get().strip()
        action = self.led_action.get()
        period = self.led_period.get().strip()

        if not pin.isdigit():

            messagebox.showerror(
                "GPIO Error",
                "GPIO Pin은 숫자로 입력하세요."
            )

            return

        if not period.isdigit():

            messagebox.showerror(
                "Period Error",
                "Period은 숫자로 입력하세요."
            )

            return

        if action == "ON":

            code = (
                f"\nREM {led}\n"
                f"PINMODE {pin}, OUTPUT\n"
                f"GPIOSET {pin}\n"
            )

        elif action == "OFF":

            code = (
                f"\nREM {led}\n"
                f"PINMODE {pin}, OUTPUT\n"
                f"GPIOCLR {pin}\n"
            )

        elif action == "BLINK":

            code = (
                f"\nREM {led} BLINK\n"
                f"REM GPIO PIN : {pin}\n\n"
                f"PINMODE {pin}, OUTPUT\n\n"
                f"GPIOSET {pin}\n"
                f"WAIT {period}\n\n"
                f"GPIOCLR {pin}\n"
                f"WAIT {period}\n"
            )

        elif action == "TOGGLE":

            code = (
                f"\nREM {led} TOGGLE\n"
                f"PINMODE {pin}, OUTPUT\n\n"
                f"GPIOSET {pin}\n"
                f"WAIT {period}\n"
                f"GPIOCLR {pin}\n"
            )

        else:

            return

        self.editor.insert(
            tk.INSERT,
            code
        )

        self.editor_dirty = True

        self.highlight_syntax()
        self.update_line_numbers()

        self.editor_status.config(
            text=(
                f"Applied: "
                f"{led} / GPIO {pin} / {action}"
            )
        )

        self.editor.focus_set()

    # =====================================================
    # Project Info
    # =====================================================

    def _project_info(
        self,
        project_name=None,
        module=None,
        board=None
    ):

        project_name = (
            project_name
            or self.current_project_name
            or self.project_name.get().strip()
        )

        module = (
            module
            or self.current_module
            or self.module_name.get().strip()
        )

        board = (
            board
            or self.current_board
            or self.board.get()
        )

        board_info = {

            "iCESugar_1.5": {
                "family": "ice40",
                "device": "up5k",
                "tool": "nextpnr-ice40"
            },

            "iCEBreaker": {
                "family": "ice40",
                "device": "up5k",
                "tool": "nextpnr-ice40"
            },

            "Tiny Tape FPGA": {
                "family": "ice40",
                "device": "up5k",
                "tool": "nextpnr-ice40"
            }
        }

        sources = build_project_sources(
            self.current_project_dir,
            module,
            include_uart=True
        )

        return {

            "project":
                project_name,

            "top_module":
                module,

            "board":
                board,

            "board_info":
                board_info.get(
                    board,
                    {}
                ),

            "sources":
                sources,

            "basic_source":
                module + ".bas",

            "iplib": [
                "IPLIB/uart_tx.v"
            ],

            "tool":
                "FPGA BASIC Tool",

            "language":
                "BASIC",

            "version":
                1
        }

    # =====================================================
    # Write JSON
    # =====================================================

    def _write_json(
        self,
        path,
        data
    ):

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False
            )

    # =====================================================
    # Save Project Metadata
    # =====================================================

    def save_project_metadata(
        self,
        show_error=True
    ):

        if (
            not self.current_project_dir
            or not self.current_module
        ):

            return False

        try:

            ensure_uart_tx_ip(
                self.current_project_dir
            )

        except Exception as e:

            if show_error:

                messagebox.showerror(
                    "IPLIB Error",
                    f"UART TX IP 생성 실패\n\n{e}"
                )

            return False

        project_name = (
            self.current_project_name
            or self.project_name.get().strip()
        )

        project_name = self.normalize_name(
            project_name
        )

        if not project_name:

            if show_error:

                messagebox.showerror(
                    "Project Error",
                    "올바른 Project Name이 필요합니다."
                )

            return False

        info = self._project_info(
            project_name
        )

        project_json = os.path.join(
            self.current_project_dir,
            "project.json"
        )

        xbprj_file = os.path.join(
            self.current_project_dir,
            project_name + ".xbprj"
        )

        old_xbprj = self.xbprj_file

        try:

            self._write_json(
                project_json,
                info
            )

            self._write_json(
                xbprj_file,
                info
            )

            if (
                old_xbprj
                and os.path.abspath(old_xbprj)
                != os.path.abspath(xbprj_file)
                and os.path.exists(old_xbprj)
            ):

                os.remove(
                    old_xbprj
                )

            self.project_json = project_json
            self.xbprj_file = xbprj_file
            self.current_project_name = project_name

            return True

        except Exception as e:

            if show_error:

                messagebox.showerror(
                    "Project Save Error",
                    f"프로젝트 파일 저장 실패\n\n{e}"
                )

            return False

    # =====================================================
    # Open Project
    # =====================================================

    def open_project(self):

        path = filedialog.askopenfilename(
            title="Open xBASIC Project",
            filetypes=[
                ("xBASIC Project", "*.xbprj"),
                ("JSON", "*.json"),
                ("*", "*.*")
            ]
        )

        if not path:

            return False

        try:

            with open(
                path,
                "r",
                encoding="utf-8"
            ) as f:

                info = json.load(f)

            required = (
                "project",
                "top_module",
                "board",
                "basic_source"
            )

            missing = [
                x
                for x in required
                if not info.get(x)
            ]

            if missing:

                raise ValueError(
                    "필수 프로젝트 항목이 없습니다: "
                    + ", ".join(missing)
                )

            board = info[
                "board"
            ]

            if board not in BOARD_PINMAP:

                raise ValueError(
                    f"지원하지 않는 Board입니다: {board}"
                )

            project_dir = os.path.dirname(
                os.path.abspath(path)
            )

            ensure_uart_tx_ip(
                project_dir
            )

            basic_file = os.path.join(
                project_dir,
                info["basic_source"]
            )

            if not os.path.isfile(
                basic_file
            ):

                raise FileNotFoundError(
                    "BASIC 소스를 찾을 수 없습니다.\n\n"
                    + basic_file
                )

            self.current_project_dir = project_dir

            self.current_project_name = (
                self.normalize_name(
                    info["project"]
                )
            )

            self.current_module = (
                self.normalize_name(
                    info["top_module"]
                )
            )

            self.current_board = board

            self.basic_file = basic_file

            self.project_json = os.path.join(
                project_dir,
                "project.json"
            )

            self.xbprj_file = path

            self.project_name.delete(
                0,
                tk.END
            )

            self.project_name.insert(
                0,
                self.current_project_name
            )

            self.module_name.delete(
                0,
                tk.END
            )

            self.module_name.insert(
                0,
                self.current_module
            )

            self.board.set(
                self.current_board
            )

            self.output_path.config(
                text=self.basic_file
            )

            self.status.config(
                text=(
                    "Status: Project opened - "
                    + self.current_project_name
                )
            )

            self.editor_title.config(
                text=(
                    "Main module - "
                    + self.current_module
                    + ".bas"
                )
            )

            self.goto_project_button.config(
                state="normal"
            )

            self.load_basic_file()

            self.save_project_metadata(
                show_error=False
            )

            self.show_editor_page()

            return True

        except Exception as e:

            messagebox.showerror(
                "Open Project Error",
                f"프로젝트를 열 수 없습니다.\n\n{e}"
            )

            return False

    # =====================================================
    # Save Project As
    # =====================================================

    def save_project_as(self):

        if not self.current_module:

            messagebox.showwarning(
                "Save Project As",
                "먼저 프로젝트를 생성하거나 열어주세요."
            )

            return False

        default_name = (
            self.current_project_name
            or self.project_name.get().strip()
            or self.current_module
        )

        path = filedialog.asksaveasfilename(
            title="Save Project As",
            initialfile=default_name + ".xbprj",
            defaultextension=".xbprj",
            filetypes=[
                ("xBASIC Project", "*.xbprj")
            ]
        )

        if not path:

            return False

        path = os.path.abspath(
            path
        )

        project_name = self.normalize_name(
            os.path.splitext(
                os.path.basename(path)
            )[0]
        )

        project_dir = os.path.dirname(
            path
        )

        if not project_name:

            messagebox.showerror(
                "Project Name Error",
                "올바른 프로젝트 이름을 입력하세요."
            )

            return False

        try:

            os.makedirs(
                project_dir,
                exist_ok=True
            )

            # -------------------------------------------------
            # BASIC
            # -------------------------------------------------

            new_basic = os.path.join(
                project_dir,
                self.current_module + ".bas"
            )

            content = self.editor.get(
                "1.0",
                "end-1c"
            )

            with open(
                new_basic,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    content
                )

            # -------------------------------------------------
            # IPLIB
            # -------------------------------------------------

            old_ip = os.path.join(
                self.current_project_dir,
                "IPLIB",
                "uart_tx.v"
            )

            new_ip_dir = os.path.join(
                project_dir,
                "IPLIB"
            )

            os.makedirs(
                new_ip_dir,
                exist_ok=True
            )

            new_ip = os.path.join(
                new_ip_dir,
                "uart_tx.v"
            )

            if os.path.isfile(old_ip):

                shutil.copy2(
                    old_ip,
                    new_ip
                )

            else:

                ensure_uart_tx_ip(
                    project_dir
                )

            # -------------------------------------------------
            # Current Project
            # -------------------------------------------------

            old_dir = (
                self.current_project_dir
            )

            old_project_name = (
                self.current_project_name
            )

            self.current_project_dir = (
                project_dir
            )

            self.current_project_name = (
                project_name
            )

            self.basic_file = (
                new_basic
            )

            self.project_name.delete(
                0,
                tk.END
            )

            self.project_name.insert(
                0,
                project_name
            )

            self.editor_dirty = False

            if not self.save_project_metadata():

                self.current_project_dir = (
                    old_dir
                )

                self.current_project_name = (
                    old_project_name
                )

                return False

            self.output_path.config(
                text=new_basic
            )

            self.status.config(
                text=(
                    "Status: Project saved as - "
                    + project_name
                )
            )

            self.editor_status.config(
                text=(
                    "Project saved: "
                    + self.xbprj_file
                )
            )

            return True

        except Exception as e:

            messagebox.showerror(
                "Save Project As Error",
                f"프로젝트 저장 실패\n\n{e}"
            )

            return False

    # =====================================================
    # Pages
    # =====================================================

    def show_project_page(self):

        self.editor_frame.pack_forget()

        self.project_frame.pack(
            fill="both",
            expand=True
        )

    def show_editor_page(self):

        self.project_frame.pack_forget()

        self.editor_frame.pack(
            fill="both",
            expand=True
        )

        self.editor.focus_set()

    # =====================================================
    # Go Project
    # =====================================================

    def go_to_project(self):

        if not self.current_project_dir:

            messagebox.showwarning(
                "Project",
                "먼저 프로젝트를 생성하세요."
            )

            return

        self.show_editor_page()

        self.editor_status.config(
            text=(
                f"Project: "
                f"{self.current_module}"
            )
        )

    # =====================================================
    # Normalize
    # =====================================================

    def normalize_name(
        self,
        name
    ):

        name = name.strip()

        name = re.sub(
            r"[^a-zA-Z0-9_]",
            "_",
            name
        )

        if name and name[0].isdigit():

            name = "_" + name

        return name

    # =====================================================
    # Create Project
    # =====================================================

    def create_project(self):

        project = (
            self.project_name.get().strip()
        )

        module = (
            self.module_name.get().strip()
        )

        board = (
            self.board.get()
        )

        if not project and not module:

            messagebox.showerror(
                "Project Error",
                "Project Name 또는 Module Name을 입력하세요."
            )

            return

        if project and not module:

            module = project

        elif module and not project:

            project = module

        project = self.normalize_name(
            project
        )

        module = self.normalize_name(
            module
        )

        if not project or not module:

            messagebox.showerror(
                "Name Error",
                "올바른 Project/Module 이름을 입력하세요."
            )

            return

        project_dir = os.path.abspath(
            project
        )

        if os.path.exists(
            project_dir
        ):

            messagebox.showerror(
                "Project Exists",
                "이미 존재하는 프로젝트입니다.\n\n"
                + project_dir
            )

            return

        try:

            os.makedirs(
                project_dir,
                exist_ok=False
            )

        except Exception as e:

            messagebox.showerror(
                "Project Create Error",
                f"프로젝트 폴더를 생성할 수 없습니다.\n\n{e}"
            )

            return

        try:

            # =================================================
            # BASIC
            # =================================================

            basic_file = os.path.join(
                project_dir,
                module + ".bas"
            )

            basic_code = (
                self.create_basic_template(
                    module
                )
            )

            with open(
                basic_file,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    basic_code
                )

            # =================================================
            # IPLIB
            # =================================================

            ensure_uart_tx_ip(
                project_dir
            )

            # =================================================
            # Project State
            # =================================================

            self.current_project_dir = (
                project_dir
            )

            self.current_project_name = (
                project
            )

            self.current_module = (
                module
            )

            self.current_board = (
                board
            )

            self.basic_file = (
                basic_file
            )

            self.project_json = None
            self.xbprj_file = None
            self.editor_dirty = False

            # =================================================
            # Metadata
            # =================================================

            if not self.save_project_metadata():

                raise RuntimeError(
                    "프로젝트 메타데이터 생성 실패"
                )

            # =================================================
            # UI
            # =================================================

            self.output_path.config(
                text=basic_file
            )

            self.status.config(
                text=(
                    "Status: Project opened - "
                    + project
                )
            )

            self.editor_title.config(
                text=(
                    "Main module - "
                    + module
                    + ".bas"
                )
            )

            self.goto_project_button.config(
                state="normal"
            )

            self.load_basic_file()

            self.show_editor_page()

        except Exception as e:

            messagebox.showerror(
                "Project Create Error",
                f"프로젝트 생성 실패\n\n{e}"
            )

    # =====================================================
    # BASIC Template
    # =====================================================

    def create_basic_template(
        self,
        module
    ):

        return f"""
REM ========================================
REM Module : {module}
REM FPGA BASIC Program
REM ========================================

REM Write your FPGA BASIC code here.

"""

    # =====================================================
    # Load BASIC
    # =====================================================

    def load_basic_file(self):

        if not self.basic_file:

            return

        try:

            with open(
                self.basic_file,
                "r",
                encoding="utf-8"
            ) as f:

                content = f.read()

            self.editor.delete(
                "1.0",
                tk.END
            )

            self.editor.insert(
                "1.0",
                content
            )

            self.highlight_syntax()
            self.update_line_numbers()

            self.editor_dirty = False

            self.editor_status.config(
                text=(
                    "Loaded: "
                    + self.basic_file
                )
            )

        except Exception as e:

            messagebox.showerror(
                "Load Error",
                str(e)
            )

    # =====================================================
    # Save BASIC
    # =====================================================

    def save_basic(self):

        if not self.basic_file:

            messagebox.showwarning(
                "Save",
                "먼저 프로젝트를 생성하세요."
            )

            return False

        try:

            content = self.editor.get(
                "1.0",
                "end-1c"
            )

            with open(
                self.basic_file,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    content
                )

            self.save_project_metadata()

            self.editor_dirty = False

            self.editor_status.config(
                text=(
                    "Saved: "
                    + self.basic_file
                )
            )

            return True

        except Exception as e:

            messagebox.showerror(
                "Save Error",
                str(e)
            )

            return False

    # =====================================================
    # Ctrl-S
    # =====================================================

    def save_basic_event(
        self,
        event
    ):

        self.save_basic()

        return "break"

    # =====================================================
    # F5
    # =====================================================

    def build_project_event(
        self,
        event
    ):

        self.build_project()

        return "break"

    # =====================================================
    # Build
    # =====================================================

    def build_project(self):

        if not self.current_project_dir:

            messagebox.showwarning(
                "Build",
                "먼저 프로젝트를 생성하세요."
            )

            return

        # -------------------------------------------------
        # Save BASIC
        # -------------------------------------------------

        if not self.save_basic():

            return

        # -------------------------------------------------
        # Generate Verilog / PCF / IPLIB
        # -------------------------------------------------

        try:

            result = generate_verilog_and_pcf(
                bas_file=self.basic_file,
                board_name=self.current_board,
                BOARD_PINMAP=BOARD_PINMAP,
                project_dir=self.current_project_dir,
                project_name=self.current_module
            )

            # -------------------------------------------------
            # Metadata
            # -------------------------------------------------

            if not self.save_project_metadata(
                show_error=True
            ):

                return

            # -------------------------------------------------
            # Build Information
            # -------------------------------------------------

            button_info = result.get(
                "button_pins",
                {}
            )

            led_info = result.get(
                "led_pins",
                {}
            )

            info_text = (
                "Generated: "
                + os.path.basename(
                    result["verilog_file"]
                )
                + ", "
                + os.path.basename(
                    result["pcf_file"]
                )
                + ", IPLIB/uart_tx.v"
            )

            if button_info:

                info_text += (
                    f" | Buttons: "
                    f"{button_info}"
                )

            if led_info:

                info_text += (
                    f" | LEDs: "
                    f"{led_info}"
                )

            self.editor_status.config(
                text=info_text
            )

        except Exception as e:

            messagebox.showerror(
                "Build Error",
                "Verilog/PCF 생성 실패\n\n"
                + str(e)
            )

            return

        # -------------------------------------------------
        # build.bat
        # -------------------------------------------------

        app_dir = os.path.dirname(
            os.path.abspath(__file__)
        )

        build_bat = os.path.join(
            app_dir,
            "build.bat"
        )

        if not os.path.exists(
            build_bat
        ):

            messagebox.showerror(
                "Build Error",
                "build.bat 파일을 찾을 수 없습니다.\n\n"
                + build_bat
            )

            return

        try:

            self.editor_status.config(
                text=(
                    "Build console started: "
                    + self.current_module
                )
            )

            self.status.config(
                text=(
                    "Status: Running build.bat - "
                    + self.current_module
                )
            )

            subprocess.Popen(
                [
                    "cmd.exe",
                    "/k",
                    "call",
                    build_bat,
                    self.current_project_dir
                ],
                cwd=self.current_project_dir,
                creationflags=(
                    subprocess.CREATE_NEW_CONSOLE
                )
            )

        except Exception as e:

            messagebox.showerror(
                "Build Error",
                str(e)
            )

    # =====================================================
    # Editor Changed
    # =====================================================

    def on_editor_changed(
        self,
        event=None
    ):

        self.editor_dirty = True

        self.highlight_syntax()
        self.update_line_numbers()

    # =====================================================
    # Line Numbers
    # =====================================================

    def update_line_numbers(
        self,
        event=None
    ):

        lines = int(
            self.editor.index(
                "end-1c"
            ).split(".")[0]
        )

        line_text = "\n".join(
            str(i)
            for i in range(
                1,
                lines + 1
            )
        )

        self.line_numbers.config(
            state="normal"
        )

        self.line_numbers.delete(
            "1.0",
            tk.END
        )

        self.line_numbers.insert(
            "1.0",
            line_text
        )

        self.line_numbers.config(
            state="disabled"
        )

    # =====================================================
    # Scroll
    # =====================================================

    def on_editor_scroll(
        self,
        first,
        last
    ):

        self.line_numbers.yview_moveto(
            first
        )

    # =====================================================
    # Syntax Highlight
    # =====================================================

    def highlight_syntax(self):

        content = self.editor.get(
            "1.0",
            "end-1c"
        )

        for tag in [
            "keyword",
            "gpio",
            "number",
            "string",
            "comment"
        ]:

            self.editor.tag_remove(
                tag,
                "1.0",
                tk.END
            )

        gpio_commands = [
            "GPIO",
            "GPIOSET",
            "GPIOCLR",
            "GPIOREAD",
            "GPIOWRITE",
            "PINMODE",
            "DIGITALREAD",
            "DIGITALWRITE"
        ]

        basic_keywords = [
            "REM",   # completed
            "LET",
            "IF",    # completed
            "THEN",  # completed (UART,LED)
            "ELSE",  # completed (UART,LED)
            "ENDIF",
            "FOR",   # thinking  'counter' using ?
            "TO",
            "STEP",
            "NEXT",
            "WHILE", # conpleted (UART,LED)
            "WEND",  # checked
            "DO",    # do ~ while (testing)
            "LOOP",  # not using
            "GOTO",
            "GOSUB",
            "RETURN",
            "PRINT", # completed
            "INPUT",
            "WAIT",  # keep going
            "DELAY", # different function (how to implement)
            "END"    # checked
        ]

        for word in gpio_commands:

            pattern = (
                r"\b"
                + word
                + r"\b"
            )

            for match in re.finditer(
                pattern,
                content,
                re.IGNORECASE
            ):

                start = self.offset_to_index(
                    content,
                    match.start()
                )

                end = self.offset_to_index(
                    content,
                    match.end()
                )

                self.editor.tag_add(
                    "gpio",
                    start,
                    end
                )

        for word in basic_keywords:

            pattern = (
                r"\b"
                + word
                + r"\b"
            )

            for match in re.finditer(
                pattern,
                content,
                re.IGNORECASE
            ):

                start = self.offset_to_index(
                    content,
                    match.start()
                )

                end = self.offset_to_index(
                    content,
                    match.end()
                )

                self.editor.tag_add(
                    "keyword",
                    start,
                    end
                )

        for match in re.finditer(
            r"\b\d+\b",
            content
        ):

            start = self.offset_to_index(
                content,
                match.start()
            )

            end = self.offset_to_index(
                content,
                match.end()
            )

            self.editor.tag_add(
                "number",
                start,
                end
            )

        for match in re.finditer(
            r'"[^"]*"',
            content
        ):

            start = self.offset_to_index(
                content,
                match.start()
            )

            end = self.offset_to_index(
                content,
                match.end()
            )

            self.editor.tag_add(
                "string",
                start,
                end
            )

        for match in re.finditer(
            r"REM.*",
            content,
            re.IGNORECASE
        ):

            start = self.offset_to_index(
                content,
                match.start()
            )

            end = self.offset_to_index(
                content,
                match.end()
            )

            self.editor.tag_add(
                "comment",
                start,
                end
            )

    # =====================================================
    # Offset
    # =====================================================

    def offset_to_index(
        self,
        content,
        offset
    ):

        before = content[
            :offset
        ]

        line = (
            before.count("\n")
            + 1
        )

        if "\n" in before:

            column = len(
                before.rsplit(
                    "\n",
                    1
                )[-1]
            )

        else:

            column = len(
                before
            )

        return (
            f"{line}.{column}"
        )

    # =====================================================
    # Reset
    # =====================================================

    def reset(self):

        self.project_name.delete(
            0,
            tk.END
        )

        self.module_name.delete(
            0,
            tk.END
        )

        self.board.current(0)

        self.status.config(
            text="Status: Ready"
        )


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    app = App()

    app.mainloop()
