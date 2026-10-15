# Sabrina English Mac mini SQLite Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unavailable Supabase sync with an authenticated SQLite-backed service on the Mac mini while preserving the existing local-first learning experience at `https://sabrina.redflyingpig.com/`.

**Architecture:** A Python standard-library HTTP service binds only to `127.0.0.1:18880`, serves the existing frontend, and exposes same-origin JSON endpoints backed by SQLite. The frontend writes to `localStorage` first, synchronizes authenticated profile state through the API, and retains offline/import/export behavior; `launchd` and the existing Cloudflare Tunnel keep it reachable.

**Tech Stack:** Python 3.9+ standard library (`http.server`, `sqlite3`, `hashlib`, `secrets`, `unittest`), vanilla HTML/CSS/JavaScript, macOS `launchd`, Cloudflare Tunnel.

**Spec:** `docs/superpowers/specs/2026-10-15-mac-mini-sqlite-sync-design.md`

## Global Constraints

- Use no third-party runtime or test dependency and no Docker, PostgreSQL, or Supabase.
- Bind the application only to `127.0.0.1:18880`; never expose SQLite or a database port.
- Runtime data lives outside Git under `~/Library/Application Support/SabrinaEnglish/` with owner-only permissions.
- Public registration is disabled; only locally provisioned `Owner`, `Sabrina`, and `Max` profiles may log in.
- PIN length is 6–64 characters; store only per-profile scrypt hashes and random salts.
- Session tokens are random, stored client-side, hashed server-side, and expire after 90 days.
- Dynamic API responses use `Cache-Control: no-store`; request bodies are capped at 1 MiB.
- Preserve current lessons, speech, streak, review, favorites, JSON import/export, and offline local storage.
- Backups are consistent SQLite backups, run daily, and retain the newest 30 files.

## Review Focus

- Two devices save the same profile from the same version: reject the stale write with `409`, return current state, merge, and retry without data loss.
- A valid token for one profile attempts to read or write another profile: API derives identity only from the token and never accepts a profile ID from the client.
- Malformed, oversized, or non-object JSON reaches an API endpoint: reject it without changing the database or exhausting memory.
- The service or network disappears after a learning action: local state remains usable and is synchronized after connectivity returns.
- A hostile Origin or repeated wrong PINs target login/write endpoints: reject cross-origin writes and rate-limit failures without locking out unrelated profiles.

---

### Task 1: SQLite profile and session store

**Files:**
- Create: `sabrina_backend/__init__.py`
- Create: `sabrina_backend/store.py`
- Create: `tests/test_store.py`

**Interfaces:**
- Consumes: Python standard-library `sqlite3`, `hashlib`, `secrets`, `json`, and UTC timestamps.
- Produces: `Store(db_path)`, `Store.initialize()`, `Store.create_profile(display_name, pin)`, `Store.authenticate(username, pin)`, `Store.create_session(profile_id)`, `Store.resolve_session(token)`, `Store.delete_session(token)`, `Store.read_state(profile_id)`, `Store.write_state(profile_id, expected_version, state)`, and `VersionConflict`.

- [ ] **Step 1: Write failing store tests**

Add tests named `test_initializes_secure_schema`, `test_profile_names_are_case_and_space_insensitive`, `test_pin_is_hashed_and_wrong_pin_fails`, `test_session_is_hashed_scoped_and_expires`, `test_state_version_conflict_returns_current_state`, and `test_three_profiles_are_isolated`. Assert WAL/foreign keys, no plaintext PIN/token, 90-day expiry, version increments, `VersionConflict.current`, and independent Owner/Sabrina/Max state.

- [ ] **Step 2: Run the store tests and verify failure**

Run: `python3 -m unittest -v tests.test_store`
Expected: FAIL because `sabrina_backend.store` does not exist.

- [ ] **Step 3: Implement the store interfaces**

