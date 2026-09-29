# syntax=docker/dockerfile:1
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies in their own layer, so editing the app does not reinstall them.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# This process holds GitHub and LeetCode tokens, so it does not run as root.
# Nothing here is written to disk: state lives in memory for the process.
RUN useradd --create-home --uid 10001 appuser
COPY --chown=appuser:appuser \
    app.py \
    integration.py \
    github_integration.py \
    leetcode_integration.py \
    pomodoro.py \
    sites_integration.py \
    ./
USER appuser

EXPOSE 5000

# --workers 1 is not a default, it is a requirement. Tokens live in an
# in-process store, so a second worker would not see the session that just
# completed an OAuth login and the dashboard would report "not connected" after
# a successful sign-in. Use threads for concurrency instead.
#
# --no-control-socket because the default path is $HOME/.gunicorn/gunicorn.ctl,
# and the compose files give this container a read-only root filesystem with only
# /tmp writable. Without it every boot logs a "Control server error: read-only
# file system". The socket is for an external process to signal the master, and
# nothing here uses one.
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5000", \
     "--workers", "1", \
     "--threads", "8", \
     "--timeout", "60", \
     "--no-control-socket", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
