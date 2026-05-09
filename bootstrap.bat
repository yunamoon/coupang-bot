@echo off
setlocal
REM cmd 기본 코드페이지(cp949)와 파일 인코딩(UTF-8)을 맞춰 한글 깨짐 방지
chcp 65001 >nul

echo ===========================================
echo   쿠팡 이츠 자동수락- 탄이봇 셋업
echo ===========================================
echo.

REM 이미 코드와 같은 폴더에서 실행된 경우 (예: 사용자가 git clone 받은 폴더에서 직접 실행).
REM 별도 clone 없이 이 폴더 그대로 셋업.
if exist "%~dp0bot.py" (
    echo [INFO] 같은 폴더에서 코드 발견. clone 단계 건너뜀.
    cd /d "%~dp0"
    goto deps
)

REM --- Step 1: Git ---
where git >nul 2>&1
if errorlevel 1 (
    echo [1/5] Git 자동 설치 중... ^(시간이 좀 걸려요^)
    winget install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo.
        echo [실패] Git 자동 설치가 안 됐어요.
        echo        아래 링크에서 직접 설치 후 다시 실행해주세요:
        echo        https://git-scm.com/download/win
        echo.
        pause
        exit /b 1
    )
    echo.
    echo [완료] Git 설치 끝. 이 창을 닫고 bootstrap.bat을 다시 더블클릭해주세요.
    pause
    exit /b 0
)
echo [1/5] Git: OK

REM --- Step 2: Python ---
py -3 --version >nul 2>&1
if errorlevel 1 (
    echo [2/5] Python 자동 설치 중... ^(시간이 좀 걸려요^)
    winget install --id Python.Python.3.11 -e --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo.
        echo [실패] Python 자동 설치가 안 됐어요.
        echo        아래 링크에서 직접 설치 후 다시 실행해주세요:
        echo        https://www.python.org/downloads/
        echo        ^(설치 시 "Add python.exe to PATH" 체크 필수^)
        echo.
        pause
        exit /b 1
    )
    echo.
    echo [완료] Python 설치 끝. 이 창을 닫고 bootstrap.bat을 다시 더블클릭해주세요.
    pause
    exit /b 0
)
echo [2/5] Python: OK

REM --- Step 3: Clone ---
if not exist "coupang-bot\bot.py" (
    echo [3/5] 코드 다운로드 중...
    git clone https://github.com/yunamoon/coupang-bot.git coupang-bot
    if errorlevel 1 (
        echo [실패] 코드 다운로드 실패. 인터넷 연결 확인해주세요.
        pause
        exit /b 1
    )
) else (
    echo [3/5] 코드 폴더 이미 있음 - 최신화 시도
    pushd coupang-bot
    git fetch origin
    git reset --hard origin/main
    popd
)
echo [3/5] 코드: OK

cd coupang-bot

:deps
REM --- Step 4: 패키지 ---
echo [4/5] 파이썬 패키지 설치 중... ^(처음엔 1~2분 걸려요^)
py -m pip install -r requirements.txt
if errorlevel 1 (
    echo [실패] 파이썬 패키지 설치 실패. 인터넷 연결 확인해주세요.
    pause
    exit /b 1
)
echo [4/5] 패키지: OK

REM --- Step 5: 바로가기 ---
echo [5/5] 바탕화면 바로가기 생성 중...
py install_shortcut.py

echo.
echo ===========================================
echo   셋업 완료!
echo   바탕화면의 "쿠팡 이츠 자동수락- 탄이봇" 으로 실행하세요.
echo ===========================================
pause
