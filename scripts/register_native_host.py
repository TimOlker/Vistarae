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
User-level Cross-Platform Native Messaging Host Registration Tool.
Registers com.vistarae.folder_opener for Google Chrome without administrator or root rights.
- Windows: HKCU\\Software\\Google\\Chrome\\NativeMessagingHosts\\com.vistarae.folder_opener
- macOS:   ~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.vistarae.folder_opener.json
- Linux:   ~/.config/google-chrome/NativeMessagingHosts/com.vistarae.folder_opener.json
"""

import argparse
import json
import os
import stat
import sys

HOST_NAME = "com.vistarae.folder_opener"
DEFAULT_EXTENSION_ID = "ekafkcbddmcmflnbgnlkaebpllpnjggk"


def get_paths():
    """Resolves absolute repository and native host file paths."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    native_host_dir = os.path.join(repo_root, "native_host")
    dispatcher_py = os.path.join(native_host_dir, "folder_dispatcher.py")
    dispatcher_bat = os.path.join(native_host_dir, "run_dispatcher.bat")
    manifest_json = os.path.join(native_host_dir, f"{HOST_NAME}.json")
    return {
        "repo_root": repo_root,
        "native_host_dir": native_host_dir,
        "dispatcher_py": dispatcher_py,
        "dispatcher_bat": dispatcher_bat,
        "manifest_json": manifest_json,
    }


def create_manifest_data(extension_id: str, launcher_path: str) -> dict:
    """Creates the standard native messaging host manifest dictionary."""
    return {
        "name": HOST_NAME,
        "description": "Vistarae Local Folder Opener Native Host",
        "path": os.path.abspath(launcher_path),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{extension_id}/"],
    }


def register_windows(extension_id: str, uninstall: bool = False) -> bool:
    """Registers or unregisters native host in HKCU Windows Registry."""
    try:
        import winreg
    except ImportError:
        print("ERROR: winreg module unavailable (non-Windows platform)", file=sys.stderr)
        return False

    paths = get_paths()
    key_path = rf"Software\Google\Chrome\NativeMessagingHosts\{HOST_NAME}"

    if uninstall:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
            print(f"[OK] Removed registry key: HKCU\\{key_path}")
            return True
        except FileNotFoundError:
            print(f"[INFO] Registry key not found: HKCU\\{key_path}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to delete registry key: {e}", file=sys.stderr)
            return False

    # 1. Ensure run_dispatcher.bat exists
    if not os.path.exists(paths["dispatcher_bat"]):
        with open(paths["dispatcher_bat"], "w", encoding="utf-8") as f:
            f.write(
                '@echo off\nrem Vistarae Native Host Launcher\npython -u "%~dp0folder_dispatcher.py"\n'
            )

    # 2. Write manifest JSON with absolute path
    manifest_data = create_manifest_data(extension_id, paths["dispatcher_bat"])
    with open(paths["manifest_json"], "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    # 3. Register manifest in HKCU
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, os.path.abspath(paths["manifest_json"]))
        print(f"[OK] Registered manifest in HKCU\\{key_path}")
        print(f"     Manifest path: {paths['manifest_json']}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to write registry key: {e}", file=sys.stderr)
        return False


def register_unix(extension_id: str, target_dir: str, uninstall: bool = False) -> bool:
    """Registers or unregisters native host manifest on macOS or Linux."""
    paths = get_paths()
    expanded_dir = os.path.expanduser(target_dir)
    target_manifest = os.path.join(expanded_dir, f"{HOST_NAME}.json")

    if uninstall:
        if os.path.exists(target_manifest):
            os.remove(target_manifest)
            print(f"[OK] Removed native host manifest: {target_manifest}")
        else:
            print(f"[INFO] Manifest was not found: {target_manifest}")
        return True

    # 1. Apply chmod +x to folder_dispatcher.py
    if os.path.exists(paths["dispatcher_py"]):
        st = os.stat(paths["dispatcher_py"])
        os.chmod(paths["dispatcher_py"], st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # 2. Ensure target directory exists
    os.makedirs(expanded_dir, exist_ok=True)

    # 3. Write manifest
    manifest_data = create_manifest_data(extension_id, paths["dispatcher_py"])
    with open(target_manifest, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    print(f"[OK] Installed native host manifest to: {target_manifest}")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Register Vistarae Chrome Native Messaging Host without administrator privileges."
    )
    parser.add_argument(
        "--extension-id",
        default=DEFAULT_EXTENSION_ID,
        help=f"Chrome Extension ID to allow (default: {DEFAULT_EXTENSION_ID})",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove native messaging host registration",
    )
    args = parser.parse_args(argv)

    print(
        f"--- Vistarae Native Messaging Host Registration ({'Uninstall' if args.uninstall else 'Install'}) ---"
    )
    print(f"Platform: {sys.platform} | Extension ID: {args.extension_id}\n")

    if sys.platform == "win32":
        success = register_windows(args.extension_id, args.uninstall)
    elif sys.platform == "darwin":
        target = "~/Library/Application Support/Google/Chrome/NativeMessagingHosts"
        success = register_unix(args.extension_id, target, args.uninstall)
    else:  # Linux and other Unix
        target = "~/.config/google-chrome/NativeMessagingHosts"
        success = register_unix(args.extension_id, target, args.uninstall)

    if success:
        print("\nOperation completed successfully.")
        return 0
    else:
        print("\nOperation failed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
