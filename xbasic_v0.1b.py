import tkinter as tk
from tkinter import ttk, messagebox
import os
import re
import json


class App(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("FPGA BASIC Tool")
        self.geometry("1100x700")
        self.minsize(900, 600)

        # =================================================
        # Project Information
        # =================================================
        self.current_project_dir = None
        self.current_module = None
        self.current_board = None
        self.basic_file = None

        # Editor 내용이 변경되었는지 확인
        self.editor_dirty = False

        # =================================================
        # Menu
        # =================================================
        menubar = tk.Menu(self)

        file_menu = tk.Menu(
            menubar,
            tearoff=0
        )

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

        file_menu.add_separator()

        file_menu.add_command(
            label="Exit",
            command=self.destroy
        )

        menubar.add_cascade(
            label="File",
            menu=file_menu
        )

        self.config(menu=menubar)

        # =================================================
        # Main Container
        # =================================================
        self.container = ttk.Frame(self)

        self.container.pack(
            fill="both",
            expand=True
        )

        # =================================================
        # Project Page
        # =================================================
        self.project_frame = ttk.Frame(
            self.container,
            padding=15
        )

        # =================================================
        # Editor Page
        # =================================================
        self.editor_frame = ttk.Frame(
            self.container
        )

        # =================================================
        # Create Pages
        # =================================================
        self.create_project_page()
        self.create_editor_page()

        self.show_project_page()

        # =================================================
        # Shortcut
        # =================================================
        self.bind_all(
            "<Control-s>",
            self.save_basic_event
        )

    # =====================================================
    # Project Settings Page
    # =====================================================
    def create_project_page(self):

        main = self.project_frame

        # -------------------------------------------------
        # Title
        # -------------------------------------------------
        title = ttk.Label(
            main,
            text="FPGA BASIC Tool - Project Settings",
            font=("Arial", 16, "bold")
        )

        title.pack(
            anchor="w",
            pady=(0, 15)
        )

        # -------------------------------------------------
        # Project Settings
        # -------------------------------------------------
        setting = ttk.LabelFrame(
            main,
            text="Project Settings",
            padding=10
        )

        setting.pack(
            fill="x"
        )

        # -------------------------------------------------
        # Project Name
        # -------------------------------------------------
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

        # -------------------------------------------------
        # Module Name
        # -------------------------------------------------
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

        # -------------------------------------------------
        # Board
        # -------------------------------------------------
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
            values=[
                "iCEsugar 1.5",
                "iCEBreaker 1.0e"
            ]
        )

        self.board.current(0)

        self.board.grid(
            row=2,
            column=1,
            padx=5,
            pady=5,
            sticky="w"
        )

        # =================================================
        # Buttons
        # =================================================
        button_frame = ttk.Frame(main)

        button_frame.pack(
            fill="x",
            pady=15
        )

        # -------------------------------------------------
        # Create Project
        # -------------------------------------------------
        ttk.Button(
            button_frame,
            text="Create Project",
            command=self.create_project
        ).pack(
            side="left",
            padx=5
        )

        # -------------------------------------------------
        # Go To Project
        # -------------------------------------------------
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

        # -------------------------------------------------
        # Reset
        # -------------------------------------------------
        ttk.Button(
            button_frame,
            text="Reset",
            command=self.reset
        ).pack(
            side="left",
            padx=5
        )

        # -------------------------------------------------
        # Generated File
        # -------------------------------------------------
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

        # -------------------------------------------------
        # Status
        # -------------------------------------------------
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

        # -------------------------------------------------
        # Top Bar
        # -------------------------------------------------
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

        # =================================================
        # Main Area
        # =================================================
        main_area = ttk.Frame(
            self.editor_frame
        )

        main_area.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10)
        )

        # =================================================
        # Left Editor Area
        # =================================================
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

        # -------------------------------------------------
        # Line Numbers
        # -------------------------------------------------
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

        # -------------------------------------------------
        # Editor Container
        # -------------------------------------------------
        text_frame = ttk.Frame(
            editor_container
        )

        text_frame.pack(
            side="left",
            fill="both",
            expand=True
        )

        # -------------------------------------------------
        # BASIC Editor
        # -------------------------------------------------
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

        # -------------------------------------------------
        # Vertical Scrollbar
        # -------------------------------------------------
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

        # -------------------------------------------------
        # Horizontal Scrollbar
        # -------------------------------------------------
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

        # =================================================
        # Hardware Panel
        # =================================================
        self.create_hardware_panel(
            main_area
        )

        # -------------------------------------------------
        # Editor Status
        # -------------------------------------------------
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

        # =================================================
        # Syntax Highlight Tags
        # =================================================
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

        # =================================================
        # Events
        # =================================================
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

        # -------------------------------------------------
        # Module Type
        # -------------------------------------------------
        ttk.Label(
            panel,
            text="Module Type"
        ).pack(
            anchor="w"
        )

        self.hardware_type = ttk.Combobox(
            panel,
            state="readonly",
            values=[
                "LED"
            ]
        )

        self.hardware_type.current(0)

        self.hardware_type.pack(
            fill="x",
            pady=(0, 15)
        )

        # -------------------------------------------------
        # LED Index
        # -------------------------------------------------
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

        # -------------------------------------------------
        # GPIO Pin
        # -------------------------------------------------
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

        # -------------------------------------------------
        # Action
        # -------------------------------------------------
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

        # -------------------------------------------------
        # Period
        # -------------------------------------------------
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

        # -------------------------------------------------
        # Apply
        # -------------------------------------------------
        ttk.Button(
            panel,
            text="Apply",
            command=self.apply_hardware
        ).pack(
            fill="x"
        )

    # =====================================================
    # Hardware Apply
    # =====================================================
    def apply_hardware(self):

        module_type = self.hardware_type.get()

        if module_type == "LED":

            self.apply_led()

    # =====================================================
    # LED Apply
    # =====================================================
    def apply_led(self):

        led = self.led_index.get()

        pin = self.gpio_pin.get().strip()

        action = self.led_action.get()

        period = self.led_period.get().strip()

        # -------------------------------------------------
        # Validation
        # -------------------------------------------------
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

        # -------------------------------------------------
        # Generate BASIC Code
        # -------------------------------------------------
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

        # -------------------------------------------------
        # Insert At Cursor
        # -------------------------------------------------
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
    # Show Project Page
    # =====================================================
    def show_project_page(self):

        self.editor_frame.pack_forget()

        self.project_frame.pack(
            fill="both",
            expand=True
        )

    # =====================================================
    # Show Editor Page
    # =====================================================
    def show_editor_page(self):

        self.project_frame.pack_forget()

        self.editor_frame.pack(
            fill="both",
            expand=True
        )

        self.editor.focus_set()

    # =====================================================
    # Go To Existing Project
    # =====================================================
    def go_to_project(self):

        if not self.current_project_dir:

            messagebox.showwarning(
                "Project",
                "먼저 프로젝트를 생성하세요."
            )

            return

        # 중요:
        # 여기서는 load_basic_file()을 호출하지 않는다.
        # 현재 메모리에 있는 Editor 내용을 그대로 유지한다.

        self.show_editor_page()

        self.editor_status.config(
            text=f"Project: {self.current_module}"
        )

    # =====================================================
    # Normalize Name
    # =====================================================
    def normalize_name(self, name):

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

        # -------------------------------------------------
        # Validation
        # -------------------------------------------------
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

        project = self.normalize_name(project)
        module = self.normalize_name(module)

        if not project or not module:

            messagebox.showerror(
                "Name Error",
                "올바른 Project/Module 이름을 입력하세요."
            )

            return

        # -------------------------------------------------
        # Project Directory
        # -------------------------------------------------
        project_dir = os.path.abspath(project)

        # =================================================
        # IMPORTANT
        # 이미 현재 열려있는 프로젝트라면
        # 파일을 다시 로드하지 않고 에디터로 이동
        # =================================================
        if (
            self.current_project_dir == project_dir
            and self.current_module == module
        ):

            self.go_to_project()

            return

        # -------------------------------------------------
        # New Project Directory
        # -------------------------------------------------
        os.makedirs(
            project_dir,
            exist_ok=True
        )

        # -------------------------------------------------
        # Verilog File
        # -------------------------------------------------
        verilog_file = os.path.join(
            project_dir,
            module + ".v"
        )

        if not os.path.exists(verilog_file):

            verilog_code = f"""module {module} (
    input wire clk,
    input wire rst,
    output wire out
);

    assign out = 1'b0;

endmodule
"""

            with open(
                verilog_file,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(verilog_code)

        # -------------------------------------------------
        # BASIC File
        # -------------------------------------------------
        basic_file = os.path.join(
            project_dir,
            module + ".bas"
        )

        if not os.path.exists(basic_file):

            basic_code = self.create_basic_template(
                module
            )

            with open(
                basic_file,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(basic_code)

        # -------------------------------------------------
        # Board Information
        # -------------------------------------------------
        board_info = {

            "iCEsugar 1.5": {
                "family": "ice40",
                "device": "up5k",
                "tool": "nextpnr-ice40"
            },

            "iCEBreaker 1.0e": {
                "family": "ice40",
                "device": "up5k",
                "tool": "nextpnr-ice40"
            }
        }

        # -------------------------------------------------
        # Project JSON
        # -------------------------------------------------
        project_info = {

            "project": project,

            "top_module": module,

            "board": board,

            "board_info": board_info.get(
                board,
                {}
            ),

            "sources": [
                module + ".v"
            ],

            "basic_source": module + ".bas",

            "tool": "FPGA BASIC Tool",

            "language": "BASIC"
        }

        project_json = os.path.join(
            project_dir,
            "project.json"
        )

        with open(
            project_json,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                project_info,
                f,
                indent=4
            )

        # -------------------------------------------------
        # Save Current Project Info
        # -------------------------------------------------
        self.current_project_dir = project_dir
        self.current_module = module
        self.current_board = board
        self.basic_file = basic_file

        self.editor_dirty = False

        # -------------------------------------------------
        # Update Project Page
        # -------------------------------------------------
        self.output_path.config(
            text=basic_file
        )

        self.status.config(
            text=f"Status: Project opened - {project}"
        )

        # -------------------------------------------------
        # Editor Title
        # -------------------------------------------------
        self.editor_title.config(
            text=f"Module Editor - {module}.bas"
        )

        # -------------------------------------------------
        # Enable Go To Project
        # -------------------------------------------------
        self.goto_project_button.config(
            state="normal"
        )

        # -------------------------------------------------
        # Load BASIC File
        #
        # 새로운 프로젝트로 전환할 때만 실행
        # -------------------------------------------------
        self.load_basic_file()

        # -------------------------------------------------
        # Switch To Editor
        # -------------------------------------------------
        self.show_editor_page()

    # =====================================================
    # BASIC Template
    # =====================================================
    def create_basic_template(self, module):

        return f"""REM ========================================
REM Module : {module}
REM FPGA BASIC Program
REM ========================================

REM Write your FPGA BASIC code here.

END
"""

    # =====================================================
    # Load BASIC File
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
                text=f"Loaded: {self.basic_file}"
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

            return

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

                f.write(content)

            self.editor_dirty = False

            self.editor_status.config(
                text=f"Saved: {self.basic_file}"
            )

        except Exception as e:

            messagebox.showerror(
                "Save Error",
                str(e)
            )

    # =====================================================
    # Ctrl + S
    # =====================================================
    def save_basic_event(self, event):

        self.save_basic()

        return "break"

    # =====================================================
    # Editor Changed
    # =====================================================
    def on_editor_changed(self, event=None):

        self.editor_dirty = True

        self.highlight_syntax()

        self.update_line_numbers()

    # =====================================================
    # Update Line Numbers
    # =====================================================
    def update_line_numbers(self, event=None):

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
    # Scroll Synchronization
    # =====================================================
    def on_editor_scroll(self, first, last):

        self.line_numbers.yview_moveto(first)

    # =====================================================
    # Syntax Highlight
    # =====================================================
    def highlight_syntax(self):

        content = self.editor.get(
            "1.0",
            "end-1c"
        )

        # -------------------------------------------------
        # Remove Existing Tags
        # -------------------------------------------------
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

        # -------------------------------------------------
        # GPIO Commands
        # -------------------------------------------------
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

        # -------------------------------------------------
        # BASIC Keywords
        # -------------------------------------------------
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

        # -------------------------------------------------
        # GPIO Highlight
        # -------------------------------------------------
        for word in gpio_commands:

            pattern = r"\b" + word + r"\b"

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

        # -------------------------------------------------
        # BASIC Keyword Highlight
        # -------------------------------------------------
        for word in basic_keywords:

            pattern = r"\b" + word + r"\b"

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

        # -------------------------------------------------
        # Number Highlight
        # -------------------------------------------------
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

        # -------------------------------------------------
        # String Highlight
        # -------------------------------------------------
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

        # -------------------------------------------------
        # REM Comment Highlight
        # -------------------------------------------------
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
    # Offset To Tk Index
    # =====================================================
    def offset_to_index(
        self,
        content,
        offset
    ):

        before = content[:offset]

        line = before.count(
            "\n"
        ) + 1

        if "\n" in before:

            column = len(
                before.rsplit(
                    "\n",
                    1
                )[-1]
            )

        else:

            column = len(before)

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

        # 현재 프로젝트 자체는 삭제하지 않음.
        # 새 프로젝트 이름을 입력하기 위한 UI 초기화만 수행.
        self.status.config(
            text="Status: Ready"
        )


# =========================================================
# Main
# =========================================================
if __name__ == "__main__":

    app = App()

    app.mainloop()
