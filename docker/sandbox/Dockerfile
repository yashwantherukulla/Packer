# The ONLY environment extracted (hostile) code may run in (ADR-008).
# Base pinned by tag; pin by digest in CI/prod. strace enables the syscall trace (ADR-009).
FROM python:3.10.19-slim-bookworm

# strace from the pinned distro. ca-certificates deliberately NOT installed:
# the container runs with --network=none, so outbound TLS must be impossible anyway.
RUN apt-get update \
 && apt-get install -y --no-install-recommends strace \
 && rm -rf /var/lib/apt/lists/*

# Non-root user; extracted code never runs as root even before --user is re-applied at run.
RUN groupadd --gid 1000 sandbox \
 && useradd --uid 1000 --gid 1000 --no-create-home --shell /usr/sbin/nologin sandbox

# Root FS is mounted --read-only at run; /scratch is the only writable path (a small tmpfs).
WORKDIR /scratch
USER 1000:1000

# No phone-home entrypoint; the runner supplies argv per unit. This CMD is a liveness check.
CMD ["python3", "-c", "print('packer-sandbox ready')"]
