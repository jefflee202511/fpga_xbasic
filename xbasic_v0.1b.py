import tkinter as tk
from tkinter import ttk, messagebox
import os
import re
import json


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("FPGA Tool")
        self.geometry("650x500")

        # -------------------------------------------------
        # Menu
        # -------------------------------------------------
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Project")
        file_menu.add_command(label="Open")
        file_menu.add_command(label="Save")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)

        menubar.add_cascade(label="File", menu=file_menu)

        self.config(menu=menubar)

        # -------------------------------------------------
        # Main Frame
        # -------------------------------------------------
        main = ttk.Frame(self, padding=15)
        main.pack(fill="both", expand=True)

        # -------------------------------------------------
        # Title
        # -------------------------------------------------
        title = ttk.Label(
            main,
            text="FPGA Control",
            font=("Arial", 16, "bold")
        )
        title.pack(anchor="w", pady=(0, 15))

        # -------------------------------------------------
        # Project Settings
        # -------------------------------------------------
        setting = ttk.LabelFrame(
            main,
            text="Project Settings",
            padding=10
        )
        setting.pack(fill="x")

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
        button_frame.pack(fill="x", pady=15)

        ttk.Button(
            button_frame,
            text="Create Verilog",
            command=self.create_verilog
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
    # 이름 정규화
    # =====================================================
    def normalize_name(self, name):

        name = name.strip()

        # Verilog identifier에 사용할 수 없는 문자
        name = re.sub(
            r"[^a-zA-Z0-9_]",
            "_",
            name
        )

        # 숫자로 시작하면 _
        if name and name[0].isdigit():
            name = "_" + name

        return name

    # =====================================================
    # Verilog 생성
    # =====================================================
    def create_verilog(self):

        project = self.project_name.get().strip()
        module = self.module_name.get().strip()
        board = self.board.get()

        # ---------------------------------------------
        # 빈 이름 정책
        # ---------------------------------------------
        if not project and not module:

            messagebox.showerror(
                "Project Error",
                "Project Name 또는 Module Name을 입력하세요."
            )

            self.status.config(
                text="Status: Project name is empty"
            )

            return

        # Project만 입력
        if project and not module:

            module = project

            self.module_name.delete(
                0,
                tk.END
            )

            self.module_name.insert(
                0,
                module
            )

        # Module만 입력
        elif not project and module:

            project = module

            self.project_name.delete(
                0,
                tk.END
            )

            self.project_name.insert(
                0,
                project
            )

        # ---------------------------------------------
        # 이름 정규화
        # ---------------------------------------------
        project = self.normalize_name(project)
        module = self.normalize_name(module)

        if not project or not module:

            messagebox.showerror(
                "Name Error",
                "올바른 Project/Module 이름을 입력하세요."
            )

            return

        # UI에 반영
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

        # ---------------------------------------------
        # 프로젝트 디렉터리
        # ---------------------------------------------
        project_dir = os.path.abspath(project)

        os.makedirs(
            project_dir,
            exist_ok=True
        )

        # ---------------------------------------------
        # Verilog 파일
        # ---------------------------------------------
        verilog_file = os.path.join(
            project_dir,
            module + ".v"
        )

        verilog_code = f"""module {module} (
    input  wire clk,
    input  wire rst,
    output wire out
);

    // TODO:
    // Add your logic here.

    assign out = 1'b0;

endmodule
"""

        with open(
            verilog_file,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(verilog_code)

        # ---------------------------------------------
        # Board 정보
        # ---------------------------------------------
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

        # ---------------------------------------------
        # project.json
        # ---------------------------------------------
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
            "tool": "FPGA Tool",
            "language": "Verilog"
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

        # ---------------------------------------------
        # UI 표시
        # ---------------------------------------------
        self.output_path.config(
            text=verilog_file
        )

        self.status.config(
            text=f"Status: Created {project}/{module}.v"
        )

        messagebox.showinfo(
            "Verilog Created",
            f"Project created successfully.\n\n"
            f"Project : {project}\n"
            f"Module  : {module}\n"
            f"Board   : {board}\n\n"
            f"File:\n{verilog_file}"
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
