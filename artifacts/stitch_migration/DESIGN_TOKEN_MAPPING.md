# Stadium Intelligence design system

| Role | Canonical value |
|---|---|
| Canvas | `#080D16` |
| Primary, raised and hover surfaces | `#111B29`, `#192535`, `#223249` |
| Borders | `#2A3A4C` |
| Primary, secondary and tertiary text | `#F4F7FB`, `#A8BBCC`, `#8FA4B9` |
| Actions and analytic focus | `#B8F57A`, `#52C9E8` |
| Caution, evidence, positive and negative | `#E8B66D`, `#B1A5FF`, `#83DCA2`, `#F37E88` |

`frontend/src/stadium.css` defines the values. Existing primitives reference the same variables. Names for Space Grotesk, Inter and IBM Plex Mono are preferred in the stacks. This source export has no local font binaries, so the build uses system fallbacks where the named fonts are absent. CSS pitch graphics and typographic card monograms require no portrait, web font or other runtime image request.
