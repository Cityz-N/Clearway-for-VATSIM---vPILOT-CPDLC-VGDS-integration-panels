"""Windows notification-area (system tray) icon, using only ctypes.

Double-click opens Clearway in the browser; right-click shows a small menu.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import threading
from typing import Callable

user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32
kernel32 = ctypes.windll.kernel32

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_TIMER = 0x0113
WM_NULL = 0x0000
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_APP_TRAY = 0x8000 + 20
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x1, 0x2, 0x4, 0x10
MF_STRING, MF_GRAYED, MF_SEPARATOR = 0x0, 0x1, 0x800
TPM_RIGHTBUTTON, TPM_RETURNCMD = 0x2, 0x100
IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x10, 0x40
MB_ICONINFORMATION = 0x40


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("hWnd", wt.HWND), ("uID", wt.UINT), ("uFlags", wt.UINT),
                ("uCallbackMessage", wt.UINT), ("hIcon", wt.HICON), ("szTip", wt.WCHAR * 128),
                ("dwState", wt.DWORD), ("dwStateMask", wt.DWORD), ("szInfo", wt.WCHAR * 256),
                ("uVersion", wt.UINT), ("szInfoTitle", wt.WCHAR * 64), ("dwInfoFlags", wt.DWORD),
                ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wt.HICON)]


user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
user32.CreateWindowExW.restype = wt.HWND
user32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.LoadImageW.restype = wt.HANDLE
user32.CreatePopupMenu.restype = wt.HMENU
user32.AppendMenuW.argtypes = [wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR]
user32.TrackPopupMenu.argtypes = [wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.LPVOID]
user32.SetMenuDefaultItem.argtypes = [wt.HMENU, wt.UINT, wt.UINT]
user32.DestroyMenu.argtypes = [wt.HMENU]
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.SetTimer.argtypes = [wt.HWND, ctypes.c_size_t, wt.UINT, wt.LPVOID]
user32.DestroyWindow.argtypes = [wt.HWND]
user32.SetForegroundWindow.argtypes = [wt.HWND]
shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
kernel32.GetModuleHandleW.restype = wt.HMODULE


def message_box(text: str, title: str = "Clearway") -> None:
    user32.MessageBoxW(None, text, title, MB_ICONINFORMATION)


class TrayIcon:
    """``menu`` returns a list of (label, callback, enabled) tuples, or None for a separator.
    The first enabled item is the double-click default."""

    ID_BASE = 1000

    def __init__(self, icon_path: str, tooltip: Callable[[], str], menu: Callable[[], list],
                 on_open: Callable[[], None]):
        self._icon_path = icon_path
        self._tooltip = tooltip
        self._menu = menu
        self._on_open = on_open
        self._actions: dict[int, Callable[[], None]] = {}
        self._wndproc = WNDPROC(self._proc)   # keep a reference so it isn't garbage collected
        self.hwnd = None
        self._nid = None
        self._taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")

    # ------------------------------------------------------------ public
    def run(self, balloon: str | None = None) -> None:
        """Create the icon and run the Windows message loop (blocks until quit())."""
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = "ClearwayTrayWindow"
        user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = user32.CreateWindowExW(0, wc.lpszClassName, "Clearway", 0, 0, 0, 0, 0, None, None, hinst, None)
        if not self.hwnd:
            raise ctypes.WinError()
        self._add_icon(balloon)
        if not self._nid or not self._nid.hIcon:
            raise RuntimeError(f"tray icon image could not be loaded from {self._icon_path}")
        user32.SetTimer(self.hwnd, 1, 3000, None)
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def quit(self) -> None:
        if self.hwnd:
            user32.PostMessageW(self.hwnd, 0x0010, 0, 0)   # WM_CLOSE -> DestroyWindow -> WM_DESTROY

    # ------------------------------------------------------------ internals
    def _add_icon(self, balloon: str | None = None) -> None:
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_APP_TRAY
        nid.hIcon = user32.LoadImageW(None, self._icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
        nid.szTip = self._tooltip()[:127]
        if balloon:
            nid.uFlags |= NIF_INFO
            nid.szInfo = balloon[:255]
            nid.szInfoTitle = "Clearway"
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
        self._nid = nid

    def _refresh_tooltip(self) -> None:
        if not self._nid:
            return
        self._nid.uFlags = NIF_TIP
        self._nid.szTip = self._tooltip()[:127]
        shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))

    def _show_menu(self) -> None:
        hmenu = user32.CreatePopupMenu()
        self._actions.clear()
        default_id = None
        for i, item in enumerate(self._menu()):
            if item is None:
                user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
                continue
            label, action, enabled = item
            cmd = self.ID_BASE + i
            user32.AppendMenuW(hmenu, MF_STRING | (0 if enabled else MF_GRAYED), cmd, label)
            if enabled and action:
                self._actions[cmd] = action
                if default_id is None:
                    default_id = cmd
        if default_id:
            user32.SetMenuDefaultItem(hmenu, default_id, 0)
        pt = wt.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)
        cmd = user32.TrackPopupMenu(hmenu, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.x, pt.y, 0, self.hwnd, None)
        user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        user32.DestroyMenu(hmenu)
        action = self._actions.get(cmd)
        if action:
            # run outside the message loop so slow actions (network) never freeze the icon
            threading.Thread(target=action, daemon=True).start()

    def _proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_APP_TRAY:
            if lparam == WM_LBUTTONDBLCLK:
                threading.Thread(target=self._on_open, daemon=True).start()
            elif lparam == WM_RBUTTONUP:
                self._show_menu()
            return 0
        if msg == WM_TIMER:
            self._refresh_tooltip()
            return 0
        if msg == self._taskbar_created:       # Explorer restarted: put the icon back
            self._add_icon()
            return 0
        if msg == WM_DESTROY:
            if self._nid:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
                self._nid = None
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
