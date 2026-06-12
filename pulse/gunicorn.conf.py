# -----------------------------------------------------------------------------
# sparQ - Gunicorn Configuration (Production)
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import json
import time

# Server socket
bind = "0.0.0.0:8000"

# Worker processes
# Single worker required: Flask-SocketIO with async_mode="threading" keeps
# connection state in-process memory — multiple workers break SocketIO because
# Caddy round-robins requests across workers, so a client's SocketIO session
# lands on a different worker each poll and broadcasts only reach one worker.
# 64 threads matches previous capacity (4 workers × 16 threads) and provides
# headroom for concurrent SocketIO long-poll connections across all workspaces.
workers = 1
threads = 64
timeout = 120

# Logging
accesslog = None
errorlog = "-"
loglevel = "info"


def post_request(worker, req, environ, resp):
    """Called after each request - structured access logging."""
    # Skip noisy polling requests
    path = environ.get("PATH_INFO", "")
    if "/sysadmin/console/logs" in path or "/chat/unread-count" in path:
        return

    status = resp.status.split(None, 1)[0] if resp and getattr(resp, "status", None) else "-"
    log_entry = {
        "event": "request",
        "logger_name": "gunicorn.access",
        "level": "info",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
        "method": req.method,
        "path": path,
        "status": int(status) if status != "-" else 0,
        "remote_addr": environ.get("REMOTE_ADDR", "-"),
    }
    print(json.dumps(log_entry))
