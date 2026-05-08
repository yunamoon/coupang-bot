"""
쿠팡이츠 자동 수락 봇 (배포용 구조)

원리:
  1. "새 주문이 들어왔어요" 팝업을 이미지 매칭으로 감지
  2. 팝업 위치 기준 상대좌표로 +5 / 수락 버튼 클릭
  → 팝업 UI가 모든 PC에서 동일하므로 상대좌표도 동일
  → 템플릿 이미지 1개만 번들하면 어디서든 동작

사용법:
  python3 bot.py setup      ← 최초 1회: 팝업에서 상대좌표 측정
  python3 bot.py              ← 자동 수락 실행
  python3 bot.py test         ← 테스트
"""

import pyautogui
import cv2
import numpy as np
import json
import time
import sys
import os
import platform
import subprocess
from datetime import datetime

# ─── 설정 ───
SCAN_INTERVAL = 0.5
CONFIDENCE = 0.75
PLUS5_REPEAT = 6       # +5 반복 (최대치 넘으면 무시됨)
CLICK_DELAY = 0.25
POST_ACCEPT_DELAY = 3.0
DETECT_DELAY = 0.8     # 팝업 감지 후 클릭 시작 전 대기 시간

import platform

# ─── 경로 설정 ───
def resource_path(relative):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)

if platform.system() == "Darwin":
    POPUP_IMG   = resource_path("templates/popup_mac.png")
    ACCEPT_IMG  = resource_path("templates/accept_mac.png")
    CONFIG_FILE = resource_path("templates/offsets_mac.json")
else:
    POPUP_IMG   = resource_path("templates/popup.png")
    ACCEPT_IMG  = resource_path("templates/accept.png")
    CONFIG_FILE = resource_path("templates/offsets.json")

TEMPLATE_DIR = resource_path("templates")

# 수락 버튼 캡처 영역 (논리좌표 기준, 마우스 위치 중심)
ACCEPT_BTN_W = 130
ACCEPT_BTN_H = 44
ACCEPT_CONFIDENCE = 0.80

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


# ─── 유틸 ───

def get_scale():
    if platform.system() != "Darwin":
        return 1
    try:
        ss = pyautogui.screenshot()
        return ss.size[0] / pyautogui.size()[0]
    except:
        return 2

SCALE = get_scale()

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def grab():
    ss = pyautogui.screenshot()
    return cv2.cvtColor(np.array(ss), cv2.COLOR_RGB2BGR)


def click_at(x, y):
    """
    macOS Tahoe에서는 pyautogui의 합성 클릭이 Tkinter 바인딩에 안 닿는 경우가 있어
    osascript(System Events)로 클릭을 보낸다. 다른 OS는 pyautogui 그대로.
    """
    if platform.system() == "Darwin":
        pyautogui.moveTo(x, y)
        subprocess.run(
            ["osascript", "-e",
             f'tell application "System Events" to click at {{{int(x)}, {int(y)}}}'],
            capture_output=True, timeout=2
        )
    else:
        pyautogui.click(x, y)


# ─── 팝업 감지 ───

