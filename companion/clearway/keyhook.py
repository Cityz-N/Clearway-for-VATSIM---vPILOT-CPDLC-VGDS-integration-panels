"""Keyboard capture for the MSFS panel's text fields.

MSFS hands key presses to an in-game panel only *after* its own key bindings, and programs such as
ChasePlane read the keyboard on their own, so typing in the panel also moved the camera or fired
sim commands. While a panel text field has the cursor (the panel asks for it), Clearway installs a
low-level Windows keyboard hook, holds back typing keys from every program (MSFS, ChasePlane, ...)
and passes them to the panel, which types them into the field itself. Controllers are not keyboard
input and keep working.

Safety:
- only while the foreground window is MSFS; other windows always get their keys
- modifiers, function keys, Windows-key and Alt+Tab style combos always pass
- the panel must keep polling: if it stops for KEEPALIVE_S, the keyboard is handed back
- Esc hands the keyboard back at once
- the hook is installed per capture and removed afterwards (no permanent hook)
"""
from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time

log = logging.getLogger("clearway.keys")

KEEPALIVE_S = 4.0
LONGPOLL_S = 1.5
MAX_EVENTS = 500

# programs whose window counts as "the sim" (CLEARWAY_KEY_TARGETS overrides, for testing)
DEFAULT_TARGETS = ("flightsimulator.exe", "flightsimulator2024.exe")

# virtual-key codes
VK_BACK, VK_TAB, VK_RETURN, VK_ESCAPE = 0x08, 0x09, 0x0D, 0x1B
VK_SHIFT, VK_CONTROL, VK_MENU, VK_CAPITAL = 0x10, 0x11, 0x12, 0x14
VK_PRIOR, VK_NEXT, VK_END, VK_HOME = 0x21, 0x22, 0x23, 0x24
VK_LEFT, VK_UP, VK_RIGHT, VK_DOWN = 0x25, 0x26, 0x27, 0x28
VK_INSERT, VK_DELETE = 0x2D, 0x2E
VK_LWIN, VK_RWIN = 0x5B, 0x5C
VK_A, VK_V = 0x41, 0x56

ALWAYS_PASS = set(range(0x70, 0x88))                    # F1..F24
ALWAYS_PASS |= set(range(0xA0, 0xA6))                   # left/right Shift, Ctrl, Alt
ALWAYS_PASS |= set(range(0xA6, 0xB8))                   # browser, volume, media keys
ALWAYS_PASS |= {VK_SHIFT, VK_CONTROL, VK_MENU, VK_CAPITAL, VK_LWIN, VK_RWIN,
                0x5D, 0x2C, 0x90, 0x91, 0x13}           # menu key, Print Screen, Num/Scroll Lock, Pause
EDIT_KEYS = {VK_BACK: "Backspace", VK_RETURN: "Enter", VK_DELETE: "Delete", VK_LEFT: "ArrowLeft",
             VK_RIGHT: "ArrowRight", VK_UP: "ArrowUp", VK_DOWN: "ArrowDown", VK_HOME: "Home", VK_END: "End",
             VK_TAB: "Tab", VK_PRIOR: "PageUp", VK_NEXT: "PageDown", VK_INSERT: "Insert"}

WH_KEYBOARD_LL = 13
WM_KEYDOWN, WM_SYSKEYDOWN = 0x0100, 0x0104
WM_QUIT = 0x0012
LLKHF_INJECTED, LLKHF_UP = 0x10, 0x80
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
CF_UNICODETEXT = 13


