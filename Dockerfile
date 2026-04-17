FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app.
COPY . .

# Instance dir is where SQLite lives. When Railway mounts a volume here
# at runtime, the DB persists across deploys.
RUN mkdir -p /app/instance

# Railway sets $PORT at runtime. Default to 8080 for local runs.
ENV PORT=8080
EXPOSE 8080

# Single worker + threads: Playwright's sync API is not fork-safe, and the
# app uses in-memory JOBS state for SSE progress, so scaling workers would
# split state. Threads handle concurrent SSE + regenerate calls.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 600 --access-logfile - --error-logfile - app:app"]
