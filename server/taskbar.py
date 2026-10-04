"""Give the studio window its own taskbar identity (Windows only).

The studio opens as an Edge/Chrome "--app" window. Without this, Windows groups it with the
browser and pinning it pins Edge. Setting the window's AppUserModel properties makes it a
separate taskbar app: pinning pins MirMediaLabs.exe with the MIR MEDIA LABS icon.
"""
import ctypes
import time
from ctypes import wintypes

APP_ID = "MirCorp.MirMediaLabs"
TITLE = "MIR MEDIA LABS"


class GUID(ctypes.Structure):
    _fields_ = [("d1", ctypes.c_ulong), ("d2", ctypes.c_ushort), ("d3", ctypes.c_ushort), ("d4", ctypes.c_ubyte * 8)]

    def __init__(self, s):
        import uuid
        u = uuid.UUID(s)
        super().__init__(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]


class PROPVARIANT(ctypes.Structure):
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort), ("r3", ctypes.c_ushort),
                ("val", ctypes.c_void_p), ("pad", ctypes.c_void_p)]


_FMT = "9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"   # PKEY_AppUserModel_*
_IID_IPropertyStore = GUID("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")
VT_LPWSTR = 31


def set_process_app_id():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def _set_props(hwnd, exe):
    store = ctypes.c_void_p()
    if ctypes.windll.shell32.SHGetPropertyStoreForWindow(hwnd, ctypes.byref(_IID_IPropertyStore), ctypes.byref(store)):
        return False
    vtbl = ctypes.cast(ctypes.cast(store, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
    SetValue = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(PROPERTYKEY),
                                  ctypes.POINTER(PROPVARIANT))(vtbl[6])
    Commit = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p)(vtbl[7])
    Release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])
    keep = []
    try:
        # relaunch info first, the ID last (the shell reads the relaunch info when the ID is set)
        for pid, text in ((2, '"%s"' % exe), (3, exe + ",0"), (4, TITLE), (5, APP_ID)):
            buf = ctypes.create_unicode_buffer(text)
            keep.append(buf)
            pv = PROPVARIANT(VT_LPWSTR, 0, 0, 0, ctypes.cast(buf, ctypes.c_void_p), None)
            SetValue(store, ctypes.byref(PROPERTYKEY(GUID(_FMT), pid)), ctypes.byref(pv))
        Commit(store)
        return True
    except OSError:
        return False
    finally:
        Release(store)


def _find_windows(title):
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                b = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, b, n + 1)
                if b.value.startswith(title):
                    found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found


def brand_window(exe, timeout=20.0):
    """Wait for the studio window and give it the MIR MEDIA LABS taskbar identity."""
    end = time.time() + timeout
    while time.time() < end:
        hwnds = _find_windows(TITLE)
        if hwnds:
            time.sleep(0.5)         # let the browser finish setting its own properties first
            return any(_set_props(h, exe) for h in _find_windows(TITLE))
        time.sleep(0.25)
    return False
