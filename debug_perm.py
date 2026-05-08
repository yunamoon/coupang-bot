"""
권한 진단 (개선판).

Terminal/iTerm/VS Code 등 어느 앱이 Python을 띄웠는지 확인하고,
실제로 그 앱이 Accessibility 권한을 갖고 있는지 직접 검사한다.
"""

import os
import subprocess


def parent_app():
    """이 Python을 띄운 앱(터미널) 이름을 추적 — 전체 경로 출력."""
    try:
        ppid = os.getppid()
        chain = []
        for _ in range(8):
            # -ww : 너비 잘림 방지 (전체 경로)
            r = subprocess.run(
                ["ps", "-ww", "-o", "comm=", "-p", str(ppid)],
                capture_output=True, text=True, timeout=2,
            )
            comm = r.stdout.strip()
            if not comm:
                break

            # 다음 ppid도 따로 조회
            r2 = subprocess.run(
                ["ps", "-ww", "-o", "ppid=", "-p", str(ppid)],
                capture_output=True, text=True, timeout=2,
            )
            try:
                ppid = int(r2.stdout.strip())
            except ValueError:
                ppid = 0

            chain.append(comm)
            if ppid <= 1:
                break
        return chain
    except Exception as e:
        return [f"<오류: {e}>"]


def check_accessibility():
    """
    AXIsProcessTrustedWithOptions를 ApplicationServices에서 직접 import.
    (Quartz에는 이 심볼이 노출 안 돼 있다 — 그게 직전 실행에서 실패한 이유)
    """
    try:
        from ApplicationServices import (
            AXIsProcessTrustedWithOptions,
            kAXTrustedCheckOptionPrompt,
        )
        # prompt=False: 권한 없을 때 시스템 다이얼로그 띄우지 않음
        opts = {kAXTrustedCheckOptionPrompt: False}
        return bool(AXIsProcessTrustedWithOptions(opts))
    except ImportError:
        try:
            from ApplicationServices import AXIsProcessTrusted
            return bool(AXIsProcessTrusted())
        except Exception as e:
            return f"<체크 실패: {e}>"
    except Exception as e:
        return f"<체크 실패: {e}>"


def cgevent_smoke_test():
    """
    CGEventPost가 실제로 작동하는지 안전하게 시험:
    화면 (0,0) 위치로 가짜 마우스 move 이벤트만 보낸다 (클릭 X).
    권한 없으면 silent fail.
    """
    try:
        import Quartz
        evt = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventMouseMoved, (0.0, 0.0),
            Quartz.kCGMouseButtonLeft,
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, evt)
        return "이벤트 post는 호출됨 (실제 적용은 권한에 따름)"
    except Exception as e:
        return f"<예외: {e}>"


def main():
    print("=" * 60)
    print("  권한 진단 v2")
    print("=" * 60)

    chain = parent_app()
    print()
    print("  Python 프로세스 부모 체인:")
    for i, c in enumerate(chain):
        print(f"    {'  ' * i}└ {c}")

    print()
    trusted = check_accessibility()
    print(f"  ▶ AXIsProcessTrusted: {trusted}")

    print()
    print(f"  ▶ CGEvent post 시험: {cgevent_smoke_test()}")

    print()
    print("=" * 60)
    print()

    if trusted is False:
        print("  진단: ❌ Accessibility 권한 없음")
        print()
        print("  부모 체인의 'login' 위 GUI 앱이 권한 받아야 합니다.")
        print("  zsh ← login ← ??? 였다면 그 ??? 앱이 대상.")
        print("  (보통 /System/Applications/Utilities/Terminal.app)")
        print()
        print("  해결:")
        print("   1) System Settings → Privacy & Security → Accessibility")
        print("   2) 자물쇠 풀고 Terminal 토글 OFF → 다시 ON (재적용)")
        print("   3) 메뉴 → Terminal → Quit Terminal (Cmd+Q)")
        print("   4) Terminal 다시 열고 이 스크립트 재실행해 True 확인")
    elif trusted is True:
        print("  진단: ✓ 권한 보유 — 그럼에도 클릭이 안 닿는다면:")
        print("   - Input Monitoring 권한도 필요할 수 있음 (Tahoe)")
        print("   - 봇 GUI 윈도우가 mock 팝업을 가리고 있음")
        print("   - 클릭 좌표가 다른 윈도우 위에 있음")
    else:
        print(f"  진단: 체크 함수 자체가 실패 ({trusted})")
        print("   → pyobjc-framework-ApplicationServices 미설치 가능")
        print("   → pip install pyobjc-framework-Cocoa 시도")


if __name__ == "__main__":
    main()
