"""Per-user Windows single-instance guard and a payload-free wake-up signal.

The first Maodan owns a named mutex. A later launch finds it taken, sets the wake event and exits,
and the running Maodan comes back on screen. Elsewhere every launch simply owns itself.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
from ctypes import wintypes
from pathlib import Path


def _object_name(name: str) -> str:
    # Scoped to this copy of the project and this user's profile, so two copies never collide.
    identity = f'{Path(__file__).resolve().parent}|{os.getenv("APPDATA", "")}'.lower()
    scope = hashlib.sha256(identity.encode()).hexdigest()[:24]
    return f'Local\\Maodan-{scope}-{name}'


class WindowsInstance:
    def __init__(self, name: str):
        self.owner = True
        self._mutex = None
        self._event = None
        self._api = None
        if os.name != 'nt':
            return

        api = ctypes.WinDLL('kernel32', use_last_error=True)
        api.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        api.CreateMutexW.restype = wintypes.HANDLE
        api.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        api.CreateEventW.restype = wintypes.HANDLE
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        api.CloseHandle.restype = wintypes.BOOL
        api.SetEvent.argtypes = [wintypes.HANDLE]
        api.SetEvent.restype = wintypes.BOOL
        api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        api.WaitForSingleObject.restype = wintypes.DWORD
        self._api = api
        prefix = _object_name(name)
        self._mutex = api.CreateMutexW(None, False, prefix)
        if not self._mutex:
            raise ctypes.WinError(ctypes.get_last_error())
        self.owner = ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS
        self._event = api.CreateEventW(None, False, False, prefix + '-wake')
        if not self._event:
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def wake(self) -> None:
        if self._event and not self._api.SetEvent(self._event):
            raise ctypes.WinError(ctypes.get_last_error())

    def consume_wake(self) -> bool:
        return bool(self._event and self._api.WaitForSingleObject(self._event, 0) == 0)

    def close(self) -> None:
        for attribute in ('_event', '_mutex'):
            handle = getattr(self, attribute)
            if handle:
                self._api.CloseHandle(handle)
                setattr(self, attribute, None)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()
