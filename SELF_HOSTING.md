# Self-Hosting sparQ

A step-by-step guide to running your own sparQ instance on a server, with HTTPS,
on your own domain. No prior DevOps experience required. If you can copy and
paste into a terminal, you can do this.

The whole thing takes about 15 minutes.

---

## What you'll need

- **A server:** any Linux box with a public IP. A $12/month cloud VM
  (DigitalOcean, Hetzner, Linode, AWS Lightsail…) with **2 GB RAM** is plenty.
  sparQ runs on SQLite by default, so there's no separate database to manage.
- **A domain** (e.g. `<your-domain>`) that you can point at the server.
- **5 minutes of comfort with a terminal.** Every command below is copy-paste.

This guide uses Ubuntu 22.04+ and Docker. The example domain is
`<your-domain>`. Replace it with yours everywhere it appears.

---

## Step 1: Install Docker

Install Docker (which includes the Compose plugin) by following Docker's
official guide for your OS:
[docs.docker.com/engine/install](https://docs.docker.com/engine/install/). Once
it's installed, SSH into your server and verify:

```bash
docker --version && docker compose version
```

---

## Step 2: Download sparQ

`/opt` is the conventional home for self-hosted apps, so we'll put it there:

```bash
cd /opt
git clone https://github.com/gosparq/sparq.git
cd sparq
```

Run all the `docker compose` commands in this guide from this directory
(`/opt/sparq`). If you're not logged in as root, prefix the clone with `sudo`.

> **Tip:** pin to a released version instead of the latest commit, so updates
> are deliberate: `git checkout v1.0.0`

---

## Step 3: Configure

sparQ reads its configuration from `pulse/.env`. Create it from the example:

```bash
cp pulse/.env.example pulse/.env
```

The app will actually start even if you change nothing: on first run it
auto-generates a `SECRET_KEY` (the value used to sign login sessions). The catch
is that the auto-generated key isn't durable. It gets regenerated whenever the
container is rebuilt (for example during an update), which silently logs every
user out. So set a permanent one now:

```bash
# write a strong, stable SECRET_KEY into pulse/.env
SECRET=$(openssl rand -hex 32)
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET/" pulse/.env
```

Because this key lives in `pulse/.env`, which Compose loads on every start, it
now survives rebuilds and your users stay logged in across updates.

Everything else in the file is **optional** and has sensible defaults (in
production, secure HTTPS-only session cookies are enabled automatically). See
[Optional features](#optional-features) below for email, AI, and GitHub setup.
You can always add those later.

---

## Step 4: Start sparQ

First, keep the app off the public internet so it's only reachable through the
HTTPS proxy you'll add in Step 6. Edit `docker-compose.yml` and change the port
line so it binds to localhost only:

```yaml
    ports:
      - "127.0.0.1:8000:8000"   # was "8000:8000"
```

Then start it:

```bash
docker compose up -d
```

The first run builds the image (a few minutes). When it finishes, sparQ is
running on port 8000. Check it:

```bash
curl http://localhost:8000/health
```

You should get a healthy response. sparQ is now running, but only reachable on
the server itself. Next we put it on your domain with HTTPS.

---

## Step 5: Point your domain at the server

In your domain registrar / DNS provider, create an **A record**:

| Type | Name | Value |
|------|------|-------|
| A    | the host part of `<your-domain>` (e.g. `app`, or `@` for a root domain) | your server's public IP |

Wait a minute or two, then confirm it resolves:

```bash
dig +short <your-domain>      # should print your server's IP
```

DNS must be pointing at the server **before** the next step, because the HTTPS
certificate is issued by verifying you control the domain.

---

## Step 6: Add HTTPS with Caddy

[Caddy](https://caddyserver.com) is a web server that gets and renews HTTPS
certificates **automatically**, with no manual certificate management, ever.

**Install it** by following Caddy's official guide for your OS:
[caddyserver.com/docs/install](https://caddyserver.com/docs/install). Once it's
installed, confirm the service is running:

```bash
systemctl status caddy --no-pager | head -3
```

**Configure it.** Replace the contents of `/etc/caddy/Caddyfile`
(`sudo nano /etc/caddy/Caddyfile`) with:

```
<your-domain> {
    encode gzip
    reverse_proxy localhost:8000
}
```

That's the whole config. No certificate lines needed, because Caddy handles TLS
for you.

**Open the firewall and reload:**

```bash
sudo ufw allow 80,443/tcp           # 80 is required for certificate issuance, not just 443
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Open **https://<your-domain>** in your browser. You're live, with a valid
HTTPS certificate.

---

## Step 7: Create your admin account

Open **https://<your-domain>** in your browser. On a brand-new instance you'll
be sent to a one-time setup wizard at `/setup`, which creates your first admin
account, organization, and workspace. Fill it in and you're in.

(The wizard only runs while the instance has no users. After that, `/setup` is
closed and everyone signs in normally.)

To manage organizations, workspaces, and users at the server level later on,
enable the built-in admin console: set `MSA_USER` and `MSA_PASS` in `pulse/.env`,
run `docker compose up -d` again, and visit `/msa`.

---

## Optional features

All optional. Add any of these to `pulse/.env`, then re-run
`docker compose up -d` to apply.

| Feature | What to set | Notes |
|---------|-------------|-------|
| **Email** | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` | Without it, signups are created instantly (no email verification). |
| **AI assistant** | `LLM_PROVIDER` + `OPENAI_API_KEY` *or* `ANTHROPIC_API_KEY` | Enables sparQy AI features. Disabled if no key. |
| **GitHub sync** | `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET`, `GITHUB_WEBHOOK_BASE_URL=https://<your-domain>` | Connects PRs/issues/commits. Set the base URL so webhooks resolve. |
| **Push notifications** | `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIMS_EMAIL` | Generate keys: `pip install py-vapid && vapid --gen` |

Email, AI, and other providers can also be configured from the `/msa` admin
panel instead of the `.env` file.

---

## Backups

All your data (the SQLite database **and** uploaded files) lives in one place:
the `/data` directory inside the container, which is the `sparq-data` Docker
volume. To back it up, copy that directory to the host:

```bash
docker compose cp sparq:/data ./sparq-backup-$(date +%F)
```

That gives you a dated folder with everything in it. Copy it somewhere safe
(another machine, object storage) on a schedule. For example, a nightly cron job
that runs the command above and `scp`s the folder off the server.

To restore a backup:

```bash
docker compose stop sparq
docker compose cp ./sparq-backup-2026-06-17/. sparq:/data
docker compose start sparq
```

> Because the database is a single SQLite file, copying `/data` while the app is
> running is fine for routine backups. For a guaranteed-consistent snapshot,
> `docker compose stop sparq` first, copy, then `start` again.

---

## Updating sparQ

```bash
cd /opt/sparq
git fetch --tags
git checkout v1.1.0              # the version you want to move to
docker compose up -d --build
```

Your data is safe across updates because it lives in the `sparq-data` volume,
not in the container. **Always take a backup before updating** (see above).

---

## Troubleshooting

**The site won't load / no HTTPS certificate.**
Caddy can only get a certificate once DNS points at your server and ports 80 and
443 are open. Check:
```bash
dig +short <your-domain>     # must show your server IP
sudo journalctl -u caddy -n 50   # Caddy's logs explain cert failures
```

**Is sparQ itself running?**
```bash
docker compose ps                # the sparq service should be "running"
docker compose logs -f sparq     # live application logs
curl http://localhost:8000/health
```

**I changed `.env` but nothing happened.**
Re-apply it: `docker compose up -d` (recreates the container with the new
environment).

**Port 8000 already in use.**
Something else is on that port. Either stop it, or change the published port in
`docker-compose.yml` (e.g. `"127.0.0.1:8080:8000"`) and point Caddy's
`reverse_proxy` at the new port.

---

## Need help?

- **Issues & questions:** [github.com/gosparq/sparq/issues](https://github.com/gosparq/sparq/issues)
- **Security reports:** see [SECURITY.md](SECURITY.md)

sparQ is AGPL-3.0 and self-hosting is free, forever.
