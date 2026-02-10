# Changelog

## 2026-02-10

- Updated `passenger_wsgi.py` to force stable app root context and optional interpreter handoff for cPanel Passenger runtime.
- Added `.htaccess` rewrite rules so dynamic routes are forwarded to Passenger instead of static hosting fallback.
- Added `docs/backend-cpanel-deploy.md` with pull, restart, and verification steps for cPanel deployment.