Implement schema versioning and parameterized SQL in `sabrina_backend/store.py`. Normalize usernames with trimmed/collapsed spaces plus `casefold()`, use `hashlib.scrypt(n=16384, r=8, p=1)`, hash session tokens with SHA-256, enable WAL/foreign keys/busy timeout, and make state writes transactional compare-and-swap operations.

- [ ] **Step 4: Run store tests**

Run: `python3 -m unittest -v tests.test_store`
Expected: all store tests PASS.

- [ ] **Step 5: Commit the store**

```bash
git add sabrina_backend/__init__.py sabrina_backend/store.py tests/test_store.py
git commit -m "feat: add SQLite profile store"
```

### Task 2: Authenticated HTTP and static-file service

**Files:**
- Create: `sabrina_backend/app.py`
- Create: `tests/test_app.py`

**Interfaces:**
- Consumes: Task 1 `Store` interfaces and repository `index.html`.
- Produces: `create_server(host, port, root_dir, data_dir) -> ThreadingHTTPServer`, `SabrinaHandler`, and endpoints `GET /api/health`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/profile`, `PUT /api/profile`.

- [ ] **Step 1: Write failing HTTP integration tests**

Start an ephemeral test server and add tests named `test_serves_index_and_health`, `test_login_profile_round_trip_and_logout`, `test_token_cannot_select_another_profile`, `test_stale_write_returns_409_with_current_state`, `test_rejects_bad_and_oversized_json`, `test_rejects_hostile_origin`, `test_failed_logins_are_rate_limited_per_ip_and_username`, `test_api_security_headers_disable_caching`, and `test_application_logs_rotate`.

- [ ] **Step 2: Run HTTP tests and verify failure**

Run: `python3 -m unittest -v tests.test_app`
Expected: FAIL because `sabrina_backend.app` does not exist.

- [ ] **Step 3: Implement HTTP parsing, routing, and security**

Implement the exact endpoints with JSON error objects `{ "error": "stable_code", "message": "human text" }`. Derive profile identity only from the Bearer token; enforce 1 MiB before reading the body; accept same-origin writes from the configured public origin and local test origin; add `Content-Security-Policy`, `X-Content-Type-Options`, `Referrer-Policy`, and `Cache-Control` headers; serve only files resolved beneath `root_dir`; use `RotatingFileHandler` with bounded size and backup count under the data directory.

- [ ] **Step 4: Run HTTP and store tests**

Run: `python3 -m unittest -v tests.test_app tests.test_store`
Expected: all tests PASS.

- [ ] **Step 5: Commit the application server**

```bash
git add sabrina_backend/app.py tests/test_app.py
git commit -m "feat: serve authenticated study API"
```

### Task 3: Local profile administration and database backup

**Files:**
- Create: `sabrina_backend/admin.py`
- Create: `sabrina_backend/backup.py`
- Create: `tests/test_admin_backup.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Task 1 `Store`; local terminal access to the Mac mini.
- Produces: `python3 -m sabrina_backend.admin init-profiles`, `python3 -m sabrina_backend.admin reset-pin USERNAME`, `python3 -m sabrina_backend.admin list-profiles`, and `python3 -m sabrina_backend.backup --data-dir PATH --keep 30`.

- [ ] **Step 1: Write failing CLI and backup tests**

Add tests named `test_init_creates_exactly_three_profiles_and_prints_pins_once`, `test_init_is_idempotent`, `test_reset_pin_invalidates_existing_sessions`, `test_list_never_prints_secrets_or_state`, `test_backup_is_consistent_and_restorable`, and `test_backup_retains_newest_thirty`.

- [ ] **Step 2: Run tests and verify failure**

Run: `python3 -m unittest -v tests.test_admin_backup`
Expected: FAIL because the admin and backup modules do not exist.

- [ ] **Step 3: Implement local administration**

Implement argparse commands using `SABRINA_DATA_DIR` or the documented Application Support default. `init-profiles` creates only Owner, Sabrina, and Max with cryptographically random initial PINs; `reset-pin` accepts a terminal prompt or generated value and deletes that profile's sessions; `list-profiles` prints display names and timestamps only.

