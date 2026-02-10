# Backend cPanel Deployment Notes

This backend is served via cPanel Python App + Passenger using `passenger_wsgi.py`.

## Required cPanel settings

- Application root: backend project directory (contains `main.py` and `passenger_wsgi.py`)
- Application URL: `api.gastronomi.id` (or mapped subpath)
- Startup file: `passenger_wsgi.py`
- Entry point: `application`

## Required server files

- `passenger_wsgi.py` wraps FastAPI ASGI app with `a2wsgi.ASGIMiddleware`
- `.htaccess` routes non-file requests to Passenger so dynamic endpoints (for example `/health`) are handled by FastAPI

## Deploy/update flow

1. Pull latest commit on server in application root.
2. Install dependencies in cPanel virtualenv:
   - `pip install -r requirements.txt`
3. Ensure `.env` is present with valid DB credentials and CORS origins.
4. Restart app from cPanel Python App panel.
5. Verify endpoints:
   - `GET /`
   - `GET /health`
   - `GET /healthz`

## If `/health` returns hosting 404 page

- Confirm domain/subdomain points to the same cPanel application URL.
- Remove/rename conflicting `index.php` or `index.html` from the served document root.
- Confirm `.htaccess` is present and loaded in application root.
- Restart the Python application.
