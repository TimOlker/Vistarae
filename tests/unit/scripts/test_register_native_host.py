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
Unit tests for register_native_host.py.
Validates cross-platform user-level registration without admin privileges across
Windows Registry (HKCU), macOS Application Support, and Linux config paths.
"""

import os
import sys
import unittest.mock as mock

from scripts.register_native_host import (
    DEFAULT_EXTENSION_ID,
    HOST_NAME,
    create_manifest_data,
    get_paths,
    main,
    register_unix,
    register_windows,
)


def test_get_paths():
    """Verifies path resolution returns expected files under repo structure."""
    paths = get_paths()
    assert os.path.isdir(paths["repo_root"])
    assert paths["dispatcher_py"].endswith("folder_dispatcher.py")
    assert paths["dispatcher_bat"].endswith("run_dispatcher.bat")
    assert paths["manifest_json"].endswith(f"{HOST_NAME}.json")


def test_create_manifest_data():
    """Verifies generated manifest dictionary matches Chrome Native Messaging specification."""
    manifest = create_manifest_data("custom_ext_id_123", "D:/test/launcher.bat")
    assert manifest["name"] == HOST_NAME
    assert manifest["type"] == "stdio"
    assert manifest["path"] == os.path.abspath("D:/test/launcher.bat")
    assert manifest["allowed_origins"] == ["chrome-extension://custom_ext_id_123/"]


def test_register_windows_install(tmp_path, monkeypatch):
    """Verifies Windows registration creates batch launcher, writes manifest, and calls winreg."""
    mock_winreg = mock.MagicMock()
    mock_key = mock.MagicMock()
    mock_winreg.CreateKey.return_value.__enter__.return_value = mock_key
    mock_winreg.HKEY_CURRENT_USER = "HKCU"
    mock_winreg.REG_SZ = 1

    monkeypatch.setitem(sys.modules, "winreg", mock_winreg)

    # Mock get_paths to use temp directory
    test_paths = {
        "repo_root": str(tmp_path),
        "native_host_dir": str(tmp_path),
        "dispatcher_py": str(tmp_path / "folder_dispatcher.py"),
        "dispatcher_bat": str(tmp_path / "run_dispatcher.bat"),
        "manifest_json": str(tmp_path / f"{HOST_NAME}.json"),
    }
    monkeypatch.setattr("scripts.register_native_host.get_paths", lambda: test_paths)

    success = register_windows("my_test_ext_id", uninstall=False)
    assert success is True

    # Assert batch launcher exists
    assert os.path.exists(test_paths["dispatcher_bat"])
    # Assert manifest exists
    assert os.path.exists(test_paths["manifest_json"])

    # Assert winreg was called
    expected_sub_key = rf"Software\Google\Chrome\NativeMessagingHosts\{HOST_NAME}"
    mock_winreg.CreateKey.assert_called_once_with("HKCU", expected_sub_key)
    mock_winreg.SetValue.assert_called_once_with(
        mock_key, "", 1, os.path.abspath(test_paths["manifest_json"])
    )


def test_register_windows_uninstall(monkeypatch):
    """Verifies Windows uninstall calls winreg.DeleteKey."""
    mock_winreg = mock.MagicMock()
    mock_winreg.HKEY_CURRENT_USER = "HKCU"
    monkeypatch.setitem(sys.modules, "winreg", mock_winreg)

    success = register_windows("my_test_ext_id", uninstall=True)
    assert success is True

    expected_sub_key = rf"Software\Google\Chrome\NativeMessagingHosts\{HOST_NAME}"
    mock_winreg.DeleteKey.assert_called_once_with("HKCU", expected_sub_key)


def test_register_windows_uninstall_not_found(monkeypatch):
    """Verifies Windows uninstall handles FileNotFoundError gracefully."""
    mock_winreg = mock.MagicMock()
    mock_winreg.HKEY_CURRENT_USER = "HKCU"
    mock_winreg.DeleteKey.side_effect = FileNotFoundError()
    monkeypatch.setitem(sys.modules, "winreg", mock_winreg)

    success = register_windows("my_test_ext_id", uninstall=True)
    assert success is True


def test_register_windows_import_error(monkeypatch):
    """Verifies register_windows handles platforms where winreg is not present."""
    monkeypatch.setitem(sys.modules, "winreg", None)
    assert register_windows("ext_id") is False


def test_register_unix_install(tmp_path, monkeypatch):
    """Verifies macOS/Linux registration applies chmod +x and writes manifest to user folder."""
    target_dir = tmp_path / "chrome_user_hosts"
    test_py = tmp_path / "folder_dispatcher.py"
    test_py.write_text("#!/usr/bin/env python\nprint('dispatcher')\n")

    test_paths = {
        "repo_root": str(tmp_path),
        "native_host_dir": str(tmp_path),
        "dispatcher_py": str(test_py),
        "dispatcher_bat": str(tmp_path / "run_dispatcher.bat"),
        "manifest_json": str(tmp_path / f"{HOST_NAME}.json"),
    }
    monkeypatch.setattr("scripts.register_native_host.get_paths", lambda: test_paths)

    success = register_unix("test_ext_id", str(target_dir), uninstall=False)
    assert success is True

    target_manifest = target_dir / f"{HOST_NAME}.json"
    assert target_manifest.exists()


def test_register_unix_uninstall(tmp_path):
    """Verifies Unix uninstall deletes target manifest file."""
    target_dir = tmp_path / "chrome_user_hosts"
    target_dir.mkdir(parents=True)
    target_manifest = target_dir / f"{HOST_NAME}.json"
    target_manifest.write_text("{}")

    success = register_unix("test_ext_id", str(target_dir), uninstall=True)
    assert success is True
    assert not target_manifest.exists()

    # Repeat when file already deleted
    success2 = register_unix("test_ext_id", str(target_dir), uninstall=True)
    assert success2 is True


def test_main_cli_execution_windows(monkeypatch):
    """Tests CLI entry point on Windows."""
    monkeypatch.setattr(sys, "platform", "win32")
    with mock.patch("scripts.register_native_host.register_windows", return_value=True) as mock_reg:
        ret = main(["--extension-id", "custom_id_999"])
        assert ret == 0
        mock_reg.assert_called_once_with("custom_id_999", False)


def test_main_cli_execution_macos(monkeypatch):
    """Tests CLI entry point on macOS."""
    monkeypatch.setattr(sys, "platform", "darwin")
    with mock.patch("scripts.register_native_host.register_unix", return_value=True) as mock_reg:
        ret = main(["--uninstall"])
        assert ret == 0
        mock_reg.assert_called_once_with(
            DEFAULT_EXTENSION_ID,
            "~/Library/Application Support/Google/Chrome/NativeMessagingHosts",
            True,
        )


def test_main_cli_execution_linux(monkeypatch):
    """Tests CLI entry point on Linux."""
    monkeypatch.setattr(sys, "platform", "linux")
    with mock.patch("scripts.register_native_host.register_unix", return_value=True) as mock_reg:
        ret = main([])
        assert ret == 0
        mock_reg.assert_called_once_with(
            DEFAULT_EXTENSION_ID, "~/.config/google-chrome/NativeMessagingHosts", False
        )


def test_main_cli_failure(monkeypatch):
    """Tests CLI entry point returning exit code 1 on registration failure."""
    monkeypatch.setattr(sys, "platform", "win32")
    with mock.patch("scripts.register_native_host.register_windows", return_value=False):
        ret = main([])
        assert ret == 1
