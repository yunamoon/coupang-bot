"""
Windows POS UI Automation inspector.

Run this on the friend's Windows POS machine before implementing the cooking
delay feature. It checks whether the Coupang Eats POS window and target buttons
are visible through UI Automation.

Usage:
  py inspect_pos_ui.py
  py inspect_pos_ui.py --keyword "조리 지연" --keyword "시간 추가"
  py inspect_pos_ui.py --dump-depth 4 --all-windows

This script is intentionally standalone and does not affect the running bot.
It requires pywinauto only when you run this diagnostic:
  py -m pip install pywinauto
"""

from __future__ import annotations

import argparse
import platform
import sys
from dataclasses import dataclass


DEFAULT_KEYWORDS = [
    "쿠팡",
    "Coupang",
    "POS",
    "조리",
    "조리 지연",
    "시간",
    "시간 추가",
    "추가",
]


@dataclass
class ElementInfo:
    depth: int
    control_type: str
    name: str
    automation_id: str
    class_name: str
    rect: object
    enabled: object
    visible: object
    invoke_supported: object
    legacy_action: str
    clickable_methods: str


def _require_windows():
    if platform.system() != "Windows":
        print(f"[ERR] This diagnostic is Windows-only. Current OS: {platform.system()}")
        sys.exit(1)


def _load_pywinauto():
    try:
        from pywinauto import Desktop
        from pywinauto.findwindows import ElementNotFoundError
    except ImportError:
        print("[ERR] pywinauto is not installed.")
        print()
        print("Install it on the POS machine, then rerun:")
        print("  py -m pip install pywinauto")
        sys.exit(1)
    return Desktop, ElementNotFoundError


def _safe_text(value):
    if value is None:
        return ""
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def _element_info(wrapper, depth):
    info = wrapper.element_info
    return ElementInfo(
        depth=depth,
        control_type=_safe_text(info.control_type),
        name=_safe_text(info.name),
        automation_id=_safe_text(info.automation_id),
        class_name=_safe_text(info.class_name),
        rect=info.rectangle,
        enabled=_safe_call(wrapper.is_enabled),
        visible=_safe_call(wrapper.is_visible),
        invoke_supported=_supports_invoke(wrapper),
        legacy_action=_legacy_default_action(wrapper),
        clickable_methods=_clickable_methods(wrapper),
    )


def _safe_call(fn):
    try:
        return fn()
    except Exception as exc:
        return f"<err: {exc}>"


def _supports_invoke(wrapper):
    """Return whether UIA InvokePattern appears usable without moving the mouse."""
    try:
        iface = wrapper.iface_invoke
        return iface is not None
    except Exception:
        pass

    try:
        wrapper.get_invoke_pattern()
        return True
    except Exception:
        return False


def _legacy_default_action(wrapper):
    """Best-effort LegacyIAccessible default action, often 'Press' for buttons."""
    try:
        iface = wrapper.iface_legacy_iaccessible
    except Exception:
        return ""

    if iface is None:
        return ""

    candidates = [
        "CurrentDefaultAction",
        "DefaultAction",
        "current_default_action",
        "default_action",
    ]
    for attr in candidates:
        try:
            value = getattr(iface, attr)
            if callable(value):
                value = value()
            text = _safe_text(value)
            if text:
                return text
        except Exception:
            continue
    return "<legacy present>"


def _clickable_methods(wrapper):
    methods = []
    for name in ("invoke", "click", "click_input"):
        if callable(getattr(wrapper, name, None)):
            methods.append(name)
    return ",".join(methods)


def _line(info: ElementInfo):
    indent = "  " * info.depth
    parts = [
        f"{indent}- {info.control_type or '?'}",
        f"name={info.name!r}",
    ]
    if info.automation_id:
        parts.append(f"auto_id={info.automation_id!r}")
    if info.class_name:
        parts.append(f"class={info.class_name!r}")
    parts.append(f"rect={info.rect}")
    parts.append(f"enabled={info.enabled}")
    parts.append(f"visible={info.visible}")
    parts.append(f"invoke={info.invoke_supported}")
    if info.legacy_action:
        parts.append(f"legacy_action={info.legacy_action!r}")
    if info.clickable_methods:
        parts.append(f"methods={info.clickable_methods}")
    return " | ".join(parts)


