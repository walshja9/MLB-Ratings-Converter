# Plan 004: Bind Flask to localhost by default; make LAN exposure opt-in

> **Executor instructions**: Follow step by step, verify each step, honor STOP
> conditions, update the plan 004 row in `plans/README.md`. Do NOT `git commit`/`push`.
>
> **Drift check (run first)**: `git diff --stat bcfbd39..HEAD -- app.py`
> If `app.py`'s `__main__` block differs from the excerpt, STOP.

## Status
- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: security

## Why this matters

The app calls `app.run(... host="0.0.0.0")`, binding to every network interface.
Combined with unauthenticated, state-changing routes (`/pool/save`,
`/pool/<pid>` DELETE, `/prospects/done`), any device on the same network can
write to or delete from the player pool, and can drive the host into outbound
scraping. `debug=False` is already correctly set. For a single-user local tool
the right default is `127.0.0.1`, with LAN exposure available only when the user
explicitly opts in (the "also on your network" convenience). This closes the
exposure without removing the feature.

## Current state

`app.py:643-649`:
```python
if __name__ == "__main__":
    print("\n  MLB The Show 26 - Card Generator")
    print("  http://localhost:5000\n")
    import socket
    local_ip = socket.gethostbyname(socket.gethostname())
    print(f"  Also available on your network: http://{local_ip}:5000\n")
    app.run(debug=False, port=5000, host="0.0.0.0")
```

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Syntax check | `"C:/Users/Alex/Claude Context/Robert Stock - Pitching Grade Model/venv/Scripts/python.exe" -c "import py_compile; py_compile.compile('app.py', doraise=True)"` | exit 0 |
| Suite | `"C:/.../python.exe" -m pytest -q` | all pass |

## Scope

**In scope**: `app.py` (the `__main__` block only).
**Out of scope**: route definitions, adding auth/CSRF (a larger change — note as
follow-up), the templates.

## Steps

### Step 1: Default to localhost, opt in to LAN via env var

Replace the `__main__` block so it binds to `127.0.0.1` unless an explicit
opt-in env var is set. Target shape:
```python
if __name__ == "__main__":
    import os
    import socket
    expose_lan = os.environ.get("MLBSHOW_EXPOSE_LAN", "").lower() in ("1", "true", "yes")
    host = "0.0.0.0" if expose_lan else "127.0.0.1"
    print("\n  MLB The Show 26 - Card Generator")
    print("  http://localhost:5000\n")
    if expose_lan:
        local_ip = socket.gethostbyname(socket.gethostname())
        print(f"  LAN exposure ENABLED: http://{local_ip}:5000")
        print("  (anyone on your network can read/write the player pool)\n")
    app.run(debug=False, port=5000, host=host)
```

**Verify**: `py_compile` passes; `pytest -q` still all pass (no test imports the
`__main__` block, so this should be inert to tests).

### Step 2: Document the opt-in

Add one line to `README.md` (and the repo-root `AGENTS.md` "How to Run" section):
"Defaults to localhost. To reach it from your phone on the same WiFi, set
`MLBSHOW_EXPOSE_LAN=1` before running — this exposes write endpoints to your
whole network."

**Verify**: `grep -n "MLBSHOW_EXPOSE_LAN" README.md AGENTS.md` → matches.

## Test plan

- No automated test (the bind happens only under `__main__`, not exercised by the
  test client). Manual check: run the app with no env var and confirm the startup
  log no longer prints a LAN URL; run with `MLBSHOW_EXPOSE_LAN=1` and confirm it
  does. Record this as a manual verification note — do not add a flaky
  socket-binding test.

## Done criteria

- [ ] `app.py` binds `127.0.0.1` by default and `0.0.0.0` only when `MLBSHOW_EXPOSE_LAN` is truthy.
- [ ] `py_compile` on `app.py` exits 0; `pytest -q` all pass.
- [ ] `git diff --name-only` shows only `app.py`, `README.md`, `AGENTS.md`.
- [ ] `plans/README.md` status row for 004 updated.

## STOP conditions

- `app.py`'s `__main__` block drifted from the excerpt.
- Any existing test fails after the change (it shouldn't — investigate).

## Maintenance notes

- Deferred follow-up (NOT in this plan): add CSRF tokens / a shared-secret to the
  write routes (`/pool/save`, `/pool/<pid>` DELETE, `/prospects/done`) so LAN mode
  is safe to use. Localhost-by-default mitigates the immediate risk; auth is the
  complete fix.
- Reviewer: confirm the default path prints no LAN URL and the env opt-in is the
  only way to get `0.0.0.0`.
