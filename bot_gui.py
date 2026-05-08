"""
쿠팡이츠 자동 수락 봇 GUI · 탄이 마스코트 대시보드
"""

import tkinter as tk
import threading
import json
import time
import os
import platform

import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageFilter

# bot.py의 검증된 헬퍼를 그대로 사용 (Retina 스케일링, osascript 클릭 등)
import bot


def resource_path(relative):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)


if platform.system() == "Darwin":
    KFONT = "Apple SD Gothic Neo"
else:
    KFONT = "맑은 고딕"

MASCOT_IMG = resource_path("tan.jpeg")

FONT_XS = 11
FONT_SM = 13
FONT_MD = 15
FONT_LG = 18
FONT_COUNT = 54

# 봇 동작 파라미터는 bot 모듈 값을 사용
PLUS5_REPEAT = bot.PLUS5_REPEAT
CLICK_DELAY  = bot.CLICK_DELAY
POST_ACCEPT  = bot.POST_ACCEPT_DELAY
SCAN_INTERVAL = bot.SCAN_INTERVAL


# ─── 컬러 팔레트 ───
CORAL       = "#FF7A59"
CORAL_LIGHT = "#FFA68F"
CORAL_DARK  = "#E5613F"
CREAM       = "#F8F4EE"
CREAM_DARK  = "#EFE8DD"
MINT        = "#7ED6C1"
MINT_LIGHT  = "#A8E6D5"
MINT_DARK   = "#5BC0A8"
TEXT_MAIN   = "#2B2B2B"
TEXT_SUB    = "#8B8B8B"
TEXT_HINT   = "#C0BAB3"
CARD_BG     = "#FFFFFF"
BADGE_RUN   = "#7ED6C1"
BADGE_WAIT  = "#D9D5CE"
BADGE_ERR   = "#F2A4A4"
ERR_TEXT    = "#D86464"


# ─── 봇 로직 ───

def bot_loop(running_flag, status_cb, count_cb):
    try:
        with open(bot.CONFIG_FILE) as f:
            offsets = json.load(f)
    except Exception:
        status_cb(("error", "offsets.json을 찾을 수 없어요"))
        return

    count = 0
    status_cb(("waiting", "탄이가 주문 찾는 중!"))

    while running_flag():
        try:
            screen = bot.grab()
            popup = bot.find_popup(screen)  # 논리좌표로 반환됨 (Retina 변환 포함)
            if popup:
                px, py = popup[0], popup[1]
                status_cb(("running", "주문 발견! 잠시 후 수락 시작..."))

                # 팝업 완전히 렌더링될 때까지 대기 (사용자 개입 여지도 줌)
                time.sleep(bot.DETECT_DELAY)
                status_cb(("running", "수락 중..."))

                # 팝업을 한 번 클릭해 POS 창에 포커스 (macOS)
                if platform.system() == "Darwin":
                    bot.click_at(px, py)
                    time.sleep(0.2)

                tx = px + offsets["plus5_dx"]
                ty = py + offsets["plus5_dy"]
                for _ in range(PLUS5_REPEAT):
                    bot.click_at(tx, ty)
                    time.sleep(CLICK_DELAY)

                time.sleep(0.3)

                # 수락 클릭 — 이미지 매칭 우선, 실패 시 오프셋 fallback
                accept_pos = bot.find_accept_button(bot.grab())
                if accept_pos:
                    ax, ay = accept_pos[0], accept_pos[1]
                else:
                    ax = px + offsets["accept_dx"]
                    ay = py + offsets["accept_dy"]
                bot.click_at(ax, ay)

                # 폴링으로 팝업 사라지는 순간 감지 — 연이은 주문이 들어와도
                # 이전 팝업 닫힘과 새 팝업 사이의 짧은 공백을 잡아냄.
                # (단발 검사 방식은 새 팝업을 "안 사라진 팝업"으로 오인했음)
                disappeared = False
                for _ in range(13):  # 약 2초간 폴링
                    time.sleep(0.15)
                    if bot.find_popup(bot.grab()) is None:
                        disappeared = True
                        break

                if disappeared:
                    count += 1
                    count_cb(count)
                    status_cb(("running", "수락 완료! 잘했어요 탄이!"))
                    time.sleep(POST_ACCEPT)
                    status_cb(("waiting", "탄이가 주문 찾는 중!"))
                else:
                    # 2초간 팝업 공백을 못 잡음 — 다음 루프가 처리.
                    # (진짜 클릭 실패면 같은 팝업 재시도, 너무 빠른 연속 주문이면 새 팝업 정상 처리)
                    status_cb(("running", "다음 주문 확인 중..."))

        except Exception as e:
            status_cb(("error", f"오류: {e}"))

        time.sleep(SCAN_INTERVAL)


