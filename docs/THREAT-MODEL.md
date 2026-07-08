# Sandbox Threat Model (Part 3)

## Attacker
The author of a malicious model or of code extracted from one. They control the bytes
that Part 3 reconstructs and executes.

## Trust boundary
The Docker sandbox container (ADR-008). Everything the extracted code does happens
inside it; nothing it does may affect the host, the network, or other jobs.

## Assets to protect
- **Host filesystem** — no reads outside the container, no writes outside its tmpfs.
- **Host / other-tenant network** — no outbound or lateral connectivity.
- **Other jobs & the worker process** — no resource exhaustion, no privilege escalation.

## Controls (each mapped to an adversarial test in test_containment.py)
| Control (ADR-008) | Flag | Adversarial test |
|---|---|---|
| No network | `--network=none` | outbound socket connect is blocked + recorded |
| Read-only root | `--read-only` | write outside tmpfs raises EROFS |
| Scratch only in tmpfs | `--tmpfs /scratch` | write to /scratch succeeds; nowhere else |
| Drop capabilities | `--cap-drop=ALL` | privileged op (mount) fails |
| No privilege escalation | `--security-opt=no-new-privileges` | setuid gains nothing |
| Non-root UID | `--user <uid>` | `id -u` != 0 |
| PID limit | `--pids-limit` | fork bomb hits the cap, container survives |
| Memory limit | `--memory` | allocation past the cap is OOM-killed |
| CPU limit | `--cpus` | throughput bounded (documented, not asserted hard) |
| Wall-clock timeout | policy `timeout_s` | infinite loop is killed, `timed_out=True` |

## Residual risks
Kernel / Docker-daemon 0-days (out of scope; mitigated by keeping the image minimal and
the daemon patched). gVisor/e2b is a future substrate swap via the `SandboxRunner` port.
