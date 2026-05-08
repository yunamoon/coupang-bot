"""
오류 반복 알림 — GitHub Issue 자동 발행.

같은 에러가 window_sec 안에 threshold번 이상 발생하면 GitHub에 이슈를 만들고,
이미 같은 제목의 열린 이슈가 있으면 댓글로 추가. cooldown_sec 동안은 같은 에러
재알림 안 함 (스팸 방지).

설정: alert_config.json (gitignored)
{
  "github_token": "github_pat_...",
  "repo": "yunamoon/coupang-bot",
  "threshold": 3,
  "window_sec": 300,
  "cooldown_sec": 1800
}

설정이 없으면 자동으로 비활성화 — 봇 동작엔 영향 없음.
"""

import json
import os
import threading
import time
import urllib.request
from datetime import datetime

CONFIG_FILE = "alert_config.json"


class ErrorTracker:
    def __init__(self, config):
        self.threshold = config.get("threshold", 3)
        self.window_sec = config.get("window_sec", 300)
        self.cooldown_sec = config.get("cooldown_sec", 1800)
        self.token = config.get("github_token")
        self.repo = config.get("repo")
        self.enabled = bool(self.token and self.repo)
        self.events = {}       # error_msg -> [timestamp, ...]
        self.alerted_at = {}   # error_msg -> last_alert_time
        self.lock = threading.Lock()

    def record(self, error_msg):
        if not self.enabled:
            return

        with self.lock:
            now = time.time()
            cutoff = now - self.window_sec

            recent = self.events.setdefault(error_msg, [])
            recent.append(now)
            recent[:] = [t for t in recent if t > cutoff]

            if len(recent) < self.threshold:
                return

            last_alert = self.alerted_at.get(error_msg, 0)
            if now - last_alert < self.cooldown_sec:
                return

            self.alerted_at[error_msg] = now
            count = len(recent)

        # 네트워크 호출은 lock 밖에서 비동기로
        threading.Thread(
            target=self._post_issue,
            args=(error_msg, count),
            daemon=True,
        ).start()

    def _post_issue(self, error_msg, count):
        try:
            existing = self._find_open_issue(error_msg)
            if existing:
                self._add_comment(existing, error_msg, count)
            else:
                self._create_issue(error_msg, count)
        except Exception as e:
            # 알림 실패가 봇 동작에 영향 주지 않게
            print(f"[alert] GitHub 알림 실패: {e}")

    def _api(self, method, path, body=None):
        url = f"https://api.github.com{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = resp.read()
            return json.loads(payload) if payload else None

    def _find_open_issue(self, error_msg):
        title = self._make_title(error_msg)
        path = f"/repos/{self.repo}/issues?labels=bot-alert&state=open&per_page=50"
        issues = self._api("GET", path)
        for issue in issues or []:
            if issue.get("title") == title:
                return issue["number"]
        return None

    def _create_issue(self, error_msg, count):
        title = self._make_title(error_msg)
        body = (
            f"**최초 알림:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"**최근 {self.window_sec // 60}분 내 발생:** {count}회\n\n"
            f"**에러 메시지:**\n```\n{error_msg}\n```\n\n"
            f"_같은 에러가 다시 반복되면 이 이슈에 댓글이 추가됩니다._\n"
            f"_복구되면 이 이슈를 닫아주세요._"
        )
        self._api(
            "POST",
            f"/repos/{self.repo}/issues",
            {"title": title, "body": body, "labels": ["bot-alert"]},
        )

    def _add_comment(self, issue_number, error_msg, count):
        body = (
            f"**재발생:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"**최근 {self.window_sec // 60}분 내:** {count}회"
        )
        self._api(
            "POST",
            f"/repos/{self.repo}/issues/{issue_number}/comments",
            {"body": body},
        )

    def _make_title(self, error_msg):
        snippet = error_msg.replace("\n", " ").strip()
        if len(snippet) > 80:
            snippet = snippet[:77] + "..."
        return f"[봇 알림] {snippet}"


def load_tracker():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, CONFIG_FILE)
    if not os.path.exists(path):
        return ErrorTracker({})
    try:
        with open(path, encoding="utf-8") as f:
            return ErrorTracker(json.load(f))
    except Exception as e:
        print(f"[alert] {CONFIG_FILE} 로드 실패: {e}")
        return ErrorTracker({})