# ─── PIL 헬퍼 ───

def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def make_mascot(path, size=120, ring=CORAL, ring_w=4):
    """탄이 사진을 원형으로 자르고 코랄 링을 두름."""
    pad = 6
    cs = size + 2 * pad
    canvas = Image.new("RGBA", (cs, cs), (0, 0, 0, 0))

    img = Image.open(path).convert("RGBA")
    w, h = img.size
    side = min(w, h)
    img = img.crop(((w - side) // 2, (h - side) // 2,
                    (w + side) // 2, (h + side) // 2))
    img = img.resize((size, size), Image.LANCZOS)

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    pos = (pad, pad)
    canvas.paste(img, pos, mask)

    rd = ImageDraw.Draw(canvas)
    rd.ellipse(
        (pos[0] - ring_w // 2, pos[1] - ring_w // 2,
         pos[0] + size + ring_w // 2, pos[1] + size + ring_w // 2),
        outline=ring, width=ring_w,
    )
    return canvas


CARD_SHADOW_PAD = 40    # 카드 그림자 블러가 잘리지 않도록 충분한 여백 확보


def make_card(width, height, radius=22, fill=CARD_BG,
              shadow=True, shadow_alpha=30, blur=14, dy=8):
    """둥근 흰 카드 + 부드러운 그림자."""
    pad = CARD_SHADOW_PAD if shadow else 0
    canvas = Image.new("RGBA", (width + 2 * pad, height + 2 * pad), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        sd.rounded_rectangle(
            (pad, pad + dy, pad + width, pad + height + dy),
            radius=radius, fill=(0, 0, 0, shadow_alpha),
        )
        canvas = Image.alpha_composite(canvas, sh.filter(ImageFilter.GaussianBlur(blur)))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((pad, pad, pad + width, pad + height), radius=radius, fill=fill)
    return canvas


BTN_PAD_TOP    = 8       # 버튼 그림자는 아래로 떨어지므로 위는 좁게
BTN_PAD_BOTTOM = 28
BTN_PAD_X      = 16


def make_gradient_button(width, height, c1, c2, radius=24):
    """가로 그라데이션 + 아래로 떨어지는 컬러 그림자가 있는 둥근 버튼."""
    canvas_w = width + 2 * BTN_PAD_X
    canvas_h = height + BTN_PAD_TOP + BTN_PAD_BOTTOM
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    rgb1 = np.array(_hex(c1), dtype=np.float32)
    rgb2 = np.array(_hex(c2), dtype=np.float32)
    t = np.linspace(0, 1, width).reshape(1, -1, 1)
    grad = (rgb1 + (rgb2 - rgb1) * t).astype(np.uint8)
    grad = np.broadcast_to(grad, (height, width, 3)).copy()
    alpha = np.full((height, width, 1), 255, dtype=np.uint8)
    grad_img = Image.fromarray(np.concatenate([grad, alpha], axis=2), "RGBA")

    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width, height), radius=radius, fill=255)

    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle(
        (BTN_PAD_X, BTN_PAD_TOP + 7, BTN_PAD_X + width, BTN_PAD_TOP + height + 7),
        radius=radius, fill=_hex(c2) + (110,),
    )
    canvas = Image.alpha_composite(canvas, sh.filter(ImageFilter.GaussianBlur(8)))

    rounded = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    rounded.paste(grad_img, (0, 0), mask)
    canvas.paste(rounded, (BTN_PAD_X, BTN_PAD_TOP), rounded)
    return canvas


# ─── 위젯 ───

class GradientButton(tk.Canvas):
    """그라데이션 + 그림자가 있는 둥근 버튼."""

    def __init__(self, parent, width, height, text,
                 c1=CORAL_LIGHT, c2=CORAL, command=None,
                 fg="white", font=None, radius=24):
        bg = parent.cget("bg")
        super().__init__(parent,
                         width=width + 2 * BTN_PAD_X,
                         height=height + BTN_PAD_TOP + BTN_PAD_BOTTOM,
                         highlightthickness=0, bd=0, bg=bg)
        # NOTE: tk.Canvas uses self._w internally as the Tcl widget pathname,
        # so we name our own dimensions differently.
        self.btn_w = width
        self.btn_h = height
        self.text = text
        self.c1, self.c2 = c1, c2
        self.fg = fg
        self.font = font or (KFONT, 13, "bold")
        self.radius = radius
        self.command = command
        self._img = None
        self._render()
        self.bind("<Button-1>", lambda e: self.command and self.command())
        self.bind("<Enter>", lambda e: self.config(cursor="hand2"))

    def _render(self):
        img = make_gradient_button(self.btn_w, self.btn_h, self.c1, self.c2, self.radius)
        self._img = ImageTk.PhotoImage(img)
        self.delete("all")
        self.create_image(0, 0, image=self._img, anchor="nw")
        cx = BTN_PAD_X + self.btn_w // 2
        cy = BTN_PAD_TOP + self.btn_h // 2
        self.create_text(cx, cy, text=self.text, fill=self.fg, font=self.font)

    def set_state(self, c1, c2, text=None):
        self.c1, self.c2 = c1, c2
        if text is not None:
            self.text = text
        self._render()


# ─── App ───

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("쿠팡이츠 · 탄이 봇")
        self.geometry("440x710")
        self.resizable(False, False)
        self.configure(bg=CREAM)
        self.attributes("-topmost", True)

        self._running = False
        self._thread = None
        self._count = 0
        self._refs = {}                     # PhotoImage 참조 유지

        self._dot_idx = 0

        self._build_ui()
        self._animate_dots()

    # ─── 빌드 ───
    def _build_ui(self):
        self._build_mascot()
        self._build_stat_card()
        self._build_button()

        tk.Label(
            self, text="종료하려면 창을 닫으세요",
            font=(KFONT, FONT_SM), fg=TEXT_HINT, bg=CREAM,
        ).pack(pady=(8, 0))

    def _build_mascot(self):
        size = 120
        cs = size + 12  # ring 여유만 (glow 없음)
        self.mascot_canvas = tk.Canvas(
            self, width=cs, height=cs,
            bg=CREAM, highlightthickness=0, bd=0,
        )
        self.mascot_canvas.pack(pady=(14, 2))

        try:
            self._refs["mascot"] = ImageTk.PhotoImage(make_mascot(MASCOT_IMG, size=size))
            self._mascot_id = self.mascot_canvas.create_image(
                cs // 2, cs // 2, image=self._refs["mascot"],
            )
        except Exception:
            self._mascot_id = self.mascot_canvas.create_text(
                cs // 2, cs // 2, text="🐶",
                font=("Apple Color Emoji" if platform.system() == "Darwin" else KFONT, 60),
            )

        tk.Label(
            self, text="탄이",
            font=(KFONT, FONT_LG, "bold"),
            fg=TEXT_MAIN, bg=CREAM,
        ).pack(pady=(8, 0))
        tk.Label(
            self, text="오늘도 열일하는 탄이 🐶",
            font=(KFONT, FONT_SM),
            fg=TEXT_SUB, bg=CREAM,
        ).pack(pady=(2, 8))

    def _build_stat_card(self):
        card_w, card_h = 350, 250
        canvas_w = card_w + 2 * CARD_SHADOW_PAD
        canvas_h = card_h + 2 * CARD_SHADOW_PAD
        self.card_canvas = tk.Canvas(
            self, width=canvas_w, height=canvas_h,
            bg=CREAM, highlightthickness=0, bd=0,
        )
        self.card_canvas.pack()

        self._refs["card"] = ImageTk.PhotoImage(make_card(card_w, card_h))
        self.card_canvas.create_image(0, 0, image=self._refs["card"], anchor="nw")

        # 카드 내부 시작 좌표 (그림자 padding 만큼 안쪽)
        x0, y0 = CARD_SHADOW_PAD, CARD_SHADOW_PAD

        # 상태 배지
        self._badge_dot = self.card_canvas.create_oval(
            x0 + 24, y0 + 27, x0 + 35, y0 + 38,
            fill=BADGE_WAIT, outline="",
        )
        self._badge_text = self.card_canvas.create_text(
            x0 + 44, y0 + 32, text="대기 중",
            fill=TEXT_SUB, font=(KFONT, FONT_SM, "bold"), anchor="w",
        )

        # 라벨
        self.card_canvas.create_text(
            x0 + card_w // 2, y0 + 60,
            text="오늘 수락 건수",
            fill=TEXT_SUB, font=(KFONT, FONT_SM),
        )

        # 숫자 + "건" — grid의 sticky="s"로 baseline 정렬
        count_frame = tk.Frame(self.card_canvas, bg=CARD_BG)
        self.count_var = tk.StringVar(value="0")
        tk.Label(
            count_frame, textvariable=self.count_var,
            font=(KFONT, FONT_COUNT, "bold"),
            fg=TEXT_MAIN, bg=CARD_BG,
        ).grid(row=0, column=0, sticky="s")
        tk.Label(
            count_frame, text="건",
            font=(KFONT, FONT_MD),
            fg=TEXT_SUB, bg=CARD_BG,
        ).grid(row=0, column=1, sticky="s", padx=(9, 0), pady=(0, 9))
        self.card_canvas.create_window(
            x0 + card_w // 2, y0 + 132, window=count_frame,
        )

        # 구분선
        self.card_canvas.create_line(
            x0 + 30, y0 + 194, x0 + card_w - 30, y0 + 194,
            fill=CREAM_DARK, width=1,
        )

        # 상태 메시지 + 로딩 도트
        status_frame = tk.Frame(self.card_canvas, width=card_w - 60, height=34, bg=CARD_BG)
        status_frame.grid_propagate(False)
        status_frame.grid_columnconfigure(0, minsize=42)
        status_frame.grid_columnconfigure(1, weight=1)
        status_frame.grid_columnconfigure(2, minsize=42)
        self.status_var = tk.StringVar(value="자동 수락을 시작해주세요")
        tk.Label(
            status_frame, textvariable=self.status_var,
            font=(KFONT, FONT_SM), fg=TEXT_SUB, bg=CARD_BG,
            anchor="center", justify="center",
        ).grid(row=0, column=1, sticky="nsew")
        self.dots_canvas = tk.Canvas(
            status_frame, width=34, height=16,
            bg=CARD_BG, highlightthickness=0, bd=0,
        )
        self.dots_canvas.grid(row=0, column=2, sticky="w", padx=(8, 0), pady=(8, 0))
        self._dot_items = []
        for i in range(3):
            d = self.dots_canvas.create_oval(
                i * 10, 4, i * 10 + 6, 10,
                fill=TEXT_HINT, outline="",
            )
            self._dot_items.append(d)
            self.dots_canvas.itemconfig(d, state="hidden")

        self.card_canvas.create_window(
            x0 + card_w // 2, y0 + 226, window=status_frame,
        )

    def _build_button(self):
        self.btn = GradientButton(
            self, width=320, height=62,
            text="자동 수락 시작 🚀",
            c1=CORAL_LIGHT, c2=CORAL,
            command=self._toggle,
            font=(KFONT, FONT_MD, "bold"),
        )
        self.btn.pack(pady=(4, 4))

    # ─── 애니메이션 ───
    def _animate_dots(self):
        if self._running:
            for i, d in enumerate(self._dot_items):
                self.dots_canvas.itemconfig(
                    d, state="normal",
                    fill=CORAL if i == self._dot_idx else TEXT_HINT,
                )
            self._dot_idx = (self._dot_idx + 1) % 3
        else:
            for d in self._dot_items:
                self.dots_canvas.itemconfig(d, state="hidden")
        self.after(280, self._animate_dots)

    # ─── 컨트롤 ───
    def _toggle(self):
        if not self._running:
            self._start()
        else:
            self._stop()

    def _start(self):
        self._running = True
        self.btn.set_state(MINT_LIGHT, MINT_DARK, text="자동 수락 중지")
        self._set_badge("running", "실행 중")
        self._thread = threading.Thread(
            target=bot_loop,
            args=(
                lambda: self._running,
                self._set_status,
                self._set_count,
            ),
            daemon=True,
        )
        self._thread.start()

    def _stop(self):
        self._running = False
        self.btn.set_state(CORAL_LIGHT, CORAL, text="자동 수락 시작 🚀")
        self._set_badge("waiting", "대기 중")
        self.status_var.set("일시 정지됐어요")

    # ─── 상태 반영 ───
    def _set_badge(self, state, label):
        if state == "running":
            self.card_canvas.itemconfig(self._badge_dot, fill=BADGE_RUN)
            self.card_canvas.itemconfig(self._badge_text, text=label, fill=MINT_DARK)
        elif state == "waiting":
            self.card_canvas.itemconfig(self._badge_dot, fill=BADGE_WAIT)
            self.card_canvas.itemconfig(self._badge_text, text=label, fill=TEXT_SUB)
        elif state == "error":
            self.card_canvas.itemconfig(self._badge_dot, fill=BADGE_ERR)
            self.card_canvas.itemconfig(self._badge_text, text=label, fill=ERR_TEXT)

    def _set_status(self, payload):
        state, msg = payload
        self.after(0, lambda: self._apply_status(state, msg))

    def _apply_status(self, state, msg):
        self.status_var.set(msg)
        if state == "running":
            self._set_badge("running", "실행 중")
        elif state == "waiting":
            self._set_badge("running", "감시 중")
        elif state == "error":
            self._set_badge("error", "오류")

    def _set_count(self, n):
        self._count = n
        self.after(0, lambda: self.count_var.set(str(n)))

    def destroy(self):
        self._running = False
        super().destroy()


if __name__ == "__main__":
    App().mainloop()