- [ ] **Step 4: Implement backup and retention**

Use `sqlite3.Connection.backup()` to a timestamped temporary file, atomically rename it after success, validate it with `PRAGMA integrity_check`, and delete only backups beyond the newest 30. Add runtime database, backup, token, and temporary-file patterns to `.gitignore`.

- [ ] **Step 5: Run all backend tests**

Run: `python3 -m unittest discover -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit administration and backup**

```bash
git add .gitignore sabrina_backend/admin.py sabrina_backend/backup.py tests/test_admin_backup.py
git commit -m "feat: add profile admin and backups"
```

### Task 4: Replace Supabase UI and synchronization

**Files:**
- Modify: `index.html`
- Create: `tests/test_frontend_contract.py`

**Interfaces:**
- Consumes: Task 2 HTTP endpoints and the existing `mergeProfileStates`, `getProfileState`, `applyProfileState`, import/export, and rendering functions.
- Produces: login/profile UI; `apiRequest(path, options)`, `loginProfile(username, pin)`, `logoutProfile()`, `loadProfileFromServer()`, `saveProfileToServer()`, online/focus retry hooks, and local-first conflict recovery.

- [ ] **Step 1: Write failing frontend contract tests**

Add tests named `test_supabase_credentials_and_rpc_are_removed`, `test_login_form_has_owner_sabrina_max_and_pin`, `test_frontend_uses_same_origin_api_and_bearer_token`, `test_local_write_precedes_sync`, `test_409_merges_and_retries_once`, `test_offline_and_expired_session_keep_local_data`, and `test_existing_learning_features_remain_present`. Inspect the HTML/JavaScript text and assert the required UI IDs, endpoint strings, call ordering markers, and legacy feature controls.

- [ ] **Step 2: Run contract tests and verify failure**

Run: `python3 -m unittest -v tests.test_frontend_contract`
Expected: FAIL because Supabase code remains and PIN login is absent.

- [ ] **Step 3: Implement profile login and session handling**

Replace the username creation dialog with Owner/Sabrina/Max selection plus a 6–64-character PIN input. Store the returned token under `sabrinaEnglish:session`, provide explicit logout/switch-user behavior, and never include the PIN in URLs or persistent storage.

- [ ] **Step 4: Replace Supabase RPC synchronization**

Remove the Supabase URL/key/RPC layer. Preserve local-first writes; load and save through `/api/profile`; include `state_version`; on `409` merge the returned current state with local state and retry exactly once; retry on `online` and `visibilitychange`; preserve local data on network failure, `401`, or logout.

- [ ] **Step 5: Run frontend contracts and complete test suite**

Run: `python3 -m unittest discover -v`
Expected: all tests PASS.

- [ ] **Step 6: Perform local browser smoke test**

Run the server against a temporary data directory, initialize the three profiles, then verify at desktop and mobile viewport sizes: login, lesson rendering, speech button availability, mark learned, favorite, review, export/import, logout, offline message, and relogin persistence.

- [ ] **Step 7: Commit the frontend migration**

```bash
git add index.html tests/test_frontend_contract.py
git commit -m "feat: sync study profiles with Mac mini"
```

### Task 5: macOS deployment and operational documentation

**Files:**
- Create: `deploy/ai.sabrina-english.site.plist.template`
- Create: `deploy/ai.sabrina-english.backup.plist.template`
- Create: `deploy/install.sh`
- Create: `deploy/uninstall.sh`
- Create: `tests/test_deploy_contract.py`
- Create: `OPERATIONS.md`
- Modify: `SUPABASE-SETUP.md`

**Interfaces:**
- Consumes: Task 2 server entry point and Task 3 backup command; existing port `18880`, project path, LaunchAgent label, and Cloudflare hostname.
- Produces: idempotent install/uninstall scripts, application and daily-backup LaunchAgents, health-check commands, backup/restore runbook, and retirement notice for Supabase.

- [ ] **Step 1: Write failing deployment contract tests**

Add tests named `test_service_binds_loopback_on_18880`, `test_launchagents_use_absolute_paths_and_keepalive`, `test_backup_runs_daily_and_keeps_thirty`, `test_install_is_idempotent_and_preserves_database`, `test_uninstall_does_not_delete_data`, and `test_operations_cover_health_backup_restore_and_tunnel`.

- [ ] **Step 2: Run deployment tests and verify failure**

Run: `python3 -m unittest -v tests.test_deploy_contract`
Expected: FAIL because deployment artifacts do not exist.

- [ ] **Step 3: Implement deployment artifacts**

Make `deploy/install.sh` render absolute project/data paths into the two plist templates, create owner-only data directories, bootstrap the database without overwriting profiles, load/restart both LaunchAgents, and check `/api/health`. Make uninstall unload agents and remove only installed plist files, never the database or backups.

- [ ] **Step 4: Write operations and migration documentation**

Document install, three-profile initialization, PIN reset, logs, health checks, Cloudflare route verification, backup, restore, upgrade, rollback, and uninstall in `OPERATIONS.md`. Replace `SUPABASE-SETUP.md` with a short historical notice pointing to the new runbook; do not leave live Supabase credentials or deployment commands.

- [ ] **Step 5: Run complete automated verification**

Run: `python3 -m unittest discover -v && git diff --check`
Expected: all tests PASS and no whitespace errors.

- [ ] **Step 6: Commit deployment support**

```bash
git add deploy tests/test_deploy_contract.py OPERATIONS.md SUPABASE-SETUP.md
git commit -m "ops: deploy Sabrina service on Mac mini"
```

### Task 6: Deploy, migrate, and verify the live service

**Files:**
- Modify outside repository: `~/Library/LaunchAgents/ai.sabrina-english.site.plist`
- Create outside repository: `~/Library/LaunchAgents/ai.sabrina-english.backup.plist`
- Create outside repository: `~/Library/Application Support/SabrinaEnglish/sabrina.db`

**Interfaces:**
- Consumes: Tasks 1–5 and existing Cloudflare Tunnel route `sabrina.redflyingpig.com -> http://127.0.0.1:18880`.
- Produces: running Mac mini service, three initialized profiles, verified backups, and evidence for every acceptance item in the spec.

