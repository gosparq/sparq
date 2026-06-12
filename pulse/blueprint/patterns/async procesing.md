# Async & Background Processing Patterns
### For Single-Workspace Flask Apps with Low Load

---

## Currently Implemented

**Pattern 1 (Fire-and-Forget Threads)** is implemented:

```python
# Usage - submit any function to run in background
from system.background import submit_task

submit_task(my_function, arg1, arg2, kwarg=value)
```

**For async email specifically:**
```python
from system.email import send_email_async

send_email_async(to="user@example.com", subject="Hello", html_body="<p>Hi</p>")
```

Key files:
- `system/background/__init__.py` - ThreadPoolExecutor with Flask app context
- `system/email/service.py` - `send_email_async()` function

Currently used by:
- Quote sending (`/quotes/<id>/send`)
- Invoice sending (`/invoices/<id>/send`)

---

This document describes practical options for doing **async / background work** in a **single-container**, **single-workspace Flask application** (like an internal tool or small SaaS app for a small business).

Assumptions:

- The app runs in **one Docker container**.
- **Very low traffic** (e.g., a handful of users, no heavy concurrency).
- You want the **UI to stay responsive** when doing things like:
  - Sending SMS / email / push notifications
  - Calling external APIs
  - Running scheduled tasks (e.g., “send a reminder a day before an event”)
- You **do not** want to introduce Redis, RabbitMQ, or a full-blown queue system yet.

---

## 1. Why You Need Async / Background Work

Even in a tiny app, certain actions are **slow or unreliable**:

- Sending SMS or email via external APIs
- Hitting third-party APIs (billing, CRMs, etc.)
- Generating reports (PDFs, CSV exports, etc.)
- Scheduled notifications (e.g., reminders before events)
- Periodic housekeeping (cleanup, sync, etc.)

If you do these **inside the HTTP request**:

- Users sit staring at a spinner.
- If the external service is slow or flaky, your request hangs.
- You may block your web server worker and reduce throughput.

So we want patterns where:

1. **HTTP request is fast** (the API responds quickly).
2. **Work is done in the background** (threads, queues, async loop).
3. For low load and small business use, we keep it **simple** and **in-process**.

---

## 2. Overview of Options (Within a Single Container)

For a single-workspace, low-load Flask app, you realistically have **four** in-process options:

1. **Fire-and-forget Threads**  
   Simple, great for one-off async API calls.

2. **In-Memory Task Queue + Worker Thread**  
   A tiny job system baked into your process.

3. **Scheduler Thread for Timed / Recurring Tasks**  
   For “send X at time T” or “every N minutes” logic.

4. **Background `asyncio` Event Loop**  
   For high-concurrency **I/O-bound** work using `async/await`.

These can be **combined**:

- Scheduler thread decides *when*.
- Queue / threads / async loop decide *how* the work runs.

---

## 3. Scenario: Small Business Single-Workspace App

Imagine a single-workspace app for a small company. Typical needs:

1. **Calendar notifications**
   - Events stored in a DB (meetings, tasks, deadlines).
   - Users want an SMS/email **1 day before** the event.
   - If the container is briefly down, it’s okay if the SMS is late, but preferably not lost.

2. **Async API calls after user actions**
   - User clicks “Sync with CRM” or “Send Invoice via SMS”.
   - Call external services without making the user wait.

3. **Housekeeping / maintenance**
   - Clean up old temp files/logs.
   - Mark stale entities as archived.
   - Periodically ping an external API to refresh data.

For such an app:

- Reliability matters, but it’s not catastrophic if a job occasionally runs late.
- Load is tiny, so a full task queue service is overkill.
- A **single-container** solution is acceptable.

---

## 4. Pattern 1 – Fire-and-Forget Threads (Simplest)

### Use Case

- User triggers something that calls an external API:
  - Send SMS
  - Send email
  - Call a webhook
- You just need:
  - Immediate HTTP response
  - Work done in the background shortly after

### How it Works

- The Flask route **submits** work to a **thread pool** (`ThreadPoolExecutor`).
- The thread runs the slow task.
- The HTTP request returns right away.

### Example: Async SMS API call

