#!/bin/bash
# Docker Watchdog - Monitors Docker daemon and auto-restarts if it crashes
# Usage: ./scripts/docker-watchdog.sh &

LOGFILE="${LOGFILE:-docker-watchdog.log}"
CHECK_INTERVAL="${CHECK_INTERVAL:-30}"  # Check every 30 seconds

echo "[$(date)] Docker watchdog started (checking every ${CHECK_INTERVAL}s)" | tee -a "$LOGFILE"

while true; do
    # Check if Docker daemon is responsive
    if ! docker ps >/dev/null 2>&1; then
        echo "[$(date)] ❌ Docker daemon not responding, attempting restart..." | tee -a "$LOGFILE"

        # Kill Docker Desktop (gracefully)
        osascript -e 'quit app "Docker"' 2>/dev/null
        sleep 5

        # Start Docker Desktop
        open -a Docker
        echo "[$(date)] 🔄 Waiting for Docker to start..." | tee -a "$LOGFILE"

        # Wait up to 60 seconds for Docker to be ready
        for i in {1..30}; do
            if docker ps >/dev/null 2>&1; then
                echo "[$(date)] ✅ Docker daemon restored" | tee -a "$LOGFILE"

                # Check if PostgreSQL container is running
                if ! docker ps | grep -q autonomous_coding_postgres; then
                    echo "[$(date)] 🔄 Starting PostgreSQL container..." | tee -a "$LOGFILE"
                    docker start autonomous_coding_postgres
                fi

                break
            fi
            sleep 2
        done

        if ! docker ps >/dev/null 2>&1; then
            echo "[$(date)] ⚠️  Docker failed to start after 60s" | tee -a "$LOGFILE"
        fi
    fi

    sleep "$CHECK_INTERVAL"
done
