"""Store the GitHub library token in the operating system credential store.

No cleartext token is written to AINotePro's configuration, exported JSON, or
subprocess command-line arguments. Credentials are scoped to the repository.
This module has no third-party Python dependencies.
"""
from __future__ import annotations

import ctypes
import os
import re
import shutil
import subprocess
import sys

_SERVICE = "org.ainotepro.github-library"
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


class CredentialStoreError(RuntimeError):
    pass


def _account(repository):
    if not isinstance(repository, str) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository
    ):
        raise ValueError("Select a valid GitHub repository before saving its token")
    return repository.casefold()


def _validate_token(token):
    if not isinstance(token, str) or not _TOKEN_PATTERN.fullmatch(token):
        raise ValueError("GitHub token must contain only letters, numbers and underscores")
    if len(token) > 8192:
        raise ValueError("GitHub token is too long")
    return token


def _mac_api():
    security = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
    foundation = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    u32 = ctypes.c_uint32
    ptr = ctypes.c_void_p
    cstr = ctypes.c_char_p

    security.SecKeychainFindGenericPassword.argtypes = (
        ptr, u32, cstr, u32, cstr,
        ctypes.POINTER(u32), ctypes.POINTER(ptr), ctypes.POINTER(ptr),
    )
    security.SecKeychainFindGenericPassword.restype = ctypes.c_int32
    security.SecKeychainAddGenericPassword.argtypes = (
        ptr, u32, cstr, u32, cstr, u32, ptr, ctypes.POINTER(ptr),
    )
    security.SecKeychainAddGenericPassword.restype = ctypes.c_int32
    security.SecKeychainItemModifyAttributesAndData.argtypes = (ptr, ptr, u32, ptr)
    security.SecKeychainItemModifyAttributesAndData.restype = ctypes.c_int32
    security.SecKeychainItemDelete.argtypes = (ptr,)
    security.SecKeychainItemDelete.restype = ctypes.c_int32
    security.SecKeychainItemFreeContent.argtypes = (ptr, ptr)
    security.SecKeychainItemFreeContent.restype = ctypes.c_int32
    foundation.CFRelease.argtypes = (ptr,)
    foundation.CFRelease.restype = None
    return security, foundation


def _mac_find(security, repository, *, read_password=False):
    service = _SERVICE.encode("utf-8")
    account = repository.encode("utf-8")
    length = ctypes.c_uint32()
    data = ctypes.c_void_p()
    item = ctypes.c_void_p()
    result = security.SecKeychainFindGenericPassword(
        None, len(service), service, len(account), account,
        ctypes.byref(length) if read_password else None,
        ctypes.byref(data) if read_password else None,
        ctypes.byref(item),
    )
    return result, length, data, item


def _mac_get(repository):
    security, foundation = _mac_api()
    result, length, data, item = _mac_find(security, repository, read_password=True)
    try:
        if result == -25300:  # errSecItemNotFound
            return ""
        if result:
            raise CredentialStoreError(f"macOS Keychain read failed (status {result})")
        return ctypes.string_at(data, length.value).decode("ascii")
    finally:
        if data.value:
            security.SecKeychainItemFreeContent(None, data)
        if item.value:
            foundation.CFRelease(item)


def _mac_set(repository, token):
    security, foundation = _mac_api()
    secret = token.encode("ascii")
    secret_buffer = ctypes.create_string_buffer(secret)
    secret_ptr = ctypes.cast(secret_buffer, ctypes.c_void_p)
    status, _length, _data, item = _mac_find(security, repository)
    try:
        if status == -25300:
            service = _SERVICE.encode("utf-8")
            account = repository.encode("utf-8")
            code = security.SecKeychainAddGenericPassword(
                None, len(service), service, len(account), account,
                len(secret), secret_ptr, None,
            )
        elif status == 0:
            code = security.SecKeychainItemModifyAttributesAndData(
                item, None, len(secret), secret_ptr,
            )
        else:
            raise CredentialStoreError(f"macOS Keychain lookup failed (status {status})")
        if code:
            raise CredentialStoreError(f"macOS Keychain write failed (status {code})")
    finally:
        if item.value:
            foundation.CFRelease(item)


def _mac_delete(repository):
    security, foundation = _mac_api()
    status, _length, _data, item = _mac_find(security, repository)
    try:
        if status == -25300:
            return
        if status:
            raise CredentialStoreError(f"macOS Keychain lookup failed (status {status})")
        code = security.SecKeychainItemDelete(item)
        if code:
            raise CredentialStoreError(f"macOS Keychain delete failed (status {code})")
    finally:
        if item.value:
            foundation.CFRelease(item)


