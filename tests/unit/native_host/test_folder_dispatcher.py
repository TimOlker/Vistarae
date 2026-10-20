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
Unit tests for folder_dispatcher.py.
Validates 4-byte native-endian framing, chunked read accumulation,
shell metacharacter sanitization, UNC private subnet security, and OS launching.
Enforces >= 90% branch and line coverage.
"""

import io
import json
import struct
import sys
import unittest.mock as mock

import pytest

from native_host.folder_dispatcher import (
    configure_binary_stdio,
    handle_request,
    is_trusted_unc_host,
    launch_native_file_manager,
    log_debug,
    main,
    normalize_and_validate_path,
    probe_unc_share_reachability,
    read_exact,
    read_message,
    send_message,
)


class ChunkedStream:
    """Simulates fragmented stdio pipe delivery returning small byte chunks."""

    def __init__(self, data: bytes, chunk_size: int = 2):
        self.data = data
        self.chunk_size = chunk_size
        self.offset = 0

    def read(self, n: int) -> bytes:
        if self.offset >= len(self.data):
            return b""
        size = min(n, self.chunk_size)
        chunk = self.data[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


def test_read_exact_accumulation_and_eof():
    """Verifies that read_exact properly accumulates chunks and handles EOF."""
    data = b"Hello, Vistarae Native Host!"
    stream = ChunkedStream(data, chunk_size=3)

    result = read_exact(stream, len(data))
    assert result == data

    # Test clean EOF
    eof_result = read_exact(stream, 4)
    assert eof_result is None


def test_read_message_framing_and_decode():
    """Tests 4-byte native-endian decoding of JSON payloads."""
    payload = {"action": "ping"}
    encoded = json.dumps(payload).encode("utf-8")
    wire_data = struct.pack("=I", len(encoded)) + encoded

    stream = io.BytesIO(wire_data)
    msg = read_message(stream)
    assert msg == payload

    # Test clean EOF on 0 bytes
    empty_stream = io.BytesIO(b"")
    assert read_message(empty_stream) is None


def test_read_message_default_stream():
    """Tests read_message using default sys.stdin.buffer."""
    payload = {"action": "ping"}
    encoded = json.dumps(payload).encode("utf-8")
    wire_data = struct.pack("=I", len(encoded)) + encoded

    mock_stdin = io.BytesIO(wire_data)
    with mock.patch("sys.stdin", mock.MagicMock(buffer=mock_stdin)):
        msg = read_message()
        assert msg == payload


def test_send_message_default_stream():
    """Tests send_message using default sys.stdout.buffer."""
    mock_stdout = io.BytesIO()
    with mock.patch("sys.stdout", mock.MagicMock(buffer=mock_stdout)):
        send_message({"status": "ok"})
        raw = mock_stdout.getvalue()
        assert len(raw) > 4
        msg_len = struct.unpack("=I", raw[:4])[0]
        assert msg_len == len(raw[4:])


def test_read_message_payload_size_ceiling():
    """Asserts that payloads exceeding 1MB raise ValueError."""
    fake_len = struct.pack("=I", 1024 * 1024 + 1)
    stream = io.BytesIO(fake_len + b"{}")

    with pytest.raises(ValueError, match="exceeds 1MB limit"):
        read_message(stream)


def test_read_message_unexpected_eof():
    """Asserts that stream truncation during payload read raises EOFError."""
    fake_len = struct.pack("=I", 100)
    stream = io.BytesIO(fake_len + b"short")

    with pytest.raises(EOFError):
        read_message(stream)


def test_send_message_framing():
    """Verifies that send_message writes a 4-byte native endian length header followed by JSON."""
    stream = io.BytesIO()
    response = {"status": "ok", "action": "pong"}

    send_message(response, stream)
    raw_output = stream.getvalue()

    msg_len = struct.unpack("=I", raw_output[:4])[0]
    payload_bytes = raw_output[4:]

    assert msg_len == len(payload_bytes)
    assert json.loads(payload_bytes.decode("utf-8")) == response


def test_shell_metacharacter_rejection():
    """Asserts that shell metacharacters (; & | ` $ > < \n \r) are immediately rejected."""
    bad_chars = [";", "&", "|", "`", "$", ">", "<", "\n", "\r"]
    for char in bad_chars:
        malicious_path = f"/photos{char}rm -rf /"
        with pytest.raises(ValueError) as excinfo:
            normalize_and_validate_path(malicious_path)
        code, _ = excinfo.value.args[0]
        assert code == "ILLEGAL_CHARACTERS"


def test_null_byte_rejection():
    """Asserts that null byte injection is detected and rejected with NULL_BYTE_DETECTED."""
    poisoned_path = "/photos/safe\0/etc/shadow"
    with pytest.raises(ValueError) as excinfo:
        normalize_and_validate_path(poisoned_path)
    code, _ = excinfo.value.args[0]
    assert code == "NULL_BYTE_DETECTED"


def test_empty_or_non_string_path():
    """Asserts that empty or invalid type paths are rejected with INVALID_PATH."""
    with pytest.raises(ValueError) as exc1:
        normalize_and_validate_path("")
    assert exc1.value.args[0][0] == "INVALID_PATH"

    with pytest.raises(ValueError) as exc2:
        normalize_and_validate_path(None)  # type: ignore
    assert exc2.value.args[0][0] == "INVALID_PATH"


def test_percent_encoded_shell_character_rejection():
    """Asserts that shell metacharacters encoded via URL percent syntax (%3B) are rejected."""
    encoded_path = "file:///photos%3Bcalc.exe"
    with pytest.raises(ValueError) as excinfo:
        normalize_and_validate_path(encoded_path)
    code, _ = excinfo.value.args[0]
    assert code == "ILLEGAL_CHARACTERS"


def test_unc_private_host_validation():
    """Verifies that private IP subnets and localhost are trusted for UNC paths."""
    assert is_trusted_unc_host("localhost") is True
    assert is_trusted_unc_host("127.0.0.1") is True
    assert is_trusted_unc_host("192.168.1.100") is True
    assert is_trusted_unc_host("10.0.1.50") is True
    assert is_trusted_unc_host("172.16.0.10") is True
    assert is_trusted_unc_host("nas.local") is True

    # External internet hosts must be rejected
    assert is_trusted_unc_host("attacker.com") is False
    assert is_trusted_unc_host("8.8.8.8") is False
    assert is_trusted_unc_host("203.0.113.1") is False


def test_unc_external_host_rejection():
    """Verifies that external UNC shares raise UNTRUSTED_NETWORK_HOST to prevent NTLM reflection."""
    external_unc = "\\\\evil-attacker.com\\share\\photos"
    with pytest.raises(ValueError) as excinfo:
        normalize_and_validate_path(external_unc)
    code, _ = excinfo.value.args[0]
    assert code == "UNTRUSTED_NETWORK_HOST"


def test_unc_reachability_probe_success():
    """Verifies probe_unc_share_reachability returns True for accessible shares."""
    with mock.patch("os.path.exists", return_value=True):
        assert probe_unc_share_reachability("\\\\192.168.1.100\\share") is True


def test_unc_reachability_timeout(monkeypatch):
    """Verifies that unreachable private UNC shares return NETWORK_TIMEOUT."""
    monkeypatch.setattr(
        "native_host.folder_dispatcher.probe_unc_share_reachability",
        lambda path, timeout_sec: False,
    )
    private_unc = "\\\\192.168.1.254\\offline_nas\\photos"
    with pytest.raises(ValueError) as excinfo:
        normalize_and_validate_path(private_unc)
    code, _ = excinfo.value.args[0]
    assert code == "NETWORK_TIMEOUT"


def test_file_uri_normalization(tmp_path):
    """Verifies that file:/// URIs are stripped, percent-decoded, and resolved."""
    test_dir = tmp_path / "My Yosemite Photos"
    test_dir.mkdir()

    uri = test_dir.as_uri()
    normalized = normalize_and_validate_path(uri)
    assert normalized == str(test_dir.resolve())

    # Test file:// prefix without third slash
    uri2 = "file://" + str(test_dir.resolve()).replace("\\", "/")
    normalized2 = normalize_and_validate_path(uri2)
    assert normalized2 == str(test_dir.resolve())


def test_path_not_found():
    """Asserts that non-existent paths raise PATH_NOT_FOUND."""
    fake_path = "/non_existent_vistarae_path_98765"
    with pytest.raises(ValueError) as excinfo:
        normalize_and_validate_path(fake_path)
    code, _ = excinfo.value.args[0]
    assert code == "PATH_NOT_FOUND"


def test_launch_native_file_manager_platforms(tmp_path):
    """Tests file manager launching across Windows, macOS, and Linux."""
    test_file = tmp_path / "photo.jpg"
    test_file.write_text("dummy")

    # 1. Windows test
    with (
        mock.patch("sys.platform", "win32"),
        mock.patch("os.startfile", create=True) as mock_startfile,
    ):
        launched = launch_native_file_manager(str(test_file))
        assert launched == str(tmp_path)
        mock_startfile.assert_called_once_with(str(tmp_path))

    # 2. macOS test
    with mock.patch("sys.platform", "darwin"), mock.patch("subprocess.Popen") as mock_popen:
        launched = launch_native_file_manager(str(tmp_path))
        assert launched == str(tmp_path)
        mock_popen.assert_called_once_with(["open", str(tmp_path)], shell=False)

    # 3. Linux test
    with mock.patch("sys.platform", "linux"), mock.patch("subprocess.Popen") as mock_popen:
        launched = launch_native_file_manager(str(tmp_path))
        assert launched == str(tmp_path)
        mock_popen.assert_called_once_with(["xdg-open", str(tmp_path)], shell=False)


def test_handle_request_ping():
    """Verifies the ping action returns ok, pong, and platform."""
    res = handle_request({"action": "ping"})
    assert res["status"] == "ok"
    assert res["action"] == "pong"
    assert res["platform"] == sys.platform


def test_handle_request_open_folder_success(tmp_path):
    """Verifies open_folder returns status: ok with resolved directory."""
    with mock.patch("native_host.folder_dispatcher.launch_native_file_manager") as mock_launch:
        mock_launch.return_value = str(tmp_path)
        res = handle_request({"action": "open_folder", "path": str(tmp_path)})
        assert res["status"] == "ok"
        assert res["path"] == str(tmp_path)


def test_handle_request_open_folder_execution_failed(tmp_path):
    """Verifies unexpected execution errors return EXECUTION_FAILED."""
    with mock.patch(
        "native_host.folder_dispatcher.normalize_and_validate_path",
        side_effect=RuntimeError("OS pipe broken"),
    ):
        res = handle_request({"action": "open_folder", "path": str(tmp_path)})
        assert res["status"] == "error"
        assert res["code"] == "EXECUTION_FAILED"


def test_handle_request_unknown_action():
    """Verifies unknown actions return error with UNKNOWN_ACTION code."""
    res = handle_request({"action": "format_c_drive"})
    assert res["status"] == "error"
    assert res["code"] == "UNKNOWN_ACTION"


def test_configure_binary_stdio_and_logging(capsys):
    """Verifies log_debug writes to stderr and configure_binary_stdio executes without error."""
    log_debug("Diagnostic test log")
    captured = capsys.readouterr()
    assert "[native_host] Diagnostic test log" in captured.err
    assert captured.out == ""

    # Should not raise exception on any platform
    configure_binary_stdio()


def test_main_event_loop_success_and_eof():
    """Verifies main loop processes inbound messages and exits on EOF."""
    ping_payload = {"action": "ping"}
    encoded = json.dumps(ping_payload).encode("utf-8")
    wire_data = struct.pack("=I", len(encoded)) + encoded

    mock_in = io.BytesIO(wire_data)
    mock_out = io.BytesIO()

    with (
        mock.patch("sys.stdin", mock.MagicMock(buffer=mock_in)),
        mock.patch("sys.stdout", mock.MagicMock(buffer=mock_out)),
        pytest.raises(SystemExit) as exit_info,
    ):
        main()
    assert exit_info.value.code == 0

    # Inspect response written to stdout
    raw_out = mock_out.getvalue()
    msg_len = struct.unpack("=I", raw_out[:4])[0]
    res = json.loads(raw_out[4 : 4 + msg_len].decode("utf-8"))
    assert res["status"] == "ok"
    assert res["action"] == "pong"


def test_launch_native_file_manager_directory_direct(tmp_path):
    """Verifies that launching a directory uses the directory directly."""
    with (
        mock.patch("sys.platform", "win32"),
        mock.patch("os.startfile", create=True) as mock_startfile,
    ):
        launched = launch_native_file_manager(str(tmp_path))
        assert launched == str(tmp_path)
        mock_startfile.assert_called_once_with(str(tmp_path))


def test_file_uri_non_windows_path_normalization():
    """Verifies file:/// normalization under POSIX simulation."""
    with (
        mock.patch("sys.platform", "linux"),
        mock.patch("os.path.exists", return_value=True),
        mock.patch("os.path.realpath", return_value="/var/photos"),
    ):
        res = normalize_and_validate_path("file:///var/photos")
        assert res == "/var/photos"


def test_handle_request_plain_value_error():
    """Verifies handle_request handles standard single-string ValueError."""
    with mock.patch(
        "native_host.folder_dispatcher.normalize_and_validate_path",
        side_effect=ValueError("Direct string validation message"),
    ):
        res = handle_request({"action": "open_folder", "path": "/test"})
        assert res["status"] == "error"
        assert res["code"] == "VALIDATION_ERROR"
        assert "Direct string validation message" in res["message"]


def test_main_event_loop_malformed_json():
    """Verifies main loop catches malformed JSON and writes MALFORMED_JSON error."""
    bad_json = b"{invalid json"
    wire_data = struct.pack("=I", len(bad_json)) + bad_json

    mock_in = io.BytesIO(wire_data)
    mock_out = io.BytesIO()

    with (
        mock.patch("sys.stdin", mock.MagicMock(buffer=mock_in)),
        mock.patch("sys.stdout", mock.MagicMock(buffer=mock_out)),
        pytest.raises(SystemExit),
    ):
        main()

    raw_out = mock_out.getvalue()
    msg_len = struct.unpack("=I", raw_out[:4])[0]
    res = json.loads(raw_out[4 : 4 + msg_len].decode("utf-8"))
    assert res["code"] == "MALFORMED_JSON"