def find_popup(screen):
    """'새 주문이 들어왔어요' 템플릿을 화면에서 찾아 중심좌표 반환"""
    if not os.path.exists(POPUP_IMG):
        return None

    tmpl = cv2.imread(POPUP_IMG)
    if tmpl is None:
        return None

    if tmpl.shape[0] > screen.shape[0] or tmpl.shape[1] > screen.shape[1]:
        return None

    res = cv2.matchTemplate(screen, tmpl, cv2.TM_CCOEFF_NORMED)
    _, val, _, loc = cv2.minMaxLoc(res)

    if val >= CONFIDENCE:
        th, tw = tmpl.shape[:2]
        # 논리 좌표로 변환
        cx = int((loc[0] + tw // 2) / SCALE)
        cy = int((loc[1] + th // 2) / SCALE)
        return (cx, cy, val)

    return None


def find_accept_button(screen):
    """수락 버튼 템플릿을 화면에서 찾아 중심좌표 반환.

    팝업 내부 UI가 변해도(경고 메시지 추가 등) 수락 버튼만 추적.
    템플릿이 없거나 매칭 실패 시 None.
    """
    if not os.path.exists(ACCEPT_IMG):
        return None

    tmpl = cv2.imread(ACCEPT_IMG)
    if tmpl is None:
        return None

    if tmpl.shape[0] > screen.shape[0] or tmpl.shape[1] > screen.shape[1]:
        return None

    res = cv2.matchTemplate(screen, tmpl, cv2.TM_CCOEFF_NORMED)
    _, val, _, loc = cv2.minMaxLoc(res)

    if val >= ACCEPT_CONFIDENCE:
        th, tw = tmpl.shape[:2]
        cx = int((loc[0] + tw // 2) / SCALE)
        cy = int((loc[1] + th // 2) / SCALE)
        return (cx, cy, val)

    return None


# ─── 셋업: 상대좌표 측정 ───

def setup():
    """
    팝업이 뜬 상태에서 각 버튼 위치를 기록하고,
    팝업 제목 기준 상대좌표(오프셋)를 저장.
    이 오프셋은 모든 같은 POS에서 동일.
    """
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"), exist_ok=True)

    suffix = "_mac" if platform.system() == "Darwin" else ""
    print()
    print("=" * 50)
    print(f"  셋업 ({'Mac 테스트용' if suffix else 'Windows POS용'})")
    print(f"  Retina: {SCALE}x")
    print("=" * 50)
    print()
    print("  주문 팝업이 뜬 상태에서 진행하세요.")
    print()

    # 1. 팝업 제목 템플릿 캡처
    print("  1/3  '새 주문이 들어왔어요' 텍스트 위에 마우스")
    input("       → Enter ")
    popup_x, popup_y = pyautogui.position()

    ss = grab()
    pw, ph = int(160 * SCALE), int(28 * SCALE)
    px, py = int(popup_x * SCALE), int(popup_y * SCALE)
    h_img, w_img = ss.shape[:2]
    x1 = max(0, px - pw // 2)
    y1 = max(0, py - ph // 2)
    x2 = min(w_img, px + pw // 2)
    y2 = min(h_img, py + ph // 2)
    crop = ss[y1:y2, x1:x2]
    cv2.imwrite(POPUP_IMG, crop)
    print(f"       ✓ popup.png ({crop.shape[1]}x{crop.shape[0]}px)")
    print()

    # 2. +5 버튼 위치
    print("  2/3  '+5' 버튼 위에 마우스")
    input("       → Enter ")
    plus_x, plus_y = pyautogui.position()
    print(f"       ✓ +5 위치: ({plus_x}, {plus_y})")
    print()

    # 3. 수락 버튼 위치 + 이미지 캡처
    print("  3/3  '수락' 버튼 위에 마우스")
    print("       (팁: +5를 최대까지 누른 상태에서 측정하면 더 정확)")
    input("       → Enter ")
    accept_x, accept_y = pyautogui.position()
    print(f"       ✓ 수락 위치: ({accept_x}, {accept_y})")

    # 수락 버튼 이미지도 같이 캡처 (런타임 매칭용 — UI 변동에 강건)
    ss = grab()
    aw, ah = int(ACCEPT_BTN_W * SCALE), int(ACCEPT_BTN_H * SCALE)
    ax_phys, ay_phys = int(accept_x * SCALE), int(accept_y * SCALE)
    h_img, w_img = ss.shape[:2]
    x1 = max(0, ax_phys - aw // 2)
    y1 = max(0, ay_phys - ah // 2)
    x2 = min(w_img, ax_phys + aw // 2)
    y2 = min(h_img, ay_phys + ah // 2)
    accept_crop = ss[y1:y2, x1:x2]
    cv2.imwrite(ACCEPT_IMG, accept_crop)
    print(f"       ✓ accept.png ({accept_crop.shape[1]}x{accept_crop.shape[0]}px)")
    print()

    # 상대좌표 계산 (팝업 제목 중심 기준) — 이미지 매칭 실패 시 fallback
    offsets = {
        "plus5_dx": plus_x - popup_x,
        "plus5_dy": plus_y - popup_y,
        "accept_dx": accept_x - popup_x,
        "accept_dy": accept_y - popup_y,
    }

    with open(CONFIG_FILE, "w") as f:
        json.dump(offsets, f, indent=2)

    print("  상대좌표 (팝업 제목 기준):")
    print(f"    +5:  dx={offsets['plus5_dx']}, dy={offsets['plus5_dy']}")
    print(f"    수락: dx={offsets['accept_dx']}, dy={offsets['accept_dy']}")
    print()
    print("=" * 50)
    print("  셋업 완료!")
    print()
    print("  ★ 이 offsets.json + popup.png + accept.png를 프로그램에 번들하면")
    print("    다른 PC에서도 셋업 없이 바로 실행 가능!")
    print()
    print("  python3 bot.py       ← 실행")
    print("  python3 bot.py test  ← 테스트")
    print("=" * 50)


# ─── 설정 로드 ───

def load_offsets():
    if not os.path.exists(CONFIG_FILE):
        log("offsets.json 없음 → python3 bot.py setup 먼저 실행")
        sys.exit(1)
    if not os.path.exists(POPUP_IMG):
        log("popup.png 없음 → python3 bot.py setup 먼저 실행")
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        return json.load(f)


# ─── 자동 수락 ───

def try_accept(offsets):
    screen = grab()

    # 1) 팝업 감지
    popup = find_popup(screen)
    if not popup:
        return False

    px, py = popup[0], popup[1]
    log(f"팝업 감지! 위치=({px},{py}) 정확도={popup[2]:.2f}")

    # 팝업 완전히 렌더링될 때까지 대기 (사용자 개입 여지도 줌)
    time.sleep(DETECT_DELAY)

    # 팝업 자체를 한 번 클릭해 POS 창에 포커스를 줌
    if platform.system() == "Darwin":
        click_at(px, py)
        time.sleep(0.2)

    # 2) +5 반복 클릭 (팝업 위치 + 오프셋)
    tx = px + offsets["plus5_dx"]
    ty = py + offsets["plus5_dy"]
    log(f"  → +5 클릭 ({tx},{ty}) ×{PLUS5_REPEAT}")
    for i in range(PLUS5_REPEAT):
        click_at(tx, ty)
        time.sleep(CLICK_DELAY)

    time.sleep(0.3)

    # 3) 수락 클릭 — 이미지 매칭 우선 (UI 변동에 강건), 실패 시 오프셋 fallback
    accept_pos = find_accept_button(grab())
    if accept_pos:
        ax, ay = accept_pos[0], accept_pos[1]
        log(f"  → 수락 [이미지 매칭] ({ax},{ay}) 정확도={accept_pos[2]:.2f}")
    else:
        ax = px + offsets["accept_dx"]
        ay = py + offsets["accept_dy"]
        log(f"  → 수락 [오프셋 fallback] ({ax},{ay})")
    click_at(ax, ay)

    return True


# ─── 실행 ───

def run():
    offsets = load_offsets()

    log("=" * 45)
    log("쿠팡이츠 자동 수락 봇")
    log(f"  +5 오프셋: ({offsets['plus5_dx']}, {offsets['plus5_dy']})")
    log(f"  수락 오프셋: ({offsets['accept_dx']}, {offsets['accept_dy']})")
    log("=" * 45)
    log("대기 중... (Ctrl+C 종료)")
    log("")

    count = 0
    try:
        while True:
            if try_accept(offsets):
                count += 1
                log(f"  (누적: {count}건)")
                time.sleep(POST_ACCEPT_DELAY)
            time.sleep(SCAN_INTERVAL)
    except KeyboardInterrupt:
        log(f"\n종료. 총 {count}건.")


# ─── 테스트 ───

def test():
    offsets = load_offsets()
    log("테스트 — 팝업이 보이는 상태에서")

    screen = grab()
    popup = find_popup(screen)

    if popup:
        px, py = popup[0], popup[1]
        log(f"  팝업: ({px},{py}) 정확도={popup[2]:.2f}")
        log(f"  +5 클릭 예정: ({px + offsets['plus5_dx']}, {py + offsets['plus5_dy']})")
        log(f"  수락 클릭 예정: ({px + offsets['accept_dx']}, {py + offsets['accept_dy']})")
    else:
        log("  팝업: 화면에 없음")


# ─── 메인 ───

if __name__ == "__main__":
    os.makedirs(TEMPLATE_DIR, exist_ok=True)

    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "setup":
            setup()
        elif cmd == "test":
            test()
        else:
            print("사용법: python3 bot.py [setup|test]")
    else:
        run()
