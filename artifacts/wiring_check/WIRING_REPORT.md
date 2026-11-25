# Frontend, API, and backend wiring verification

The inventory covered 34 registered routes used by the application. Ten direct HTTP probes checked readiness, JSON error handling, protected routes, separate FC26 and FC27 reads, V3.2.1 recommendation output, and FC27 research refusal in production mode. Tests used separate clones of the local PostgreSQL fixture databases. The direct FastAPI-served build and Vite preview both passed the FC27 availability browser journey.

## Fixes verified

- Decorative player artwork no longer intercepts the player detail link.
- Squad Lab lock controls use a native checkbox with a pointer target aligned to its visible box.
- Preferred PlayStyle suggestions stay in the form flow so the recommendation button remains reachable.
- Turning off the shared research opt-in removes the active Squad Lab editor, cached shortlist and results.
- The recommendation service checks current deployment settings at request time. An explicit test override only applies within a local deployment. Production still rejects research reads.
- The extended Squad Lab browser script now checks the actual results panel for stale responses and uses the current control labels.

## Verification

| Check | Result |
| --- | --- |
| Frontend TypeScript and production build | Passed |
| Frontend tests with live local API | 95 passed |
| Full PostgreSQL-backed backend suite | 823 passed, 24 failed, 10 skipped |
| Focused release, version and API backend tests | 20 passed |
| Stadium browser journey | 7 checks passed |
| FC27 availability browser journey | 5 checks passed |
| FC27 card, squad and profile browser journey | 9 checks passed |
| Performance Evidence Lab browser journey | 2 checks passed |
| FC27 availability through Vite preview proxy | 5 checks passed |

The initial full backend run reported 77 failures. The final 24 remaining tests cover nine historical V2 behavior expectations, eleven historical integration expectations and four V3 scoring calibration targets. Their exact test IDs are in the verification JSON. The existing scoring thresholds, golden fixtures and research access policy were kept. The local FC27 release is confirmed on PostgreSQL. Public release approval and verified card goalkeeper references remain unavailable.

Vite development hot reload could not be certified here. The normal Windows environment blocked esbuild resolution at the workspace path, and a shortened-drive attempt repeatedly restarted on file-watch events. The production build and Vite preview exercised the running backend successfully.