def _matches_keywords(info: ElementInfo, keywords):
    haystack = " ".join([
        info.name,
        info.automation_id,
        info.class_name,
        info.control_type,
    ]).lower()
    return [kw for kw in keywords if kw.lower() in haystack]


def _iter_children(wrapper):
    try:
        return wrapper.children()
    except Exception:
        return []


def _dump_tree(wrapper, keywords, max_depth, current_depth=0, matches=None):
    if matches is None:
        matches = []

    info = _element_info(wrapper, current_depth)
    found = _matches_keywords(info, keywords)
    marker = "  <<< MATCH: " + ", ".join(found) if found else ""
    print(_line(info) + marker)
    if found:
        matches.append(info)

    if current_depth >= max_depth:
        return matches

    for child in _iter_children(wrapper):
        _dump_tree(child, keywords, max_depth, current_depth + 1, matches)
    return matches


def _window_candidates(desktop, keywords, all_windows):
    windows = []
    for win in desktop.windows():
        info = _element_info(win, 0)
        if not info.name and not info.class_name:
            continue
        found = _matches_keywords(info, keywords)
        if all_windows or found:
            windows.append((win, info, found))
    return windows


def _try_focus_window(win):
    print()
    print("[FOCUS TEST]")
    try:
        if hasattr(win, "restore"):
            win.restore()
        win.set_focus()
        print("[OK] restore/set_focus completed.")
        return True
    except Exception as exc:
        print(f"[WARN] restore/set_focus failed: {exc}")
        print("       This may need foreground-window workaround in implementation.")
        return False


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Inspect Windows UI Automation tree for Coupang Eats POS."
    )
    parser.add_argument(
        "--keyword",
        action="append",
        dest="keywords",
        help="Keyword to search in window/control name, class, automation id.",
    )
    parser.add_argument(
        "--dump-depth",
        type=int,
        default=3,
        help="How deep to dump child controls for each candidate window.",
    )
    parser.add_argument(
        "--all-windows",
        action="store_true",
        help="Dump every top-level window instead of keyword-matched candidates.",
    )
    parser.add_argument(
        "--no-focus-test",
        action="store_true",
        help="Skip restore/set_focus test for matched POS candidate windows.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    _require_windows()
    Desktop, _ = _load_pywinauto()

    keywords = args.keywords or DEFAULT_KEYWORDS
    desktop = Desktop(backend="uia")

    print("=" * 72)
    print("  POS UI Automation Inspector")
    print("=" * 72)
    print(f"Keywords: {', '.join(keywords)}")
    print(f"Dump depth: {args.dump_depth}")
    print()

    candidates = _window_candidates(desktop, keywords, args.all_windows)
    if not candidates:
        print("[RESULT] No top-level windows matched the keywords.")
        print("Try:")
        print("  py inspect_pos_ui.py --all-windows --dump-depth 1")
        return 2

    total_matches = []
    print(f"[WINDOWS] {len(candidates)} candidate(s)")
    for idx, (win, info, found) in enumerate(candidates, start=1):
        print()
        print("-" * 72)
        print(f"[WINDOW {idx}] {_line(info)}")
        if found:
            print(f"Top-level keyword match: {', '.join(found)}")

        if not args.no_focus_test and found:
            _try_focus_window(win)

        print()
        print("[UIA TREE]")
        matches = _dump_tree(win, keywords, max(0, args.dump_depth))
        total_matches.extend(matches)

    print()
    print("=" * 72)
    print("[SUMMARY]")
    print(f"Control keyword matches: {len(total_matches)}")
    for info in total_matches[:30]:
        print(_line(info))
    if len(total_matches) > 30:
        print(f"... {len(total_matches) - 30} more")

    print()
    target_matches = [
        info for info in total_matches
        if "조리" in info.name or "시간" in info.name
    ]
    invoke_matches = [info for info in target_matches if info.invoke_supported is True]
    if invoke_matches:
        print("[NEXT] UIA InvokePattern is available on target-looking controls.")
        print("       Mouse-free automation may be possible. Capture this output.")
    elif target_matches:
        print("[NEXT] Target Korean labels were found, but InvokePattern was not.")
        print("       click()/click_input() tradeoff or image fallback needs validation.")
    else:
        print("[NEXT] Target Korean labels were not found in UIA names.")
        print("       Image matching fallback may be needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
