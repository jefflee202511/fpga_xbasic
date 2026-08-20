import tkinter as tk
from tkinter import ttk, messagebox
import os
import re
import json


class App(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("FPGA Tool")
        self.geometry("1000x700")

        self.current_project_dir = None
        self.current_module = None
        self.current_board = None
        self.basic_file = None

        # -------------------------------------------------
        # Menu
        # -------------------------------------------------
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)

        file_menu.add_command(
            label="New Project",
            command=self.show_project_page
        )

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
        # 전체 Container
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

        self.create_project_page()
        self.create_editor_page()

        self.show_project_page()

        # Ctrl + S
        self.bind_all(
            "<Control-s>",
            self.save_basic_event
        )

    # =====================================================
    # Project Settings 화면
    # =====================================================
    def create_project_page(self):

        main = self.project_frame

        title = ttk.Label(
            main,
            text="FPGA Control - Project Settings",
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

        # -------------------------------------------------
        # Buttons
        # -------------------------------------------------
        button_frame = ttk.Frame(main)

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
            text="Generated File",
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
    # BASIC Editor 화면
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

        # -------------------------------------------------
        # Editor Main
        # -------------------------------------------------
        editor_container = ttk.Frame(
            self.editor_frame
        )

        editor_container.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10)
        )

        # -------------------------------------------------
        # Line Number
        # -------------------------------------------------
        self.line_numbers = tk.Text(
            editor_container,
            width=5,
            padx=5,
            takefocus=0,
            border=0,
            background="#eeeeee",
            foreground="#555555",
            state="disabled"
        )

        self.line_numbers.pack(
            side="left",
            fill="y"
        )

        # -------------------------------------------------
        # BASIC Editor
        # -------------------------------------------------
        editor_frame = ttk.Frame(
            editor_container
        )

        editor_frame.pack(
            side="left",
            fill="both",
            expand=True
        )

        self.editor = tk.Text(
            editor_frame,
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
        # Scrollbar
        # -------------------------------------------------
        scrollbar_y = ttk.Scrollbar(
            editor_frame,
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
            self.editor_frame,
            orient="horizontal",
            command=self.editor.xview
        )

        scrollbar_x.pack(
            fill="x",
            padx=10
        )

        self.editor.config(
            xscrollcommand=scrollbar_x.set
        )

        # -------------------------------------------------
        # Status
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

        # -------------------------------------------------
        # Syntax Tags
        # -------------------------------------------------

        # BASIC Keyword
        self.editor.tag_configure(
            "keyword",
            foreground="#569cd6"
        )

        # GPIO Command
        self.editor.tag_configure(
            "gpio",
            foreground="#4ec9b0"
        )

        # Number
        self.editor.tag_configure(
            "number",
            foreground="#b5cea8"
        )

        # String
        self.editor.tag_configure(
            "string",
            foreground="#ce9178"
        )

        # Comment
        self.editor.tag_configure(
            "comment",
            foreground="#6a9955"
        )

        # -------------------------------------------------
        # Event
        # -------------------------------------------------
        self.editor.bind(
            "<KeyRelease>",
            self.on_editor_changed
        )

        self.editor.bind(
            "<<Modified>>",
            self.on_text_modified
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
    # 화면 전환
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
    # 이름 정규화
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
    # Project 생성
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

        # Project만 입력
        if project and not module:

            module = project

        # Module만 입력
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

        # UI 반영
        self.project_name.delete(
            0,
            tk.END
        )

        self.project_name.insert(
            0,
            project
        )

        self.module_name.delete(
            0,
            tk.END
        )

        self.module_name.insert(
            0,
            module
        )

        # -------------------------------------------------
        # Project Directory
        # -------------------------------------------------
        project_dir = os.path.abspath(
            project
        )

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

                f.write(
                    verilog_code
                )

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

                f.write(
                    basic_code
                )

        # -------------------------------------------------
        # Board Info
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
        # project.json
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

            "tool": "FPGA Tool",

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
        # Project 정보 저장
        # -------------------------------------------------
        self.current_project_dir = project_dir

        self.current_module = module

        self.current_board = board

        self.basic_file = basic_file

        self.output_path.config(
            text=basic_file
        )

        self.status.config(
            text=f"Status: Created {project}"
        )

        # -------------------------------------------------
        # BASIC Editor 로드
        # -------------------------------------------------
        self.load_basic_file()

        self.editor_title.config(
            text=f"Module Editor - {module}.bas"
        )

        # -------------------------------------------------
        # 화면 전환
        # -------------------------------------------------
        self.show_editor_page()

    # =====================================================
    # BASIC 기본 템플릿
    # =====================================================
    def create_basic_template(self, module):

        return f"""REM ========================================
REM Module : {module}
REM FPGA BASIC Program
REM ========================================

PINMODE 0, OUTPUT
PINMODE 1, OUTPUT

GPIOSET 0
GPIOCLR 1

FOR I = 0 TO 10

    GPIOSET 0
    WAIT 100

    GPIOCLR 0
    WAIT 100

NEXT I

END
"""

    # =====================================================
    # BASIC File Load
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

            self.editor_status.config(
                text=f"Loaded: {self.basic_file}"
            )

        except Exception as e:

            messagebox.showerror(
                "Load Error",
                str(e)
            )

    # =====================================================
    # BASIC Save
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

                f.write(
                    content
                )

            self.editor_status.config(
                text=f"Saved: {self.basic_file}"
            )

        except Exception as e:

            messagebox.showerror(
                "Save Error",
                str(e)
            )

    def save_basic_event(self, event):

        self.save_basic()

        return "break"

    # =====================================================
    # Editor Changed
    # =====================================================
    def on_editor_changed(self, event=None):

        self.highlight_syntax()

        self.update_line_numbers()

    # =====================================================
    # Text Modified
    # =====================================================
    def on_text_modified(self, event=None):

        if self.editor.edit_modified():

            self.editor.edit_modified(
                False
            )

    # =====================================================
    # Line Number Update
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
    # Scroll Sync
    # =====================================================
    def on_editor_scroll(self, first, last):

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

        # 기존 Tag 제거
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
    # Offset -> Tk Text Index
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

        self.output_path.config(
            text="-"
        )

        self.status.config(
            text="Status: Ready"
        )


# =========================================================
# Main
# =========================================================
if __name__ == "__main__":

    app = App()

    app.mainloop()
