import os
import sys
from pathlib import Path

# Ensure core directory is on sys.path regardless of execution working directory
base_dir = Path(__file__).resolve().parent
if (base_dir / "core").is_dir() and str(base_dir / "core") not in sys.path:
    sys.path.insert(0, str(base_dir / "core"))
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

# Server socket
port = os.environ.get("PORT", "8000")
bind = f"0.0.0.0:{port}"

# Worker processes & threading
# Use gthread worker class so long-running requests (e.g. timetable generation SSE stream)
# do not block the worker heartbeat or block other incoming HTTP requests.
worker_class = "gthread"
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "4"))

# Timeout: Allow up to 10 minutes (600s) for complex GA / institutional timetable optimization
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "600"))
graceful_timeout = 30
keepalive = 10

# Restart workers periodically to prevent memory leaks in long-running Python processes
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
