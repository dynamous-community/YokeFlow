#!/bin/bash
# Entrypoint script for YokeFlow API
# Fixes permissions then runs as non-root user

# If Docker socket exists and is accessible as root, fix its permissions
if [ -S /var/run/docker.sock ]; then
    # Change socket group to docker (gid 999) so yokeflow user can access it
    chgrp docker /var/run/docker.sock 2>/dev/null || true
    chmod g+rw /var/run/docker.sock 2>/dev/null || true
fi

# Fix generations directory permissions (mounted volume)
if [ -d /app/generations ]; then
    chown -R yokeflow:yokeflow /app/generations 2>/dev/null || true
fi

# Create generations directory if it doesn't exist
mkdir -p /app/generations
chown yokeflow:yokeflow /app/generations

# Create Claude Code config directory structure for OAuth token support
# Claude Code needs write access to .claude/debug and other subdirs
mkdir -p /home/yokeflow/.claude/debug
mkdir -p /home/yokeflow/.claude/projects
chown -R yokeflow:yokeflow /home/yokeflow/.claude

# Switch to yokeflow user and exec the main command
exec gosu yokeflow "$@"
