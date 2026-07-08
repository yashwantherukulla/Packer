# Release Checklist

- [ ] Per-PR CI (`quality` + `integration`) green on the release commit.
- [ ] Nightly E2E (`e2e-nightly.yml`) green: API chain + Playwright chain.
- [ ] Sandbox containment gate green; `docs/THREAT-MODEL.md` current.
- [ ] `docker compose -f docker/compose.yml up --build` works from a clean checkout
      (`tests/e2e/test_clean_checkout.py` passes).
- [ ] Byte-exact extraction asserted in the chain test.
- [ ] Malicious fixture scores `malicious`; benign scores `benign`.
- [ ] Performance baselines recorded/refreshed in `docs/PERFORMANCE.md`.
- [ ] Docs synced: README, ARCHITECTURE, DEVELOPMENT, OPERATIONS reflect what shipped.
- [ ] `uv.lock` committed; `.python-version` = 3.10.
