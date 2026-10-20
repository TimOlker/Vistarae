# Copyright (c) 2026 Tim Olker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""
Vistarae Chrome Native Messaging Host: folder_dispatcher.py
Handles bidirectional native messaging communication over binary standard I/O streams.
Enforces 4-byte native-endian binary framing, Windows binary stdio configuration (os.O_BINARY),
shell metacharacter sanitization, and private UNC network share security.
"""

import ipaddress
import json
import os
import re
import socket
import struct
import subprocess
import sys
import threading
import urllib.parse

# 1MB maximum message payload ceiling enforced by Google Chrome Native Messaging
MAX_PAYLOAD_SIZE = 1024 * 1024

# Prohibited shell metacharacters
PROHIBITED_SHELL_CHARS = re.compile(r"[;&|`$><\r\n]")

# RFC 1918 Private IPv4 Networks
PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]


def log_debug(message: str) -> None:
    """Isolates all diagnostic logging strictly to sys.stderr to preserve binary stdout framing."""
    sys.stderr.write(f"[native_host] {message}\n")
    sys.stderr.flush()


def configure_binary_stdio() -> None:
    """Configures stdin and stdout to binary mode on Windows to eliminate CRLF byte alteration."""
    if sys.platform == "win32":
        try:
            import msvcrt

            msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
            log_debug("Windows binary mode enabled on stdio via msvcrt.setmode")
        except Exception as e:
            log_debug(f"Failed to set Windows binary mode: {e}")


def read_exact(stream, num_bytes: int) -> bytes | None:
    """
    Accumulates exactly num_bytes from stream.
    Prevents message truncation caused by fragmented stdio pipe packets.
    """
    buf = bytearray()
    while len(buf) < num_bytes:
        chunk = stream.read(num_bytes - len(buf))
        if not chunk:
            return None  # Stream closed / EOF
        buf.extend(chunk)
    return bytes(buf)


def read_message(stream=None) -> dict | None:
    """
    Reads a single framed message from the native input stream.
    Returns decoded dictionary or None on clean EOF.
    """
    if stream is None:
        stream = sys.stdin.buffer

    raw_len = read_exact(stream, 4)
    if raw_len is None:
        return None  # Clean EOF

    msg_len = struct.unpack("=I", raw_len)[0]
    if msg_len > MAX_PAYLOAD_SIZE:
        raise ValueError(f"Payload length {msg_len} exceeds 1MB limit")

    payload_bytes = read_exact(stream, msg_len)
    if payload_bytes is None:
        raise EOFError("Unexpected EOF while reading message payload")

    return json.loads(payload_bytes.decode("utf-8"))


def send_message(response: dict, stream=None) -> None:
    """
    Packs response dictionary with 4-byte native endian length prefix and flushes stdout buffer.
    """
    if stream is None:
        stream = sys.stdout.buffer

    encoded = json.dumps(response).encode("utf-8")
    stream.write(struct.pack("=I", len(encoded)))
    stream.write(encoded)
    stream.flush()


def is_trusted_unc_host(host: str) -> bool:
    """
    Evaluates whether a UNC hostname or IP address resides in an allowed private network.
    Guards against external NTLM credential reflection attacks.
    """
    host_clean = host.strip().lower()
    if not host_clean or host_clean in ("localhost", "127.0.0.1", "::1"):
        return True

    if host_clean.endswith(".local"):
        return True

    try:
        ip = ipaddress.ip_address(host_clean)
        return any(ip in net for net in PRIVATE_NETWORKS)
    except ValueError:
        # Check if hostname resolves to private IP
        try:
            resolved_ip = socket.gethostbyname(host_clean)
            ip = ipaddress.ip_address(resolved_ip)
            return any(ip in net for net in PRIVATE_NETWORKS)
        except Exception:
            return False


def probe_unc_share_reachability(path: str, timeout_sec: float = 1.0) -> bool:
    """
    Probes UNC network share reachability within timeout_sec using worker thread.
    Prevents thread deadlocks when network drives or NAS shares are offline.
    """
    result = {"reachable": False}

    def worker():
        try:
            result["reachable"] = os.path.exists(path)
        except Exception:
            result["reachable"] = False

    t = threading.Thread(target=worker)
    t.daemon = True
    t.start()
    t.join(timeout_sec)
    return result["reachable"]


def normalize_and_validate_path(raw_path: str) -> str:
    """
    Normalizes path, strips file:/// URIs, validates shell characters, and ensures path exists.
    Raises ValueError with specific error codes on security or validation failure.
    """
    if not raw_path or not isinstance(raw_path, str):
        raise ValueError(("INVALID_PATH", "Path must be a non-empty string"))

    # Null byte injection detection
    if "\0" in raw_path:
        raise ValueError(("NULL_BYTE_DETECTED", "Prohibited null byte in path"))

    # Shell metacharacter detection
    if PROHIBITED_SHELL_CHARS.search(raw_path):
        raise ValueError(("ILLEGAL_CHARACTERS", "Prohibited shell metacharacters detected in path"))

    # Strip file:/// or file:// scheme
    path = raw_path
    if path.startswith("file:///"):
        path = path[8:]
        # On Windows file:///C:/path -> C:/path
        if sys.platform == "win32" and len(path) > 2 and path[1] == ":":
            pass
        elif sys.platform != "win32":
            path = "/" + path
    elif path.startswith("file://"):
        path = path[7:]

    # Percent-decoding
    path = urllib.parse.unquote(path)

    # Re-check shell characters post-unquote
    if PROHIBITED_SHELL_CHARS.search(path):
        raise ValueError(
            (
                "ILLEGAL_CHARACTERS",
                "Prohibited shell metacharacters detected after decoding",
            )
        )

    # UNC network share validation
    is_unc = path.startswith("\\\\") or path.startswith("//")
    if is_unc:
        # Extract host component: \\host\share -> host
        parts = re.split(r"[\\/]+", path.lstrip("\\/"))
        unc_host = parts[0] if parts else ""
        if not is_trusted_unc_host(unc_host):
            raise ValueError(
                (
                    "UNTRUSTED_NETWORK_HOST",
                    f"External UNC host '{unc_host}' is prohibited to prevent NTLM reflection",
                )
            )

        # Reachability probe
        if not probe_unc_share_reachability(path, timeout_sec=1.0):
            raise ValueError(("NETWORK_TIMEOUT", "UNC network share probe timed out after 1.0s"))

        return path

    # Canonicalize local path
    expanded = os.path.expanduser(path)
    canonical = os.path.realpath(expanded)

    if not os.path.exists(canonical):
        raise ValueError(("PATH_NOT_FOUND", f"Directory or file does not exist: {canonical}"))

    return canonical


def launch_native_file_manager(target_path: str) -> str:
    """
    Launches OS native file explorer without shell=True to eliminate command injection.
    Resolves files to containing parent directory.
    """
    target_dir = os.path.dirname(target_path) if os.path.isfile(target_path) else target_path

    if sys.platform == "win32":
        try:
            os.startfile(target_dir)  # type: ignore[attr-defined]
        except AttributeError:
            subprocess.Popen(["explorer.exe", target_dir], shell=False)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", target_dir], shell=False)
    else:
        subprocess.Popen(["xdg-open", target_dir], shell=False)

    return target_dir


def handle_request(req: dict) -> dict:
    """Processes inbound action message and returns formatted response."""
    action = req.get("action")

    if action == "ping":
        return {
            "status": "ok",
            "action": "pong",
            "version": "1.0.0",
            "platform": sys.platform,
        }

    if action == "open_folder":
        raw_path = req.get("path")
        try:
            clean_path = normalize_and_validate_path(raw_path)
            launched_dir = launch_native_file_manager(clean_path)
            return {
                "status": "ok",
                "action": "open_folder",
                "path": launched_dir,
            }
        except ValueError as val_err:
            if isinstance(val_err.args[0], tuple):
                code, msg = val_err.args[0]
            else:
                code, msg = "VALIDATION_ERROR", str(val_err)
            return {"status": "error", "code": code, "message": msg}
        except Exception as exc:
            return {"status": "error", "code": "EXECUTION_FAILED", "message": str(exc)}

    return {
        "status": "error",
        "code": "UNKNOWN_ACTION",
        "message": f"Action '{action}' is not supported",
    }


def main():
    """Main event loop reading framed JSON requests from stdin and responding over stdout."""
    configure_binary_stdio()
    log_debug("Native messaging host dispatcher started")

    while True:
        try:
            message = read_message()
            if message is None:
                log_debug("Stdin closed by browser (EOF). Terminating cleanly.")
                sys.exit(0)

            response = handle_request(message)
            send_message(response)
        except json.JSONDecodeError:
            send_message(
                {
                    "status": "error",
                    "code": "MALFORMED_JSON",
                    "message": "Failed to decode JSON payload",
                }
            )
        except (ValueError, EOFError) as e:
            log_debug(f"Framing error: {e}")
            sys.exit(1)
        except Exception as e:
            log_debug(f"Unhandled dispatcher error: {e}")
            send_message({"status": "error", "code": "INTERNAL_ERROR", "message": str(e)})


if __name__ == "__main__":
    main()
