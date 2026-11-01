# Security model

**YAGL deliberately ships without accounts or authentication.** Anyone able to access the instance can read, modify, or delete the shared list, configure stores, and import/export layout data. The intended deployment is a trusted household or a reverse-proxy/access-controlled homelab. Do not treat an obscure hostname as authentication. An isolated Docker container reduces exposure but is not a complete security boundary.

## Operational suggestions

- Use HTTPS when publishing on a public domain.
- Use your reverse proxy, VPN, or Cloudflare Access if you need authentication; YAGL does not provide accounts.
- Keep Docker, host, and container dependencies up to date.
- Back up `/data/yagl.sqlite3` using the documented SQLite backup process.
- Never put secrets, passwords, or sensitive personal information into shopping-list entries, since all users of the instance can view them.
- Avoid placing YAGL on a privileged Docker network, mounting `/var/run/docker.sock`, or mounting host paths beyond its database.
- No CORS allowlist is configured for cross-origin API use. Requests are not access-controlled and the app is not hardened against malicious authorized clients. Review deployment exposure accordingly.

## Reporting a vulnerability

Before publication, the repository maintainer should enable GitHub **Private vulnerability reporting** under Security → Advisories. Until that is configured, contact the repository maintainer privately through an established channel rather than publishing proof-of-concept exploits or private instance details in a public issue.

No security support SLA is promised for alpha releases.