def _windows_api():
    from ctypes import wintypes

    class CREDENTIALW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR), ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", wintypes.DWORD), ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p), ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    library = ctypes.WinDLL("Advapi32", use_last_error=True)
    library.CredReadW.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(CREDENTIALW)),
    )
    library.CredReadW.restype = wintypes.BOOL
    library.CredWriteW.argtypes = (ctypes.POINTER(CREDENTIALW), wintypes.DWORD)
    library.CredWriteW.restype = wintypes.BOOL
    library.CredDeleteW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD)
    library.CredDeleteW.restype = wintypes.BOOL
    library.CredFree.argtypes = (ctypes.c_void_p,)
    library.CredFree.restype = None
    return library, CREDENTIALW


def _windows_get(repository):
    library, CREDENTIALW = _windows_api()
    pointer = ctypes.POINTER(CREDENTIALW)()
    target = _SERVICE + ":" + repository
    if not library.CredReadW(target, 1, 0, ctypes.byref(pointer)):
        if ctypes.get_last_error() == 1168:  # ERROR_NOT_FOUND
            return ""
        raise CredentialStoreError(f"Windows Credential Manager read failed ({ctypes.get_last_error()})")
    try:
        cred = pointer.contents
        return ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize).decode("ascii")
    finally:
        library.CredFree(pointer)


def _windows_set(repository, token):
    library, CREDENTIALW = _windows_api()
    secret = token.encode("ascii")
    buffer = (ctypes.c_ubyte * len(secret)).from_buffer_copy(secret)
    credential = CREDENTIALW()
    credential.Type = 1  # CRED_TYPE_GENERIC
    credential.TargetName = _SERVICE + ":" + repository
    credential.UserName = repository
    credential.CredentialBlobSize = len(secret)
    credential.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
    credential.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE (survives restart)
    if not library.CredWriteW(ctypes.byref(credential), 0):
        raise CredentialStoreError(f"Windows Credential Manager write failed ({ctypes.get_last_error()})")


def _windows_delete(repository):
    library, _credential = _windows_api()
    if not library.CredDeleteW(_SERVICE + ":" + repository, 1, 0):
        if ctypes.get_last_error() != 1168:
            raise CredentialStoreError(
                f"Windows Credential Manager delete failed ({ctypes.get_last_error()})"
            )


def _linux_run(operation, repository, token=""):
    binary = shutil.which("secret-tool")
    if not binary:
        raise CredentialStoreError(
            "Secret Service is not available. Install libsecret's secret-tool "
            "and unlock a desktop keyring to save GitHub tokens securely."
        )
    arguments = [binary, operation]
    if operation == "store":
        arguments.extend(["--label=AINotePro GitHub Library"])
    arguments.extend(["application", _SERVICE, "repository", repository])
    try:
        response = subprocess.run(
            arguments, input=token if operation == "store" else None,
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CredentialStoreError("Linux Secret Service is unavailable or timed out") from exc
    if response.returncode != 0:
        raise CredentialStoreError("Linux Secret Service operation failed or keyring is locked")
    return response.stdout.rstrip("\r\n") if operation == "lookup" else ""


def get_token(repository):
    """Return empty string if this repository has no token; never log credentials."""
    account = _account(repository)
    if sys.platform == "darwin":
        return _mac_get(account)
    if sys.platform == "win32":
        return _windows_get(account)
    if sys.platform.startswith("linux"):
        return _linux_run("lookup", account)
    raise CredentialStoreError("No supported system credential store on this platform")


def set_token(repository, token):
    account = _account(repository)
    token = _validate_token(token)
    if sys.platform == "darwin":
        _mac_set(account, token)
    elif sys.platform == "win32":
        _windows_set(account, token)
    elif sys.platform.startswith("linux"):
        _linux_run("store", account, token)
    else:
        raise CredentialStoreError("No supported system credential store on this platform")


def delete_token(repository):
    account = _account(repository)
    if sys.platform == "darwin":
        _mac_delete(account)
    elif sys.platform == "win32":
        _windows_delete(account)
    elif sys.platform.startswith("linux"):
        _linux_run("clear", account)
    else:
        raise CredentialStoreError("No supported system credential store on this platform")
