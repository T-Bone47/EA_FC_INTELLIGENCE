# STADIUM 3.0 — NAVIGATION, COMMAND CENTER & AUTH REVIEW
**EA FC Intelligence — Football Intelligence Operating System**
*Revision: 3.0.0 | Modules: Dashboard.tsx, Compare.tsx, Nav.tsx, Profile.tsx*

---

## 1. Executive Summary

Stadium 3.0 unifies the entire application navigation and entry experience into a coherent football intelligence command center. The navigation combines an always-accessible responsive sidebar with keyboard shortcuts (`/` or `Cmd+K` to search, `Tab` for skip-to-content), an active game version toggle (FC26 vs FC27), and an asymmetric Bento Command Center hero.

---

## 2. Component Specifications

### 2.1 The Asymmetric Bento Command Center (`Dashboard.tsx`)
- **Dominant Tactical Hero:** Features the headline *"Build a smarter squad. Play your football."*, calibrated V3.2 badges, and a live 4-3-3 tactical cockpit mini-pitch.
- **Direct Action Triggers:**
  - `Find my best fit` (launches Intelligence Studio).
  - `Open Squad Lab` (opens 11-player formation builder).
  - `Browse Catalogue` (opens player scouting directory).
- **Quick-Launch Archetype Tray:** Instant shortcuts for 5 verified tactical setups (Direct Attacking, High Pressing, Possession Buildup, Wing Play, Low Block Counter).
- **Primary Workflows Bento Pipeline:** 4 modules with iconography and micro-KPI badges:
  1. *01 Discover Players (Scouting)*
  2. *02 Tactical Intelligence (V3.2 Engine)*
  3. *03 Optimize My Squad (Squad Lab)*
  4. *04 Compare Card Versions (Head-to-Head)*
- **Tactical Telemetry & History:** Displays recently cached manager analyses with 1-click restore.

### 2.2 Global Stadium Navigation (`Nav.tsx`)
- **Accessibility & Focus:** Includes immediate `#main` skip link with high-contrast lime background when focused.
- **Seven Core Destinations:** Overview (`⌂`), Discover (`⌕`), Intelligence (`◇`), Squad Lab (`▦`), Compare (`⇄`), Evidence Lab (`◫`), Profile (`◎`).
- **Mobile Menu Overlay:** Responsive drawer activated via `button: Menu`, automatically focusing the first navigation link and closing upon `Escape` or backdrop click.
- **Global Search Shortcut:** Listens for `/` or `Ctrl/Cmd + K` to immediately focus the header search input.

### 2.3 Head-to-Head Comparison Lab (`Compare.tsx`)
- **Dual Tab Architecture:** Players vs Card Versions.
- **Card Version Research:** Dedicated route `/compare?scope=cards` with research dataset opt-in and item ID search.
- **Synchronized Visualizations:** Radar polygon charts, attribute delta differences, and explicit "Why the higher item leads" analytical summaries.

### 2.4 Football Manager Identity & Auth (`Profile.tsx`, `Login.tsx`, `Signup.tsx`)
- **Manager Persona:** Tactical preferences storage, favourite formation and tactical profile saving.
- **Saved Squads & Shortlists:** Secure management of custom squad scenarios and bookmarked cards.
- **Honest Session Persistence:** JWT-backed authentication with session revocation and automatic cleanup.
