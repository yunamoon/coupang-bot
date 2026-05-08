"""
바탕화면에 봇 바로가기를 자동 생성.

사용법 (POS에서 git clone 후 1회만):
  py install_shortcut.py
"""

import os
import platform
import subprocess
import sys

SHORTCUT_NAME = "쿠팡 이츠 자동수락- 탄이봇"
TARGET_FILE = "start_bot_silent.vbs"
ICON_FILE = "tan.ico"
RUN_AS_ADMIN = True  # 관리자 권한으로 실행. False면 UAC 프롬프트 안 뜸.


def install_windows():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(project_dir, TARGET_FILE)
    icon = os.path.join(project_dir, ICON_FILE)

    if not os.path.exists(target):
        print(f"[ERR] {TARGET_FILE} 을 찾을 수 없습니다: {project_dir}")
        sys.exit(1)

    has_icon = os.path.exists(icon)
    if not has_icon:
        print(f"[WARN] {ICON_FILE} 이 없어 기본 아이콘으로 생성됩니다.")

    # PowerShell 단일 인용부 내에서 ' 는 '' 로 이스케이프
    target_q = target.replace("'", "''")
    project_q = project_dir.replace("'", "''")
    name_q = SHORTCUT_NAME.replace("'", "''")
    icon_q = icon.replace("'", "''")

    # 관리자 권한 비트(.lnk 바이너리 0x15 바이트의 0x20 비트) 토글
    admin_block = ""
    if RUN_AS_ADMIN:
        admin_block = (
            "$bytes = [IO.File]::ReadAllBytes($path);"
            "$bytes[0x15] = $bytes[0x15] -bor 0x20;"
            "[IO.File]::WriteAllBytes($path, $bytes);"
        )

    icon_line = f"$lnk.IconLocation = '{icon_q}';" if has_icon else ""

    ps_script = (
        "$ws = New-Object -ComObject WScript.Shell;"
        "$desktop = [Environment]::GetFolderPath('Desktop');"
        f"$path = Join-Path $desktop '{name_q}.lnk';"
        "$lnk = $ws.CreateShortcut($path);"
        f"$lnk.TargetPath = '{target_q}';"
        f"$lnk.WorkingDirectory = '{project_q}';"
        f"{icon_line}"
        "$lnk.Save();"
        f"{admin_block}"
    )

    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script]
    )

    if result.returncode != 0:
        print("[ERR] 바로가기 생성 실패")
        sys.exit(1)

    print(f"[OK] 바탕화면에 '{SHORTCUT_NAME}.lnk' 생성 완료")
    if RUN_AS_ADMIN:
        print("     (관리자 권한 실행 — 더블클릭 시 UAC 프롬프트가 뜹니다)")
    print()
    print("이제 바탕화면 바로가기를 더블클릭하면 봇이 실행됩니다.")


def main():
    if platform.system() != "Windows":
        print(f"이 스크립트는 Windows 전용입니다. (현재 OS: {platform.system()})")
        sys.exit(1)
    install_windows()


if __name__ == "__main__":
    main()
