# Phase 32 baseline

- Source export SHA-256 `ae68996058f14d9c41206c879e847c494fb7b18ef085a21e7e9b40c2a0ef1104`. ZIP CRC verified. Ten HTML and PNG pairs plus two design documents.
- The Windows project is a source export without Git metadata. The original frontend source and built assets are backed up in `TOOLING/stitch-reference/pre-migration` beside the project.
- Existing compiled assets were 348,344 bytes of JavaScript and 18,194 bytes of CSS, excluding source maps.
- Windows Vitest baseline was 90 passing and three live tests skipped across 17 files. The separate Phase 31 delivery recorded a Linux PostgreSQL baseline of 797 passing, 24 known failures, six skips and 90 passing subtests. That count comes from the delivered report and represents a different checkout.
- Existing Chromium journeys are `frontend/verification/fc27-local.mjs` and `frontend/verification/fc27-performance.mjs`. They use a loopback release and test database.
- The primary local data sources are the release-gated player catalogue, V3.2 service, hash-pinned FC27 item release and Phase 31 evidence routes.