- [ ] **Step 1: Capture pre-deployment state and backup**

Record current Git revision, service plist, Tunnel route, local HTTP response, and public response. Export or preserve any recoverable browser data before replacing the service; do not delete old Supabase migrations in this deployment.

- [ ] **Step 2: Install and initialize**

Run `deploy/install.sh`, execute `python3 -m sabrina_backend.admin init-profiles`, securely present the three one-time PINs to the user, and immediately run the backup command once.

- [ ] **Step 3: Verify local runtime**

Run the full test suite, `curl` the loopback health endpoint, inspect LaunchAgent status/logs, confirm only `127.0.0.1:18880` is listening, validate database permissions, run `PRAGMA integrity_check`, and restore the first backup into a temporary database.

- [ ] **Step 4: Verify public desktop and mobile flows**

Open `https://sabrina.redflyingpig.com/` at desktop and mobile viewport sizes. For Owner, Sabrina, and Max, verify login and isolated state. On two browser contexts using the same profile, verify learned/favorite/streak changes synchronize and a stale concurrent update merges without data loss.

- [ ] **Step 5: Verify failure recovery**

Stop the application service, perform a learning action in an already loaded browser, confirm local retention and offline status, restart the service, confirm automatic synchronization, then restart the LaunchAgent once more and confirm existing database state remains.

- [ ] **Step 6: Final completion audit and commit any operational fixes**

Re-run `python3 -m unittest discover -v`, `git diff --check`, local health, public health, profile isolation, cross-device sync, backup integrity, and LaunchAgent/Tunnel status. Commit only fixes required by observed deployment behavior; leave secrets and runtime data untracked.
