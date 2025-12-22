# Docker Desktop Stability on macOS

**Problem:** Docker Desktop can crash during long-running autonomous sessions, even when macOS sleep is disabled.

**Impact:** PostgreSQL goes offline → Sessions fail with "Connection refused" errors

## Root Cause

Docker Desktop on macOS is a GUI application that can crash for several reasons:
- Memory pressure after hours of operation
- macOS system updates/maintenance
- Background resource management
- Rare Docker Desktop bugs

Even with `sudo pmset -a disablesleep 1`, Docker Desktop can still crash independently.

## Solution: Two-Part Strategy

### Part 1: Disable macOS Sleep (Required)

**CRITICAL: Must disable BOTH system sleep AND display sleep**

Docker Desktop runs as a GUI application. When the display sleeps and screen locks, macOS throttles/suspends user-space processes including Docker's hypervisor/VM.

**Mac Mini / iMac - Complete Configuration:**
```bash
# Disable system sleep
sudo pmset -a disablesleep 1

# Disable display sleep (CRITICAL for Docker!)
sudo pmset -a displaysleep 0

# Disable Power Nap
sudo pmset -a powernap 0

# Cancel any scheduled sleep/wake events
sudo pmset schedule cancelall

# Disable screen lock (prevents Docker throttling)
sysadminctl -screenLock off
```

**Or via System Settings:**
- System Settings → Lock Screen
- Set "Require password after..." to **Never**
- System Settings → Energy Saver
- Set "Turn display off after" to **Never**

**To verify:**
```bash
pmset -g | grep -i sleep
# Should show:
#   SleepDisabled    1
#   displaysleep     0
#   powernap         0
```

**To re-enable sleep later:**
```bash
sudo pmset -a disablesleep 0
sudo pmset -a displaysleep 10
sudo pmset -a powernap 1
sysadminctl -screenLock on
```

### Part 2: Docker Watchdog (Recommended)

A background script that monitors Docker and auto-restarts it if it crashes:

**Start the watchdog:**
```bash
./scripts/docker-watchdog.sh &
```

**What it does:**
1. Checks Docker daemon every 30 seconds
2. If Docker is not responding:
   - Quits Docker Desktop gracefully
   - Restarts Docker Desktop
   - Waits for daemon to be ready
   - Restarts PostgreSQL container
3. Logs all events to `docker-watchdog.log`

**Monitoring:**
```bash
# Watch the watchdog log in real-time
tail -f docker-watchdog.log
```

**Stopping the watchdog:**
```bash
# Find the process
ps aux | grep docker-watchdog

# Kill it
kill <PID>
```

## Complete Startup Sequence

For long-running autonomous sessions:

```bash
# Terminal 1: Disable ALL sleep (one-time setup)
sudo pmset -a disablesleep 1       # System sleep
sudo pmset -a displaysleep 0        # Display sleep (CRITICAL!)
sudo pmset -a powernap 0            # Power Nap
sudo pmset schedule cancelall       # Scheduled events
sysadminctl -screenLock off         # Screen lock (CRITICAL!)

# Verify settings
pmset -g | grep -i sleep

# Terminal 2: Start Docker watchdog (optional but recommended)
./scripts/docker-watchdog.sh &

# Terminal 3: Start API server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 4: Start Web UI
cd web-ui && npm run dev
```

Then navigate to http://localhost:3000 and start your sessions.

**Why both display sleep AND screen lock matter:**
- Display sleep alone can trigger screen lock
- Screen lock causes macOS to throttle GUI applications
- Docker Desktop (a GUI app) gets throttled → VM suspends → PostgreSQL unreachable
- Must disable BOTH to prevent Docker issues

## Evidence from Session Logs

### Session 41 (First Docker Crash)
```
All tasks #689-696 are now complete! Let me commit this work:
[Tool: Bash]
Failed to execute command in Docker: ('Connection aborted.', ConnectionRefusedError(61, 'Connection refused'))
```

**What happened:** Docker daemon stopped responding mid-session.

### Recovery
The agent tried to recover but couldn't commit work. However:
- ✅ Session 42 started successfully (after Docker recovered)
- ✅ Session 44 completed Epic #104 (8 tasks)
- ✅ All work was eventually committed

This shows the system is resilient, but the watchdog would prevent the interruption entirely.

## Why Not Just Use System Preferences?

**System Preferences → Energy Saver:**
- ✅ Can prevent automatic sleep
- ❌ Doesn't prevent Docker Desktop crashes
- ❌ Can be overridden by other processes
- ❌ Settings can be reset by system updates

**pmset + watchdog:**
- ✅ More reliable sleep prevention
- ✅ Auto-recovery from Docker crashes
- ✅ Logged events for debugging
- ✅ No human intervention needed

## Watchdog Configuration

The watchdog script supports environment variables:

```bash
# Check every 60 seconds instead of 30
CHECK_INTERVAL=60 ./scripts/docker-watchdog.sh &

# Use custom log file
LOGFILE=/tmp/docker-watch.log ./scripts/docker-watchdog.sh &
```

## Alternative: Deploy to Linux Server

For production use, deploy to a Linux server where:
- ✅ Docker is a system service (systemd manages it)
- ✅ No Desktop app to crash
- ✅ No sleep issues
- ✅ Better stability for long-running processes

Options:
- Digital Ocean Droplet ($12/month)
- AWS EC2 t3.medium
- Linode
- Your own Linux server

## Troubleshooting

**Watchdog not starting:**
```bash
# Check if script exists and is executable
ls -la scripts/docker-watchdog.sh
# Should show: -rwxr-xr-x

# If not executable:
chmod +x scripts/docker-watchdog.sh
```

**Docker keeps crashing:**
```bash
# Check Docker Desktop resources
# Docker Desktop → Preferences → Resources
# Increase CPUs, Memory, Swap if needed

# Check macOS Console for Docker Desktop crashes
# Applications → Utilities → Console
# Filter: "Docker"
```

**PostgreSQL not restarting:**
```bash
# Manually restart container
docker start autonomous_coding_postgres

# Check container health
docker ps -a | grep postgres

# Check logs
docker logs autonomous_coding_postgres
```

## Summary

✅ **Always do:** `sudo pmset -a disablesleep 1`
✅ **Recommended:** Run Docker watchdog in background
✅ **Best long-term:** Deploy to Linux server

With both sleep prevention AND the watchdog, autonomous sessions can run for days without interruption.
