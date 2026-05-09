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


# 로컬 오버라이드(_local) — GUI 셋업으로 생성. 있으면 git 번들보다 우선.
def _local_path(p):
    base, ext = os.path.splitext(p)
    return f"{base}_local{ext}"

def popup_img_path():
    local = _local_path(POPUP_IMG)
    return local if os.path.exists(local) else POPUP_IMG

def accept_img_path():
    local = _local_path(ACCEPT_IMG)
    return local if os.path.exists(local) else ACCEPT_IMG

def config_file_path():
    local = _local_path(CONFIG_FILE)
    return local if os.path.exists(local) else CONFIG_FILE

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
    클릭한 뒤 사용자가 마우스 쓰던 위치로 즉시 복귀.
    봇이 클릭 좌표에 커서를 죽치게 두면 사용자 작업 흐름을 빼앗으므로,
    매 클릭 직전에 현재 커서 위치를 캡처해 클릭 직후 그 자리로 워프.

    매번 캡처하는 이유: 사용자가 마우스를 움직이는 중에도 "방금 사용자가 둔 위치"로
    복귀하기 위함. 시퀀스 시작점에 고정하면 사용자 움직임을 덮어써 버림.

    macOS Tahoe에서는 pyautogui의 합성 클릭이 Tkinter 바인딩에 안 닿는 경우가 있어
    osascript(System Events)로 클릭을 보낸다. 다른 OS는 pyautogui 그대로.
    """
    try:
        saved = pyautogui.position()
    except Exception:
        saved = None

    if platform.system() == "Darwin":
        pyautogui.moveTo(x, y)
        subprocess.run(
            ["osascript", "-e",
             f'tell application "System Events" to click at {{{int(x)}, {int(y)}}}'],
            capture_output=True, timeout=2
        )
    else:
        pyautogui.click(x, y)

    if saved is not None:
        try:
            pyautogui.moveTo(saved[0], saved[1])
        except Exception:
            pass


# ─── 팝업 감지 ───

def find_popup(screen):
    """'새 주문이 들어왔어요' 템플릿을 화면에서 찾아 중심좌표 반환"""
    img_path = popup_img_path()
    if not os.path.exists(img_path):
        return None

    tmpl = cv2.imread(img_path)
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
    img_path = accept_img_path()
    if not os.path.exists(img_path):
        return None

    tmpl = cv2.imread(img_path)
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
    cfg = config_file_path()
    if not os.path.exists(cfg):
        log("offsets.json 없음 → python3 bot.py setup 먼저 실행")
        sys.exit(1)
    if not os.path.exists(popup_img_path()):
        log("popup.png 없음 → python3 bot.py setup 먼저 실행")
        sys.exit(1)
    with open(cfg) as f:
        return json.load(f)


# ─── GUI 셋업용 헬퍼 (친구가 직접 재캘리브레이션할 때) ───
# CLI setup()은 git 커밋용 기본값 생성, 이 함수들은 _local 파일로 저장.

def capture_popup_at(mouse_x, mouse_y):
    """주어진 마우스 위치 기준으로 팝업 제목 템플릿을 _local 경로에 저장."""
    ss = grab()
    pw, ph = int(160 * SCALE), int(28 * SCALE)
    px, py = int(mouse_x * SCALE), int(mouse_y * SCALE)
    h_img, w_img = ss.shape[:2]
    x1 = max(0, px - pw // 2)
    y1 = max(0, py - ph // 2)
    x2 = min(w_img, px + pw // 2)
    y2 = min(h_img, py + ph // 2)
    crop = ss[y1:y2, x1:x2]
    out = _local_path(POPUP_IMG)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cv2.imwrite(out, crop)
    return out


def capture_accept_at(mouse_x, mouse_y):
    ss = grab()
    aw, ah = int(ACCEPT_BTN_W * SCALE), int(ACCEPT_BTN_H * SCALE)
    ax, ay = int(mouse_x * SCALE), int(mouse_y * SCALE)
    h_img, w_img = ss.shape[:2]
    x1 = max(0, ax - aw // 2)
    y1 = max(0, ay - ah // 2)
    x2 = min(w_img, ax + aw // 2)
    y2 = min(h_img, ay + ah // 2)
    crop = ss[y1:y2, x1:x2]
    out = _local_path(ACCEPT_IMG)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cv2.imwrite(out, crop)
    return out


def save_offsets_local(popup_xy, plus5_xy, accept_xy):
    """팝업 제목 기준 상대좌표를 _local json에 저장."""
    offsets = {
        "plus5_dx": plus5_xy[0] - popup_xy[0],
        "plus5_dy": plus5_xy[1] - popup_xy[1],
        "accept_dx": accept_xy[0] - popup_xy[0],
        "accept_dy": accept_xy[1] - popup_xy[1],
    }
    out = _local_path(CONFIG_FILE)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(offsets, f, indent=2)
    return out, offsets


# ─── 셋업 검증 (친구 마법사 가드레일) ───
# 잘못된 캡처(같은 위치 3번 클릭, 배경 캡처, 비현실적 거리)를 잡아 봇 망가짐 방지.

def _distance(p1, p2):
    return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5


def _image_detail_score(img_path):
    """grayscale 표준편차. 단색 배경 ~0, 텍스트/UI 30+."""
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return -1
    return float(img.std())


def validate_setup(popup_xy, plus5_xy, accept_xy):
    """캡처된 좌표·이미지를 검증해 경고 메시지 리스트 반환 (정상이면 [])."""
    warnings = []

    pp  = _distance(popup_xy, plus5_xy)
    pa  = _distance(popup_xy, accept_xy)
    p5a = _distance(plus5_xy, accept_xy)
    max_d = max(pp, pa, p5a)

    # 세 점이 한 곳에 모여있음 — 단계마다 마우스 안 움직임 의심.
    # 40px: 카운트다운 동안 손 흔들림(~5px) + 의도적 다른 버튼 거리(>50px) 사이.
    if max_d < 40:
        warnings.append("세 위치가 거의 같은 점이에요. 단계마다 마우스를 옮겨서 다른 위치를 가리켰는지 확인해주세요.")
    elif p5a < 25:
        # 위 케이스 아니면서 +5와 수락만 가까운 경우 (실수로 같은 버튼 두 번 캡처)
        warnings.append("+5 버튼과 수락 버튼이 거의 같은 위치예요. 서로 다른 버튼이 맞는지 확인해주세요.")

    # 비현실적 거리 (다른 화면/창의 버튼을 캡처한 의심)
    if pp > 600:
        warnings.append(
            f"+5 버튼이 팝업에서 너무 멀어요 ({int(pp)}px). 같은 팝업 안의 버튼인지 확인해주세요."
        )
    if pa > 600:
        warnings.append(
            f"수락 버튼이 팝업에서 너무 멀어요 ({int(pa)}px). 같은 팝업 안의 버튼인지 확인해주세요."
        )

    # 이미지가 단조로움 (배경 캡처 의심)
    popup_local = _local_path(POPUP_IMG)
    if os.path.exists(popup_local):
        s = _image_detail_score(popup_local)
        if 0 <= s < 12:
            warnings.append(
                "팝업 캡처가 단조로워요. \"새 주문이 들어왔어요\" 텍스트 위에 정확히 마우스를 올렸는지 확인해주세요."
            )

    accept_local = _local_path(ACCEPT_IMG)
    if os.path.exists(accept_local):
        s = _image_detail_score(accept_local)
        if 0 <= s < 12:
            warnings.append(
                "수락 버튼 캡처가 단조로워요. \"수락\" 버튼 위에 정확히 마우스를 올렸는지 확인해주세요."
            )

    return warnings


def cleanup_local_setup():
    """_local 파일 모두 삭제 — 잘못된 셋업 초기화용."""
    for p in (_local_path(POPUP_IMG), _local_path(ACCEPT_IMG), _local_path(CONFIG_FILE)):
        try:
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass


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
