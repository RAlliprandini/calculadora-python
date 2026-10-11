"""Calculadora com interface gráfica feita em Tkinter (sem dependências externas)."""

import ast
import math
import operator
import re
import tkinter as tk

# ---------------------------------------------------------------------------
# Paleta de cores
# ---------------------------------------------------------------------------
BG = "#0f1117"
TEXT = "#f4f4f8"
MUTED = "#7b8199"

NUM_BG, NUM_HOVER, NUM_PRESS = "#1d2130", "#272c3f", "#323850"
FUNC_BG, FUNC_HOVER, FUNC_PRESS = "#262b3d", "#30364c", "#3b425c"
FUNC_FG = "#a5b4fc"
OP_BG, OP_HOVER, OP_PRESS = "#2a2547", "#352e5c", "#40386f"
OP_FG = "#c4b5fd"
EQ_BG, EQ_HOVER, EQ_PRESS = "#7c5cff", "#8f74ff", "#6a4be6"

FONT = "Segoe UI"
OPERATORS = "+-*/"

# ---------------------------------------------------------------------------
# Lógica matemática
# ---------------------------------------------------------------------------
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def safe_eval(expr: str) -> float:
    """Avalia uma expressão aritmética simples sem usar eval()."""

    def _ev(node):
        if isinstance(node, ast.Expression):
            return _ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return _BIN_OPS[type(node.op)](_ev(node.left), _ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = _ev(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        raise ValueError("Expressão inválida")

    return _ev(ast.parse(expr, mode="eval"))


def format_number(value: float) -> str:
    """Formata o resultado: inteiros sem '.0' e no máximo 10 dígitos significativos."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        raise ValueError("Resultado inválido")
    if float(value).is_integer() and abs(value) < 1e15:
        return str(int(value))
    return f"{value:.10g}"


def pretty(expr: str) -> str:
    """Converte a expressão interna para exibição (× ÷ − com espaçamento)."""
    symbols = {"+": "+", "-": "−", "*": "×", "/": "÷"}
    out = []
    for i, ch in enumerate(expr):
        if ch in symbols:
            prev = expr[i - 1] if i > 0 else ""
            is_binary = prev and prev not in OPERATORS and prev != "e"
            out.append(f" {symbols[ch]} " if is_binary else symbols[ch])
        else:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# Componentes visuais
# ---------------------------------------------------------------------------
def rounded_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class RoundButton(tk.Canvas):
    """Botão arredondado com efeitos de hover e clique."""

    def __init__(self, master, text, command, colors, fg, width, height, radius, font):
        super().__init__(
            master, width=width, height=height, bg=BG,
            highlightthickness=0, bd=0, cursor="hand2",
        )
        self.command = command
        self.bg, self.hover, self.press = colors
        self._inside = False

        self.shape = rounded_rect(self, 1, 1, width - 1, height - 1, radius, fill=self.bg, outline="")
        self.create_text(width / 2, height / 2, text=text, fill=fg, font=font)

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", lambda _e: self._fill(self.press))
        self.bind("<ButtonRelease-1>", self._on_release)

    def _fill(self, color):
        self.itemconfig(self.shape, fill=color)

    def _on_enter(self, _event):
        self._inside = True
        self._fill(self.hover)

    def _on_leave(self, _event):
        self._inside = False
        self._fill(self.bg)

    def _on_release(self, _event):
        if self._inside:
            self._fill(self.hover)
            self.command()
        else:
            self._fill(self.bg)

    def flash(self):
        """Animação curta usada quando a tecla correspondente é pressionada."""
        self._fill(self.press)
        self.after(120, lambda: self._fill(self.hover if self._inside else self.bg))


# ---------------------------------------------------------------------------
# Aplicação
# ---------------------------------------------------------------------------
class Calculator:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.expr = ""
        self.history = ""
        self.error = None
        self.just_evaluated = False
        self.buttons = {}

        scale = root.winfo_fpixels("1i") / 96.0
        self.btn_w, self.btn_h = int(78 * scale), int(64 * scale)
        self.radius = int(18 * scale)
        self.gap = int(5 * scale)

        root.title("Calculadora")
        root.configure(bg=BG)
        root.resizable(False, False)

        self._build_display()
        self._build_keypad()
        self._refresh()

        root.bind("<Key>", self._on_key)
        root.bind("<Control-c>", self._copy_result)

    # ---------- Interface ----------
    def _build_display(self):
        frame = tk.Frame(self.root, bg=BG)
        frame.pack(fill="x", padx=22, pady=(24, 10))

        self.preview_label = tk.Label(
            frame, text="", bg=BG, fg=MUTED, font=(FONT, 14), anchor="e",
        )
        self.preview_label.pack(fill="x")

        self.main_label = tk.Label(
            frame, text="0", bg=BG, fg=TEXT, font=(FONT, 36, "bold"), anchor="e",
        )
        self.main_label.pack(fill="x")

    def _build_keypad(self):
        num = ((NUM_BG, NUM_HOVER, NUM_PRESS), TEXT)
        func = ((FUNC_BG, FUNC_HOVER, FUNC_PRESS), FUNC_FG)
        op = ((OP_BG, OP_HOVER, OP_PRESS), OP_FG)
        eq = ((EQ_BG, EQ_HOVER, EQ_PRESS), "#ffffff")

        def d(n):
            return (n, num, lambda: self.input_digit(n))

        layout = [
            [("C", func, self.clear), ("⌫", func, self.backspace),
             ("%", func, self.percent), ("÷", op, lambda: self.input_operator("/"))],
            [d("7"), d("8"), d("9"), ("×", op, lambda: self.input_operator("*"))],
            [d("4"), d("5"), d("6"), ("−", op, lambda: self.input_operator("-"))],
            [d("1"), d("2"), d("3"), ("+", op, lambda: self.input_operator("+"))],
            [("±", func, self.toggle_sign), d("0"), (".", num, self.input_dot),
             ("=", eq, self.equals)],
        ]

        pad = tk.Frame(self.root, bg=BG)
        pad.pack(padx=17, pady=(0, 18))

        for r, row in enumerate(layout):
            for c, (label, (colors, fg), command) in enumerate(row):
                btn = RoundButton(
                    pad, label, command, colors, fg,
                    self.btn_w, self.btn_h, self.radius, (FONT, 18),
                )
                btn.grid(row=r, column=c, padx=self.gap, pady=self.gap)
                self.buttons[label] = btn

    def _refresh(self):
        if self.error:
            main, size = self.error, 16
        else:
            main = pretty(self.expr) or "0"
            size = 36 if len(main) <= 11 else max(16, int(36 * 11 / len(main)))
        self.main_label.config(text=main, font=(FONT, size, "bold"))

        if self.just_evaluated or self.error:
            preview = self.history
        else:
            preview = self._live_preview()
        self.preview_label.config(text=preview)

    def _live_preview(self) -> str:
        body = self.expr.lstrip("-")
        if not any(o in body for o in OPERATORS) or self.expr[-1:] in OPERATORS:
            return ""
        try:
            return "= " + format_number(safe_eval(self.expr))
        except Exception:
            return ""

    # ---------- Ações ----------
    def _current_number(self):
        return re.search(r"(\d+\.?\d*|\.\d+)$", self.expr)

    def _start_new_if_needed(self):
        self.error = None
        if self.just_evaluated:
            self.expr = ""
            self.just_evaluated = False

    def input_digit(self, digit: str):
        self._start_new_if_needed()
        match = self._current_number()
        if match and match.group() == "0":
            self.expr = self.expr[:-1] + digit  # evita zeros à esquerda
        else:
            self.expr += digit
        self._refresh()

    def input_dot(self):
        self._start_new_if_needed()
        match = self._current_number()
        if match and "." in match.group():
            return
        self.expr += "." if match else "0."
        self._refresh()

    def input_operator(self, op: str):
        self.error = None
        self.just_evaluated = False  # continua a conta a partir do resultado
        if not self.expr:
            if op == "-":
                self.expr = "-"
        elif self.expr[-1] in OPERATORS:
            if self.expr != "-":
                self.expr = self.expr[:-1] + op
        else:
            self.expr += op
        self._refresh()

    def clear(self):
        self.expr, self.history, self.error = "", "", None
        self.just_evaluated = False
        self._refresh()

    def backspace(self):
        if self.just_evaluated or self.error:
            self.clear()
            return
        self.expr = self.expr[:-1]
        self._refresh()

    def percent(self):
        self.error = None
        match = self._current_number()
        if not match:
            return
        value = float(match.group()) / 100
        self.expr = self.expr[: match.start()] + format_number(value)
        self.just_evaluated = False
        self._refresh()

    def toggle_sign(self):
        self.error = None
        match = self._current_number()
        if not match:
            return
        prefix, number = self.expr[: match.start()], match.group()
        unary_minus = prefix.endswith("-") and (len(prefix) == 1 or prefix[-2] in OPERATORS)
        prefix = prefix[:-1] if unary_minus else prefix + "-"
        self.expr = prefix + number
        self.just_evaluated = False
        self._refresh()

    def equals(self):
        expr = self.expr.rstrip(OPERATORS)
        if not expr or self.just_evaluated:
            return
        self.history = pretty(expr) + " ="
        try:
            self.expr = format_number(safe_eval(expr))
        except ZeroDivisionError:
            self._set_error("Não é possível dividir por zero")
            return
        except Exception:
            self._set_error("Erro")
            return
        self.just_evaluated = True
        self._refresh()

    def _set_error(self, message: str):
        self.error = message
        self.expr = ""
        self.just_evaluated = True
        self._refresh()

    def _copy_result(self, _event=None):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.expr or "0")

    # ---------- Teclado ----------
    def _on_key(self, event):
        keymap = {"+": "+", "-": "−", "*": "×", "x": "×", "/": "÷",
                  ".": ".", ",": ".", "%": "%", "=": "="}
        special = {"Return": "=", "KP_Enter": "=", "BackSpace": "⌫",
                   "Escape": "C", "Delete": "C"}

        if event.state & 0x4:  # Ctrl pressionado: deixa os atalhos passarem
            return
        if event.char.isdigit():
            label = event.char
        else:
            label = keymap.get(event.char) or special.get(event.keysym)

        button = self.buttons.get(label)
        if button:
            button.flash()
            button.command()


def _enable_high_dpi():
    """Deixa o texto nítido em telas com escala no Windows."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def main():
    _enable_high_dpi()
    root = tk.Tk()
    Calculator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