```python
from flask import Flask, request, jsonify
from concurrent.futures import ThreadPoolExecutor
import requests

app = Flask(__name__)

executor = ThreadPoolExecutor(max_workers=4)

SMS_API_URL = "https://sms-provider.example.com/send"
SMS_API_KEY = "your-key"

def send_sms(to, body):
    try:
        resp = requests.post(
            SMS_API_URL,
            json={"to": to, "body": body},
            headers={"Authorization": f"Bearer {SMS_API_KEY}"}
        )
        resp.raise_for_status()
        # log success
    except Exception as e:
        # log error, maybe write to DB
        print("SMS error:", e)

@app.route("/send-sms", methods=["POST"])
def send_sms_endpoint():
    data = request.get_json()
    to = data["to"]
    body = data["body"]

    # Fire-and-forget
    executor.submit(send_sms, to, body)

    return jsonify({"status": "queued"}), 202
````

### Pros

* Very simple.
* No extra libraries beyond the standard library.
* Perfect for **very low load** and simple background tasks.

### Cons

* Tasks exist only in memory. If the container restarts, they’re lost.
* No retries, no job history.
* Not suitable for heavy workloads or lots of concurrent tasks.

---

## 5. Pattern 2 – In-Memory Task Queue + Worker Thread

### Use Case

When you want:

* A single place to **enqueue** tasks from various routes.
* A **worker loop** that processes them one by one.
* Still entirely in one process/container, no external queue service.

### How it Works

* An in-memory `queue.Queue` stores tasks.
* A background **worker thread** loops on the queue and executes tasks.
* Flask endpoints just `put` tasks into the queue.

### Example: Minimal Task Queue

```python
from flask import Flask, request, jsonify
from queue import Queue, Empty
import threading
import time
import requests

task_queue = Queue()

SMS_API_URL = "https://sms-provider.example.com/send"
SMS_API_KEY = "your-key"

def send_sms_task(to, body):
    resp = requests.post(
        SMS_API_URL,
        json={"to": to, "body": body},
        headers={"Authorization": f"Bearer {SMS_API_KEY}"}
    )
    resp.raise_for_status()

def worker_loop(app):
    # Need app context if using DB or app config
    with app.app_context():
        while True:
            try:
                task, args, kwargs = task_queue.get(timeout=1)
            except Empty:
                continue

            try:
                task(*args, **kwargs)
            except Exception as e:
                print("Task error:", e)
                # Optionally log to DB for manual retry.
            finally:
                task_queue.task_done()

def create_app():
    app = Flask(__name__)

    # Start worker thread once at startup
    worker_thread = threading.Thread(target=worker_loop, args=(app,), daemon=True)
    worker_thread.start()

    @app.route("/send-sms", methods=["POST"])
    def send_sms():
        data = request.get_json()
        to = data["to"]
        body = data["body"]

        # Enqueue the SMS task
        task_queue.put((send_sms_task, (to, body), {}))
        return jsonify({"status": "queued"}), 202

    return app

app = create_app()
```

### Pros

* Centralized task handling (one worker loop).
* Easy to add new task types (just new functions).
* Still simple and in-process.

### Cons

* Same durability issue: tasks disappear on restart.
* Single worker thread means tasks are processed sequentially (you can add more workers if needed).
* No built-in scheduling; this is just a queue.

---

## 6. Pattern 3 – Scheduler Thread for Timed / Recurring Tasks

### Use Case

* “Send a reminder **1 day before** an event.”
* “Every night at midnight, clean up old records.”
* “Every N minutes, sync with an external system.”

For this scenario:

* Each event has:

  * `start_time`
  * `notify_at` (e.g., `start_time - 1 day`)
  * `notified` flag

The scheduler:

1. Runs every `CHECK_INTERVAL_SECONDS`.
2. Finds all events where `notify_at <= now` and `notified = False`.
3. Sends SMS/email, then sets `notified = True`.

### Example: Scheduler Loop

```python
import threading
import time
from datetime import datetime
from your_app import db
from your_app.models import Event  # hypothetical SQLAlchemy model
from your_app.tasks import send_sms_task  # e.g., from Pattern 2

CHECK_INTERVAL_SECONDS = 60  # check every minute

def scheduler_loop(app):
    with app.app_context():
        while True:
            now = datetime.utcnow()

            due_events = (
                Event.query
                .filter(Event.notify_at <= now, Event.notified == False)
                .all()
            )

            for event in due_events:
                send_sms_task(
                    to=event.user_phone,
                    body=f"Reminder: {event.title} is tomorrow at {event.start_time}."
                )
                event.notified = True

            if due_events:
                db.session.commit()

            time.sleep(CHECK_INTERVAL_SECONDS)
```

Hook it up in `create_app`:

```python
def create_app():
    app = Flask(__name__)
    # init db, config, etc.

    # Start scheduler thread
    scheduler_thread = threading.Thread(target=scheduler_loop, args=(app,), daemon=True)
    scheduler_thread.start()

    return app
