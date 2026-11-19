"""Windows process helpers (standard library only, ctypes): one Clearway at a time, and "is vPilot running?"."""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes as wt

_mutex = None          # kept for the life of the process: Windows frees it when Clearway exits


def claim_single_instance(name: str) -> bool:
    """True if this is the only Clearway with this name (port); False if another one already runs."""
    global _mutex
    if os.name != "nt":
        return True
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.argtypes = [wt.LPVOID, wt.BOOL, wt.LPCWSTR]
    k32.CreateMutexW.restype = wt.HANDLE
    handle = k32.CreateMutexW(None, False, "Local\\" + name)
    if not handle:
        return True                       # can't tell: don't block Clearway from starting
    if ctypes.get_last_error() == 183:    # ERROR_ALREADY_EXISTS
        k32.CloseHandle(handle)
        return False
    _mutex = handle
    return True


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


def process_running(exe: str) -> bool | None:
    """Is a process with this file name (e.g. vPilot.exe) running? None if it can't be checked."""
    if os.name != "nt":
        return None
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
    k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
    k32.Process32FirstW.argtypes = [wt.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    k32.Process32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)      # TH32CS_SNAPPROCESS
    if not snap or snap == wt.HANDLE(-1).value:
        return None
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        want = exe.lower()
        while ok:
            if entry.szExeFile.lower() == want:
                return True
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
        return False
    finally:
        k32.CloseHandle(snap)
