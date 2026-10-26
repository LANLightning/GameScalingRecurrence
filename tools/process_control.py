import ctypes
from ctypes import wintypes as W
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
k.CloseHandle.argtypes=[W.HANDLE]
k.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,ctypes.POINTER(W.DWORD)]
k.GetProcessTimes.argtypes=[W.HANDLE,ctypes.POINTER(W.FILETIME),ctypes.POINTER(W.FILETIME),ctypes.POINTER(W.FILETIME),ctypes.POINTER(W.FILETIME)]
k.TerminateProcess.argtypes=[W.HANDLE,W.UINT]
def identity(pid):
    h=k.OpenProcess(0x1000,False,pid)
    if not h:return None
    try:
        size=W.DWORD(32768);path=ctypes.create_unicode_buffer(size.value)
        if not k.QueryFullProcessImageNameW(h,0,path,ctypes.byref(size)):return None
        a,b,c,d=W.FILETIME(),W.FILETIME(),W.FILETIME(),W.FILETIME()
        if not k.GetProcessTimes(h,ctypes.byref(a),ctypes.byref(b),ctypes.byref(c),ctypes.byref(d)):return None
        return {'exe':path.value,'created':(a.dwHighDateTime<<32)|a.dwLowDateTime}
    finally:k.CloseHandle(h)
def terminate(record):
    if identity(record['pid'])!=record['identity']:return False
    h=k.OpenProcess(0x1001,False,record['pid'])
    if not h:return False
    try:return bool(k.TerminateProcess(h,0))
    finally:k.CloseHandle(h)
