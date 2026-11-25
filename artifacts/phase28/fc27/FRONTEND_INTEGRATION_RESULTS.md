# Frontend integration results

TypeScript and production build passed. Vitest passed 93 tests including three real HTTP comparisons of recommendation rendering, explanation output and tactical what-if rows with PostgreSQL-backed results. The grouped tactical compatibility test verifies that variants retain the submitted position, formation and division.

The Chromium harness completed 15 suites and 51 checks. Desktop, tablet and mobile user paths passed. All three axe scans reported zero violations. The harness exercised visible keyboard focus, touch selections, no-data handling, failures and the FC27 research comparison and what-if loop.

A separate in-app-browser run exercised a local account and research squad, assigned a real FC27 player, requested replacements for the exact CDM slot and applied an improved choice. Keyboard navigation and 390 px width were verified on the squad page. Final integration tests exercised the squad and feedback endpoints over the application contract.

Browser coverage applies to the named journeys. The public Ultimate Team path remains data-gated. The card fixture proves engineering behavior through the release-scoped HTTP API.