class KeyCapture:
    def __init__(self, enabled=lambda: True):
        self.supported = sys.platform == "win32"
        self._enabled = enabled
        self.cond = threading.Condition()
        self.active = False
        self.seq = 0
        self.events: list[tuple[int, dict]] = []
        self.last_contact = 0.0
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._hook_lock = threading.Lock()
        self._down: set[int] = set()        # keys we held back (their key-up is held back too)
        self._proc_cache: dict[int, bool] = {}
        targets = os.environ.get("CLEARWAY_KEY_TARGETS")
        self.targets = tuple(t.strip().lower() for t in targets.split(",")) if targets else DEFAULT_TARGETS
        if self.supported:
            self._win32_setup()
            threading.Thread(target=self._watchdog, daemon=True, name="keys-watchdog").start()

    # ------------------------------------------------------------ API used by the server
    def set_capture(self, on: bool) -> bool:
        on = bool(on) and self.supported and bool(self._enabled())
        with self.cond:
            self.last_contact = time.time()
            if on == self.active:
                return self.active
            self.active = on
            self.cond.notify_all()
        if on:
            self._start_hook()
        else:
            self._stop_hook()
        log.info("panel keyboard capture %s", "on" if on else "off")
        return on

    def poll(self, since: int) -> dict:
        """Long-poll for typed keys after `since`. Also keeps the capture alive."""
        deadline = time.time() + LONGPOLL_S
        with self.cond:
            self.last_contact = time.time()
            while self.seq <= since and self.active and time.time() < deadline:
                self.cond.wait(max(0.0, deadline - time.time()))
            self.last_contact = time.time()
            events = [e for n, e in self.events if n > since]
            return {"ok": True, "seq": self.seq, "events": events, "active": self.active}

    def _emit(self, event: dict) -> None:
        with self.cond:
            self.seq += 1
            self.events.append((self.seq, event))
            if len(self.events) > MAX_EVENTS:
                del self.events[: len(self.events) - MAX_EVENTS]
            self.cond.notify_all()

    def _watchdog(self) -> None:
        while True:
            time.sleep(0.5)
            if self.active and time.time() - self.last_contact > KEEPALIVE_S:
                log.info("panel stopped polling: keyboard handed back")
                self.set_capture(False)

    # ------------------------------------------------------------ win32 plumbing
    def _win32_setup(self) -> None:
        from ctypes import wintypes as w
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        u, k = self.user32, self.kernel32

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("vkCode", w.DWORD), ("scanCode", w.DWORD), ("flags", w.DWORD),
                        ("time", w.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
        self.KBD = KBDLLHOOKSTRUCT
        self.HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, w.WPARAM, w.LPARAM)
        u.SetWindowsHookExW.argtypes = [ctypes.c_int, self.HOOKPROC, w.HINSTANCE, w.DWORD]
        u.SetWindowsHookExW.restype = w.HHOOK
        u.CallNextHookEx.argtypes = [w.HHOOK, ctypes.c_int, w.WPARAM, w.LPARAM]
        u.CallNextHookEx.restype = ctypes.c_ssize_t
        u.UnhookWindowsHookEx.argtypes = [w.HHOOK]
        u.GetMessageW.argtypes = [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT]
        u.PostThreadMessageW.argtypes = [w.DWORD, w.UINT, w.WPARAM, w.LPARAM]
        u.GetForegroundWindow.restype = w.HWND
        u.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
        u.GetWindowThreadProcessId.restype = w.DWORD
        u.GetKeyboardLayout.argtypes = [w.DWORD]
        u.GetKeyboardLayout.restype = w.HKL
        u.GetAsyncKeyState.argtypes = [ctypes.c_int]
        u.GetAsyncKeyState.restype = ctypes.c_short
        u.GetKeyState.argtypes = [ctypes.c_int]
        u.GetKeyState.restype = ctypes.c_short
        u.ToUnicodeEx.argtypes = [w.UINT, w.UINT, ctypes.POINTER(ctypes.c_ubyte), w.LPWSTR, ctypes.c_int, w.UINT, w.HKL]
        u.OpenClipboard.argtypes = [w.HWND]
        u.GetClipboardData.argtypes = [w.UINT]
        u.GetClipboardData.restype = w.HANDLE
        k.GetModuleHandleW.argtypes = [w.LPCWSTR]
        k.GetModuleHandleW.restype = w.HMODULE
        k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        k.OpenProcess.restype = w.HANDLE
        k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
        k.CloseHandle.argtypes = [w.HANDLE]
        k.GlobalLock.argtypes = [w.HANDLE]
        k.GlobalLock.restype = ctypes.c_void_p
        k.GlobalUnlock.argtypes = [w.HANDLE]
        self._proc = self.HOOKPROC(self._hook)   # keep a reference: the hook must not be garbage collected

    def _start_hook(self) -> None:
        with self._hook_lock:
            if self._thread and self._thread.is_alive():
                self._thread.join(1.0)             # a previous capture is still shutting down
            ready = threading.Event()
            self._thread = threading.Thread(target=self._hook_thread, args=(ready,), daemon=True, name="keys-hook")
            self._thread.start()
            ready.wait(2)
            if not self.active:                    # turned off again while starting
                self._post_quit()

    def _stop_hook(self) -> None:
        with self._hook_lock:
            self._post_quit()

    def _post_quit(self) -> None:
        if self._thread_id:
            self.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)

    def _hook_thread(self, ready: threading.Event) -> None:
        from ctypes import wintypes as w
        self._thread_id = self.kernel32.GetCurrentThreadId()
        self._down.clear()
        hook = self.user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, self.kernel32.GetModuleHandleW(None), 0)
        ready.set()
        if not hook:
            log.warning("keyboard hook failed (error %s)", ctypes.get_last_error())
            self._thread_id = 0
            with self.cond:
                self.active = False
                self.cond.notify_all()
            return
        msg = w.MSG()
        try:
            while self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                pass
        finally:
            self.user32.UnhookWindowsHookEx(hook)
            self._thread_id = 0

    def _sim_in_front(self) -> bool:
        from ctypes import wintypes as w
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            return False
        key = int(hwnd)
        if key in self._proc_cache:
            return self._proc_cache[key]
        pid = w.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        name = ""
        h = self.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if h:
            buf = ctypes.create_unicode_buffer(1024)
            size = w.DWORD(1024)
            if self.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                name = buf.value.replace("/", "\\").rsplit("\\", 1)[-1].lower()
            self.kernel32.CloseHandle(h)
        ok = name in self.targets
        if len(self._proc_cache) > 64:
            self._proc_cache.clear()
        self._proc_cache[key] = ok
        return ok

    def _pressed(self, vk: int) -> bool:
        return bool(self.user32.GetAsyncKeyState(vk) & 0x8000)

    def _hook(self, code, wparam, lparam):
        try:
            if code == 0 and self.active:
                kb = ctypes.cast(lparam, ctypes.POINTER(self.KBD)).contents
                if self._decide(kb, wparam in (WM_KEYDOWN, WM_SYSKEYDOWN)):
                    return 1                      # held back from every program
        except Exception:                         # never let an error stall the keyboard
            log.exception("key hook error")
        return self.user32.CallNextHookEx(None, code, wparam, lparam)

    def _decide(self, kb, is_down: bool) -> bool:
        """True = hold this key back (and send it to the panel when it's a key press)."""
        vk = kb.vkCode
        if not is_down or kb.flags & LLKHF_UP:
            if vk in self._down:
                self._down.discard(vk)
                return True
            return False
        if kb.flags & LLKHF_INJECTED or vk in ALWAYS_PASS:
            return False
        if self._pressed(VK_LWIN) or self._pressed(VK_RWIN):
            return False
        if not self._sim_in_front():
            return False
        ctrl, alt, shift = self._pressed(VK_CONTROL), self._pressed(VK_MENU), self._pressed(VK_SHIFT)
        if alt and not ctrl:                      # Alt+Tab, Alt+Enter, Alt+Esc... stay with Windows
            if vk in (VK_TAB, VK_ESCAPE, VK_RETURN, 0x20):
                return False
            self._down.add(vk)                    # other Alt shortcuts: swallowed
            return True
        self._down.add(vk)
        if vk == VK_ESCAPE:
            if ctrl and shift:                    # Ctrl+Shift+Esc (Task Manager)
                self._down.discard(vk)
                return False
            self._emit({"t": "key", "k": "Escape"})
            threading.Thread(target=self.set_capture, args=(False,), daemon=True).start()
            return True
        if vk in EDIT_KEYS:
            self._emit({"t": "key", "k": EDIT_KEYS[vk], "shift": shift, "ctrl": ctrl and not alt})
            return True
        if ctrl and not alt:                      # Ctrl shortcuts (AltGr = Ctrl+Alt types characters)
            if vk == VK_A:
                self._emit({"t": "key", "k": "SelectAll"})
            elif vk == VK_V:
                threading.Thread(target=self._paste, daemon=True).start()
            return True
        text = self._translate(kb, shift, ctrl, alt)
        if text:
            self._emit({"t": "text", "s": text})
        return True

    def _translate(self, kb, shift: bool, ctrl: bool, alt: bool) -> str:
        """The character(s) this key types with the sim window's keyboard layout (dead keys included)."""
        from ctypes import wintypes as w
        state = (ctypes.c_ubyte * 256)()
        if shift:
            state[VK_SHIFT] = 0x80
        if ctrl:
            state[VK_CONTROL] = 0x80
        if alt:
            state[VK_MENU] = 0x80
        if self.user32.GetKeyState(VK_CAPITAL) & 1:
            state[VK_CAPITAL] = 0x01
        tid = self.user32.GetWindowThreadProcessId(self.user32.GetForegroundWindow(), None)
        hkl = self.user32.GetKeyboardLayout(tid)
        buf = ctypes.create_unicode_buffer(8)
        n = self.user32.ToUnicodeEx(kb.vkCode, kb.scanCode, state, buf, 8, 0, hkl)
        if n <= 0:
            return ""                              # dead key (^, ¨...): combines with the next one
        return "".join(ch for ch in buf.value[:n] if ch >= " " or ch == "\t")

    def _paste(self) -> None:
        text = ""
        if self.user32.OpenClipboard(None):
            try:
                h = self.user32.GetClipboardData(CF_UNICODETEXT)
                if h:
                    p = self.kernel32.GlobalLock(h)
                    if p:
                        text = ctypes.wstring_at(p)
                        self.kernel32.GlobalUnlock(h)
            finally:
                self.user32.CloseClipboard()
        text = text.replace("\r\n", "\n")[:4000]
        if text:
            self._emit({"t": "text", "s": text})
