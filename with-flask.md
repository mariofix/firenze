# with-flask migration plan

Branch: `with-flask`  
Target: migrate from FastAPI/sqladmin to Flask + Flask-Smorest + Flask-Admin (Tabler working copy at `../flask-admin/`).

## Steps (agreed scope: up to step 7)

1. Branch and dependency baseline
2. Flask app factory and extension bootstrap
3. Flask-Smorest API foundation
4. Auth and authorization migration
5. Flask-Admin migration with Tabler UI
6. AGI endpoint migration (`/agi/*`)
7. Middleware and request-guard parity

## Status so far

- Step 1: **Done**
  - Branch `with-flask` created.
  - Dependencies moved toward Flask stack.
  - Local Flask-Admin Tabler working copy wired from `../flask-admin/`.

- Step 2: **In progress (implemented baseline, pending your final review)**
  - `create_app()` moved to Flask bootstrap pattern.
  - Settings are loaded into Flask config.
  - App-specific Flask config values moved into `firenze/config.py` helper.
  - Logging is configured via `LOGGING_CONFIG`, and `app.logger` uses the configured rotating file handler.
  - CORS and debug toolbar are initialized.
  - Request guards are wired in Flask hooks for allowed hosts and AGI network restrictions.
  - DB engine/session factory are exposed via app extensions.

- Step 3: **Pending**
- Step 4: **Pending**
- Step 5: **Pending**
- Step 6: **Pending**
- Step 7: **Pending**