```

### Pros

* Handles **timed** tasks inside a single container.
* Simple logic: poll DB, do work.

### Cons

* If the container is down at the exact “notify time”, the job will run later (next time the scheduler runs).
* No strict guarantees; more “best effort”.
* Still no distributed coordination (this assumes a single instance).

For a small business single-workspace app, this is often good enough.

---

## 7. Pattern 4 – Background `asyncio` Event Loop (for Async I/O)

### Use Case

* You want to use **async/await** for external API calls.
* You might need to call lots of external APIs concurrently (even if total traffic is low).
* You still want to keep Flask itself **sync** (WSGI-based).

### How it Works

* Create a dedicated `asyncio` event loop in a background thread.
* Use `asyncio.run_coroutine_threadsafe()` to submit coroutines to that loop.
* Use an async HTTP client like `httpx`.

### Example: Async SMS Task

```python
# async_tasks.py
import asyncio
import threading
import httpx

loop = asyncio.new_event_loop()

def start_loop():
    asyncio.set_event_loop(loop)
    loop.run_forever()

# Start the loop in a background thread
threading.Thread(target=start_loop, daemon=True).start()

async def send_sms_async(to, body):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://sms-provider.example.com/send",
            json={"to": to, "body": body}
        )
        resp.raise_for_status()

def queue_sms_async(to, body):
    # Fire-and-forget coroutine
    future = asyncio.run_coroutine_threadsafe(
        send_sms_async(to, body),
        loop
    )
    return future
```

Use from Flask:

```python
# app.py
from flask import Flask, request, jsonify
from async_tasks import queue_sms_async

app = Flask(__name__)

@app.route("/send-sms", methods=["POST"])
def send_sms_endpoint():
    data = request.get_json()
    to = data["to"]
    body = data["body"]

    queue_sms_async(to, body)
    return jsonify({"status": "queued"}), 202
```

### Pros

* Good for **concurrent I/O** (lots of external calls).
* Still a single Flask process + single container.

### Cons

* More complexity (two concurrency models: threads + async).
* Still not durable (no persistent job store).
* Overkill for very low load unless you really like async.

---

## 8. Typical Background Needs in a Small App (and Which Pattern to Use)

### 1. User-click “Send Notification Now”

* **Need:** Fast response, non-blocking.
* **Pattern:** Fire-and-forget thread or in-memory queue.
* **Code:** Pattern 1 or 2.

### 2. Day-Before Event Reminders (Calendar)

* **Need:** Periodic checking of DB and sending SMS/email.
* **Pattern:** Scheduler thread + direct function calls or queue (Pattern 3).
* **Tolerance:** OK if occasionally late if the app was down for a bit.

### 3. Light Reports / Exports

* **Need:** Generate CSV/PDF after a user action.
* **Pattern:** Fire-and-forget thread, or queue if more than one report at a time.

### 4. Periodic Sync with External Services

* **Need:** Every 5–15 minutes, sync with CRM/Billing.
* **Pattern:** Scheduler thread + either:

  * Sync function calls (if simple), or
  * Async loop (Pattern 4) if calling many endpoints.

### 5. Housekeeping

* **Need:** Delete stale data, clean temp uploads, etc.
* **Pattern:** Scheduler thread + functions.

---

## 9. Tradeoffs and When to Upgrade

These in-process patterns work well when:

* Your Flask app runs **as a single instance** (single container).
* Load is low.
* You can tolerate:

  * Some tasks being **lost** if the container dies at the wrong moment.
  * Some tasks running **late** after the container restarts.

You should consider moving to a **real task queue** (Redis + RQ or Celery) when:

* You scale to multiple containers / processes.
* Tasks must **survive restarts**.
* You need **retries, rate limits, monitoring, dashboards**.
* Background work volume increases and becomes business-critical.

For small, low-load, single-workspace apps, the patterns in this document are usually sufficient and much simpler to manage.

---

## 10. Recommended Setup for a Small, Single-Workspace Flask App

For a simple, production-ish setup (single container, low load):

1. **Fire-and-forget thread pool** for actions directly triggered by the user.
2. **In-memory queue + worker thread** if you prefer a queue abstraction.
3. **Scheduler thread** to:

   * Send calendar reminders (day-before notifications).
   * Run periodic housekeeping and light sync tasks.
4. Optionally, **asyncio loop** if you do a lot of outbound I/O and want async.

This gives you:

* Responsive UI
* Simple code and deployment
* Enough background processing capability for a typical small business app
* No additional infrastructure beyond your existing Flask container

You can later swap out the internal queue/scheduler with Redis/RQ or Celery with minimal changes to your route logic (they still just “enqueue a job”).

