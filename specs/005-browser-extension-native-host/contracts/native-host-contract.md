# Native Host Interface Contract: Phase 5 — Chrome Native Messaging

**Feature**: `005-browser-extension-native-host`  
**Date**: 2026-10-20  
**Status**: Completed  
**Spec Reference**: [specs/005-browser-extension-native-host/spec.md](file:///d:/Coding/Vistarae/specs/005-browser-extension-native-host/spec.md)

---

## 1. Stdio Binary Framing Specification

Communication between Google Chrome and `native_host/folder_dispatcher.py` occurs over unbuffered standard input and standard output using 32-bit (4-byte) unsigned integer length framing in the host machine's native byte order:

```
+-----------------------------------+-------------------------------------------+
| Byte 0 | Byte 1 | Byte 2 | Byte 3 | Length Bytes (UTF-8 Encoded JSON String)  |
+-----------------------------------+-------------------------------------------+
| <------ 4-byte Native uint ------>| <------------ JSON Payload -------------> |
```

### 1.1 Invariant Rules
1. **Unbuffered Streams**: All reads occur on `sys.stdin.buffer`; all writes occur on `sys.stdout.buffer` followed immediately by `flush()`.
2. **Windows Binary Mode**: On Windows (`sys.platform == 'win32'`), `folder_dispatcher.py` explicitly executes:
   ```python
   import msvcrt, os
   msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
   msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
   ```
3. **Chunked Exact-Byte Read Accumulator**: Because pipe reads may deliver fragmented chunks, `read_exact` must loop until all requested bytes are gathered:
   ```python
   def read_exact(stream, n):
       buf = bytearray()
       while len(buf) < n:
           chunk = stream.read(n - len(buf))
           if not chunk:
               return None
           buf.extend(chunk)
       return bytes(buf)
   ```
4. **Standard Error Isolation**: All debug, informational, and error logging MUST be written to `sys.stderr`. Any non-framed character written to `sys.stdout` will invalidate Chrome's framing parser and terminate the native connection.
5. **Payload Size Limit**: Payloads must not exceed Chrome's native messaging limit of 1MB (1,048,576 bytes).

---

## 2. Inbound Request Messages

### 2.1 Action: `open_folder`

#### Request JSON
```json
{
  "action": "open_folder",
  "path": "C:\\Users\\Traveler\\Pictures\\Yosemite2026"
}
```

Or with `file:///` URI:
```json
{
  "action": "open_folder",
  "path": "file:///D:/Coding/Vistarae/output"
}
```

Or with private UNC network share:
```json
{
  "action": "open_folder",
  "path": "\\\\192.168.1.100\\photos\\california"
}
```

### 2.2 Action: `ping`

#### Request JSON
```json
{
  "action": "ping"
}
```

---

## 3. Outbound Response Messages

### 3.1 Success Responses

#### Open Folder Success
```json
{
  "status": "ok",
  "action": "open_folder",
  "path": "C:\\Users\\Traveler\\Pictures\\Yosemite2026"
}
```

#### Ping Success
```json
{
  "status": "ok",
  "action": "pong",
  "version": "1.0.0",
  "platform": "win32"
}
```

### 3.2 Error Responses & Error Code Catalog

```json
{
  "status": "error",
  "code": "<ERROR_CODE>",
  "message": "<Human-readable diagnostic error description>"
}
```

| Error Code | HTTP/App Mapping | Trigger Condition |
| :--- | :--- | :--- |
| `ILLEGAL_CHARACTERS` | 400 Bad Request | Input path contains shell metacharacters (`;`, `&`, `|`, `` ` ``, `$`, `>`, `<`, `\n`, `\r`) |
| `NULL_BYTE_DETECTED` | 400 Bad Request | Input path contains a null byte (`\0`) |
| `UNTRUSTED_NETWORK_HOST` | 403 Forbidden | UNC share target is not in the private subnet allowlist (`localhost`, `127.0.0.1`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `.local`) |
| `PATH_NOT_FOUND` | 404 Not Found | Canonicalized local directory or UNC share does not exist on disk |
| `NETWORK_TIMEOUT` | 504 Gateway Timeout | UNC network share reachability probe timed out after 1.0 second |
| `MALFORMED_JSON` | 400 Bad Request | Stdio payload could not be decoded as valid UTF-8 JSON |
| `EXECUTION_FAILED` | 500 Internal Error | Operating system failed to spawn the native file manager process |

---

## 4. Operating System Execution Matrix

When spawning the file manager, `folder_dispatcher.py` uses argument vectors strictly without `shell=True`:

| Operating System | API / Command | Argument Vector |
| :--- | :--- | :--- |
| **Windows** | `os.startfile` or `subprocess.Popen` | `["explorer.exe", target_dir]` |
| **macOS** | `subprocess.Popen` | `["open", target_dir]` |
| **Linux** | `subprocess.Popen` | `["xdg-open", target_dir]` |
