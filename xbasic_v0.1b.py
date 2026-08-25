import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import re
import json
import subprocess
import shutil


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

    """
    프로젝트 내부 IPLIB/uart_tx.v를 관리한다.

    없으면 생성.
    있으면 기존 파일을 그대로 사용.

    중요:
        프로젝트 루트에는 uart_tx.v를 생성하지 않는다.
        IP는 항상 IPLIB 아래에서 관리한다.
    """

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

    """
    project.json에 기록할 Verilog source 목록 생성.

    예:

        [
            "test.v",
            "IPLIB/uart_tx.v"
        ]
    """

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
# Generate Verilog / PCF
# =========================================================

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

    board_map = BOARD_PINMAP[board_name]

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
    # Verilog Name
    # =====================================================

    def to_verilog_name(name):

        name = re.sub(
            r'[^a-zA-Z0-9_]',
            '_',
            name
        )

        if name and name[0].isdigit():

            name = "_" + name

        return name

    # =====================================================
    # Signal Name
    # =====================================================

    def get_signal_name(
        rem_text,
        pin_number
    ):

        if rem_text:

            led_match = re.search(
                r'\bLED\s*0*(\d+)\b',
                rem_text,
                re.IGNORECASE
            )

            if led_match:

                led_number = int(
                    led_match.group(1)
                )

                return f"LED_{led_number:02d}"

        if pin_number in reverse_pin_map:

            return reverse_pin_map[
                pin_number
            ]

        return f"PIN_{pin_number}"

    # =====================================================
    # BASIC Analysis
    # =====================================================

    pin_info = {}

    print_messages = []

    current_rem = None

    for original_line in basic_code.splitlines():

        original_line = original_line.strip()

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
        # -------------------------------------------------

        match = re.match(
            r'^PRINT\s+"([^"]*)"\s*$',
            line,
            re.IGNORECASE
        )

        if match:

            print_messages.append(
                match.group(1)
            )

            continue

        # -------------------------------------------------
        # PINMODE
        # -------------------------------------------------

        match = re.match(
            r'^PINMODE\s+(\d+)\s*,\s*(OUTPUT|INPUT)',
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

            verilog_name = to_verilog_name(
                signal_name
            )

            pin_info[pin_number] = {

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

    # =====================================================
    # Module
    # =====================================================

    verilog.append(
        f"module {project_name} ("
    )

    ports = []

    if clock_pin is not None:

        ports.append(
            "    input wire clk"
        )

    if print_messages and uart_tx_pin is not None:

        ports.append(
            "    output wire UART_TX"
        )

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

            ports.append(
                f"    output wire {name}"
            )

        elif mode == "INPUT":

            ports.append(
                f"    input wire {name}"
            )

    verilog.append(
        ",\n".join(ports)
    )

    verilog.append(");")
    verilog.append("")

    # =====================================================
    # UART IP Instance
    # =====================================================

    if print_messages and uart_tx_pin is not None:

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
            "reg uart_start;"
        )

        verilog.append(
            "reg [7:0] uart_data;"
        )

        verilog.append(
            "wire uart_busy;"
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

        # =================================================
        # PRINT
        # =================================================

        message = print_messages[0]

        message_bytes = [
            ord(c) & 0xff
            for c in message
        ]

        message_bytes.append(0)

        verilog.append(
            "// ========================================================"
        )

        verilog.append(
            "// Xbasic PRINT"
        )

        verilog.append(
            f'// PRINT "{message}"'
        )

        verilog.append(
            "// ========================================================"
        )

        verilog.append("")

        # -------------------------------------------------
        # ROM
        # -------------------------------------------------

        verilog.append(
            "reg [7:0] print_rom [0:"
            f"{len(message_bytes) - 1}"
            "];"
        )

        verilog.append("")

        verilog.append(
            "initial begin"
        )

        for index, value in enumerate(
            message_bytes
        ):

            verilog.append(
                f"    print_rom[{index}] = "
                f"8'h{value:02X};"
            )

        verilog.append(
            "end"
        )

        verilog.append("")

        # -------------------------------------------------
        # FSM
        # -------------------------------------------------

        verilog.append(
            "reg [15:0] print_index;"
        )

        verilog.append(
            "reg print_done;"
        )

        verilog.append("")

        verilog.append(
            "always @(posedge clk) begin"
        )

        verilog.append("")

        verilog.append(
            "    if (!print_done) begin"
        )

        verilog.append("")

        verilog.append(
            "        if (!uart_busy && !uart_start) begin"
        )

        verilog.append("")

        verilog.append(
            "            if "
            "(print_rom[print_index] != 8'h00) begin"
        )

        verilog.append(
            "                uart_data <= "
            "print_rom[print_index];"
        )

        verilog.append(
            "                uart_start <= 1'b1;"
        )

        verilog.append("")

        verilog.append(
            "            end else begin"
        )

        verilog.append(
            "                print_done <= 1'b1;"
        )

        verilog.append(
            "            end"
        )

        verilog.append("")

        verilog.append(
            "        end else begin"
        )

        verilog.append(
            "            uart_start <= 1'b0;"
        )

        verilog.append(
            "        end"
        )

        verilog.append("")

        verilog.append(
            "        if (!uart_busy && "
            "!uart_start && "
            "print_rom[print_index] != 8'h00) begin"
        )

        verilog.append(
            "            if (print_index != "
            f"{len(message_bytes) - 1}) begin"
        )

        verilog.append(
            "                print_index <= "
            "print_index + 1'b1;"
        )

        verilog.append(
            "            end"
        )

        verilog.append(
            "        end"
        )

        verilog.append("")

        verilog.append(
            "    end else begin"
        )

        verilog.append(
            "        uart_start <= 1'b0;"
        )

        verilog.append(
            "    end"
        )

        verilog.append("")

        verilog.append(
            "end"
        )

        verilog.append("")

        # -------------------------------------------------
        # Initial
        # -------------------------------------------------

        verilog.append(
            "initial begin"
        )

        verilog.append(
            "    uart_start  = 1'b0;"
        )

        verilog.append(
            "    uart_data   = 8'h00;"
        )

        verilog.append(
            "    print_index = 0;"
        )

        verilog.append(
            "    print_done  = 1'b0;"
        )

        verilog.append(
            "end"
        )

        verilog.append("")

    # =====================================================
    # GPIO
    # =====================================================

    for pin_number, info in pin_info.items():

        if info["mode"] != "OUTPUT":
            continue

        state = info["state"]

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
    verilog.append("endmodule")

    verilog_code = "\n".join(
        verilog
    )

    # =====================================================
    # PCF
    # =====================================================

    pcf = []

    if clock_pin is not None:

        pcf.append(
            f"set_io clk {clock_pin}"
        )

    if print_messages and uart_tx_pin is not None:

        pcf.append(
            f"set_io UART_TX {uart_tx_pin}"
        )

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

        "verilog_file":
            verilog_file,

        "pcf_file":
            pcf_file,

        "uart_tx_file":
            uart_tx_file,

        "has_uart_ip":
            bool(
                print_messages
                and uart_tx_pin is not None
            ),

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
            "FPGA xBASIC v0.1b"
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
            label="Go to Project",
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
            text="FPGA BASIC Tool - Project Settings",
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
            text="Go to Project",
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
            width=5,
            padx=5,
            takefocus=0,
            border=0,
            background="#eeeeee",
            foreground="#555555",
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
            background="#1e1e1e",
            foreground="#d4d4d4",
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

    def create_hardware_panel(self, parent):

        panel = ttk.LabelFrame(
            parent,
            text="Hardware Module",
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
            text="Module Type"
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
            text="LED"
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
            text="GPIO Pin"
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
            text="Apply",
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
                f"\nREM {led} ON\n"
                f"PINMODE {pin}, OUTPUT\n"
                f"GPIOSET {pin}\n"
            )

        elif action == "OFF":

            code = (
                f"\nREM {led} OFF\n"
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
            text=f"Applied: {led} / GPIO {pin} / {action}"
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
            }
        }

        # -------------------------------------------------
        # UART IP는 프로젝트 생성 시점부터 등록
        # -------------------------------------------------

        sources = build_project_sources(
            self.current_project_dir,
            module,
            include_uart=True
        )

        return {

            "project": project_name,

            "top_module": module,

            "board": board,

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

        # -------------------------------------------------
        # 항상 IPLIB 확보
        # -------------------------------------------------

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

            board = info["board"]

            if board not in BOARD_PINMAP:

                raise ValueError(
                    f"지원하지 않는 Board입니다: {board}"
                )

            project_dir = os.path.dirname(
                os.path.abspath(path)
            )

            # -------------------------------------------------
            # IPLIB가 없으면 생성
            # -------------------------------------------------

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
                    "Module Editor - "
                    + self.current_module
                    + ".bas"
                )
            )

            self.goto_project_button.config(
                state="normal"
            )

            self.load_basic_file()

            # -------------------------------------------------
            # 기존 프로젝트도 메타데이터 정리
            # -------------------------------------------------

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
            # IPLIB 복사
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
            # Current Project 변경
            # -------------------------------------------------

            old_dir = self.current_project_dir
            old_project_name = self.current_project_name

            self.current_project_dir = project_dir
            self.current_project_name = project_name
            self.basic_file = new_basic

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

                self.current_project_dir = old_dir
                self.current_project_name = old_project_name

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

        project = self.project_name.get().strip()
        module = self.module_name.get().strip()
        board = self.board.get()

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

            basic_code = self.create_basic_template(
                module
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

            self.current_project_dir = project_dir
            self.current_project_name = project
            self.current_module = module
            self.current_board = board
            self.basic_file = basic_file
            self.project_json = None
            self.xbprj_file = None
            self.editor_dirty = False

            # =================================================
            # Project Metadata
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
                    "Module Editor - "
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

            # -------------------------------------------------
            # 프로젝트 메타데이터도 동시에 갱신
            # -------------------------------------------------

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
            # 매우 중요:
            # 생성 결과에 맞춰 project.json 갱신
            # -------------------------------------------------

            self.save_project_metadata(
                show_error=True
            )

            self.editor_status.config(
                text=(
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
                creationflags=subprocess.CREATE_NEW_CONSOLE
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
            "REM",
            "LET",
            "IF",
            "THEN",
            "ELSE",
            "ENDIF",
            "FOR",
            "TO",
            "STEP",
            "NEXT",
            "WHILE",
            "WEND",
            "DO",
            "LOOP",
            "GOTO",
            "GOSUB",
            "RETURN",
            "PRINT",
            "INPUT",
            "WAIT",
            "DELAY",
            "END"
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

        before = content[:offset]

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

        return f"{line}.{column}"

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
