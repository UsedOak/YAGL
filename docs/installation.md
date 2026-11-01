# Installation and maintenance

## Prerequisites

Docker Engine and the Compose plugin. Any Linux server capable of building a Python-based image should work; other platforms with Docker Compose are expected but not comprehensively tested in this release candidate.

## Standard install

```bash
git clone https://github.com/YOUR-USERNAME/yagl.git
cd yagl
cp .env.example .env
docker compose up -d --build
docker compose ps
```

Visit `http://SERVER-IP:8080`. Docker downloads the Python base image and Python packages during the first build. No account, SMTP service, or external database is required. Startup creates SQLite tables and starter categories automatically.

Configure `YAGL_PORT` in `.env` if host port 8080 is occupied. The database is stored in the Compose named volume `yagl_data` mounted as `/data` in the container. The application itself is read-only with a writable data volume and temporary directory.

## HTTPS and reverse proxy

Point an HTTPS reverse proxy at `http://SERVER-IP:8080`; WebSocket upgrade support for `/api/live` is important. This is one container and one upstream. If the app reports `Reconnecting`, confirm the proxy is passing the WebSocket handshake and that it permits sufficiently long connections. The UI also refreshes its snapshot periodically when visible.

To use a host-local reverse proxy, set `YAGL_BIND=127.0.0.1` in `.env`. If you use a remote reverse proxy, ensure its host can reach the mapped server address. For Cloudflare Tunnel, configure an HTTP upstream to the host/container as appropriate. Do not set a separate frontend API domain.

## Back up all YAGL data

```bash
docker compose exec yagl python -m backend.backup /tmp/yagl-backup.sqlite3
docker compose cp yagl:/tmp/yagl-backup.sqlite3 ./yagl-backup.sqlite3
```

This uses SQLite's backup API to capture a consistent database, including checkmarks, all stores, aisle mappings, and category memory. Protect your downloaded backups like other household data. The export button inside YAGL backs up only one store's layout, not the entire database.

## Restore a full database backup

**Stop the app and back up the existing database before overwriting anything.** From the repository folder, place `yagl-backup.sqlite3` in that folder, then:

```bash
docker compose stop yagl
docker compose run --rm -v "$PWD/yagl-backup.sqlite3:/restore/yagl.sqlite3:ro" yagl \
  python -c 'import sqlite3; s=sqlite3.connect("file:/restore/yagl.sqlite3?mode=ro",uri=True); t=sqlite3.connect("/data/yagl.sqlite3"); s.backup(t); t.close(); s.close()'
docker compose up -d
```

The temporary restore container has the same named data volume. This process requires the restored SQLite file to be a compatible YAGL version. If using Windows PowerShell, adapt the `"$PWD/..."` bind-mount syntax.

## Update or uninstall

```bash
git pull
docker compose up -d --build
```

The data volume is retained across updates and `docker compose down` without `-v`. **Never run `docker compose down -v` unless you are deliberately deleting all YAGL data.**

To uninstall without deleting your data, run `docker compose down`. To remove the data permanently, explicitly delete the named volume only after confirming backups and understanding that the operation is destructive.

## Troubleshooting

- **Empty page/connection refused:** run `docker compose ps` and `docker compose logs yagl`; check that the host port is free and inbound access is allowed.
- **Live updates not arriving:** verify WebSocket forwarding for `/api/live`; refresh or focus the window to fetch a new copy of the list.
- **List resets after restart:** make sure you're reusing the same Compose project/volume and not deleting it with `down -v`.
- **No aisle sorting:** select a store, create aisles, and map a category or a product. Unmapped items stay visible and grouped at the end.
- **Port conflict:** change `YAGL_PORT` in `.env` and rerun `docker compose up -d`.
- **Permission problem on `/data`:** the container runs as UID 10001 and the Dockerfile creates `/data` for that UID. Named volumes are recommended; custom bind mounts must be writable by UID 10001.
