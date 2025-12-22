"""
Security Hooks for Autonomous Coding Agent
==========================================

Pre-tool-use hooks that validate bash commands for security.
Uses a blocklist approach - blocks dangerous commands, allows most development tasks.

Designed for containerized environments where broader command access is safe.
"""

import os
import shlex


# Dangerous commands that should never be allowed
BLOCKED_COMMANDS = {
    # System modification
    # Note: "rm" moved to COMMANDS_NEEDING_EXTRA_VALIDATION for safe file cleanup
    "sudo",     # Privilege escalation
    "su",       # User switching
    "chown",    # Ownership changes
    "chgrp",    # Group changes

    # Network attacks
    "dd",       # Can overwrite disks
    "mkfs",     # Filesystem creation (can destroy data)
    "fdisk",    # Disk partitioning
    "parted",   # Disk partitioning

    # System control
    "reboot",   # System restart
    "shutdown", # System shutdown
    "halt",     # System halt
    "poweroff", # System poweroff
    "init",     # Init system control
    "systemctl",# Systemd control
    "service",  # Service control

    # Package management (prevent system-wide changes)
    "apt",      # Debian package manager
    "apt-get",  # Debian package manager
    "yum",      # RedHat package manager
    "dnf",      # Fedora package manager
    "pacman",   # Arch package manager
    "brew",     # macOS package manager (system-wide)

    # Kernel modules
    "insmod",   # Load kernel module
    "rmmod",    # Remove kernel module
    "modprobe", # Kernel module management

    # User management
    "useradd",  # Add user
    "userdel",  # Delete user
    "usermod",  # Modify user
    "passwd",   # Change password
    "adduser",  # Add user (Debian)
    "deluser",  # Delete user (Debian)
}

# Commands that need additional validation even when not blocked
COMMANDS_NEEDING_EXTRA_VALIDATION = {"pkill", "chmod", "rm"}


def split_command_segments(command_string: str) -> list[str]:
    """
    Split a compound command into individual command segments.

    Handles command chaining (&&, ||, ;) but not pipes (those are single commands).
    Properly handles quoted strings to avoid splitting on operators inside quotes.

    Args:
        command_string: The full shell command

    Returns:
        List of individual command segments
    """
    result = []
    current_segment = []
    in_single_quote = False
    in_double_quote = False
    i = 0

    while i < len(command_string):
        char = command_string[i]

        # Handle quote tracking
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            current_segment.append(char)
        elif char == '"' and not in_single_quote:
            # Check if it's escaped
            if i > 0 and command_string[i-1] == '\\':
                current_segment.append(char)
            else:
                in_double_quote = not in_double_quote
                current_segment.append(char)
        # Handle operators only when not in quotes
        elif not in_single_quote and not in_double_quote:
            # Check for && or ||
            if i + 1 < len(command_string):
                two_char = command_string[i:i+2]
                if two_char in ('&&', '||'):
                    # Found operator, save current segment
                    seg = ''.join(current_segment).strip()
                    if seg:
                        result.append(seg)
                    current_segment = []
                    i += 1  # Skip the second character
                    i += 1
                    continue

            # Check for semicolon
            if char == ';':
                seg = ''.join(current_segment).strip()
                if seg:
                    result.append(seg)
                current_segment = []
                i += 1
                continue

            current_segment.append(char)
        else:
            current_segment.append(char)

        i += 1

    # Don't forget the last segment
    seg = ''.join(current_segment).strip()
    if seg:
        result.append(seg)

    return result


def extract_commands(command_string: str) -> list[str]:
    """
    Extract command names from a shell command string.

    Handles pipes, command chaining (&&, ||, ;), and subshells.
    Returns the base command names (without paths).

    Args:
        command_string: The full shell command

    Returns:
        List of command names found in the string
    """
    commands = []

    # Use split_command_segments for proper quote handling
    segments = split_command_segments(command_string)

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        try:
            tokens = shlex.split(segment)
        except ValueError:
            # Malformed command (unclosed quotes, etc.)
            # Return empty to trigger block (fail-safe)
            return []

        if not tokens:
            continue

        # Track when we expect a command vs arguments
        expect_command = True

        for token in tokens:
            # Shell operators indicate a new command follows
            if token in ("|", "||", "&&", "&"):
                expect_command = True
                continue

            # Skip shell keywords that precede commands
            if token in (
                "if",
                "then",
                "else",
                "elif",
                "fi",
                "for",
                "while",
                "until",
                "do",
                "done",
                "case",
                "esac",
                "in",
                "!",
                "{",
                "}",
            ):
                continue

            # Skip flags/options
            if token.startswith("-"):
                continue

            # Skip variable assignments (VAR=value)
            if "=" in token and not token.startswith("="):
                continue

            if expect_command:
                # Extract the base command name (handle paths like /usr/bin/python)
                cmd = os.path.basename(token)
                commands.append(cmd)
                expect_command = False

    return commands


def validate_pkill_command(command_string: str) -> tuple[bool, str]:
    """
    Validate pkill commands - only allow killing dev-related processes.

    Uses shlex to parse the command, avoiding regex bypass vulnerabilities.
    Handles regex patterns in -f flag (e.g., 'node.*index.js', 'vite|npm').

    Returns:
        Tuple of (is_allowed, reason_if_blocked)
    """
    import re

    # Allowed process names for pkill
    allowed_process_names = {
        "node",
        "npm",
        "npx",
        "pnpm",
        "yarn",
        "vite",
        "next",
        "webpack",
        "tsc",
        "python",
        "python3",
        "uvicorn",
        "gunicorn",
    }

    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse pkill command"

    if not tokens:
        return False, "Empty pkill command"

    # Separate flags from arguments, filtering out redirections
    args = []
    for token in tokens[1:]:
        # Skip flags
        if token.startswith("-"):
            continue
        # Skip shell redirections (>, >>, 2>, &>, etc.)
        if token.startswith(">") or token.endswith(">") or ">" in token:
            continue
        # Skip /dev/null and other file descriptors
        if token.startswith("/dev/") or token in ("&1", "&2"):
            continue
        args.append(token)

    if not args:
        return False, "pkill requires a process name"

    # The target is typically the last non-flag argument
    target = args[-1]

    def extract_process_name(pattern: str) -> str:
        """
        Extract process name from a pkill -f pattern, handling regex operators.

        Examples:
            'node.*index.js' -> 'node'
            'node server.js' -> 'node'
            'vite' -> 'vite'
        """
        # First split on space to get the first word
        if " " in pattern:
            pattern = pattern.split()[0]

        # Then remove regex operators (.*+?[](){}^$|\) to get the base process name
        # Split on any regex metacharacter and take the first part
        cleaned = re.split(r'[.*+?\[\](){}^$|\\]', pattern)[0]
        return cleaned.strip()

    # For -f flag (full command line match), handle regex patterns with | (OR operator)
    # e.g., "pkill -f 'vite|npm run dev'" -> check both 'vite' and 'npm run dev'
    if "|" in target:
        # Split on pipe and validate each alternative
        alternatives = target.split("|")
        for alt in alternatives:
            alt = alt.strip()
            process_name = extract_process_name(alt)
            if process_name not in allowed_process_names:
                return False, f"pkill only allowed for dev processes: {allowed_process_names}"
        return True, ""

    # For simple patterns, extract the process name
    # e.g., "pkill -f 'node server.js'" -> "node"
    # e.g., "pkill -f 'node.*index.js'" -> "node"
    process_name = extract_process_name(target)

    if process_name in allowed_process_names:
        return True, ""
    return False, f"pkill only allowed for dev processes: {allowed_process_names}"


def validate_chmod_command(command_string: str) -> tuple[bool, str]:
    """
    Validate chmod commands - only allow making files executable with +x.

    Returns:
        Tuple of (is_allowed, reason_if_blocked)
    """
    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse chmod command"

    if not tokens or tokens[0] != "chmod":
        return False, "Not a chmod command"

    # Look for the mode argument
    # Valid modes: +x, u+x, a+x, etc. (anything ending with +x for execute permission)
    mode = None
    files = []

    for token in tokens[1:]:
        if token.startswith("-"):
            # Skip flags like -R (we don't allow recursive chmod anyway)
            return False, "chmod flags are not allowed"
        elif mode is None:
            mode = token
        else:
            files.append(token)

    if mode is None:
        return False, "chmod requires a mode"

    if not files:
        return False, "chmod requires at least one file"

    # Only allow +x variants (making files executable)
    # This matches: +x, u+x, g+x, o+x, a+x, ug+x, etc.
    import re

    if not re.match(r"^[ugoa]*\+x$", mode):
        return False, f"chmod only allowed with +x mode, got: {mode}"

    return True, ""


def validate_rm_command(command_string: str) -> tuple[bool, str]:
    """
    Validate rm commands - allow safe file cleanup, block dangerous operations.

    Allows:
        - Single files: rm file.js, rm -f .git/index.lock
        - Project files: rm server/migrations/003.js
        - Safe temp dirs: rm -rf .playwright-mcp/, rm -rf node_modules/.cache/
        - Safe wildcards: rm *.log, rm temp/*.txt

    Blocks:
        - System paths: rm -rf /, rm -rf /etc, rm -rf /usr
        - Home directory: rm -rf ~, rm -rf $HOME
        - Dangerous wildcards: rm -rf *, rm -rf /*
        - Parent escapes: rm -rf ../../../
        - Important project: rm -rf .git/, rm package.json, rm -rf src/

    Returns:
        Tuple of (is_allowed, reason_if_blocked)
    """
    import re

    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse rm command"

    if not tokens or tokens[0] != "rm":
        return False, "Not an rm command"

    # Parse flags and targets
    has_recursive = False
    has_force = False
    targets = []

    i = 1
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("-"):
            # Handle combined flags like -rf
            if "r" in token.lower():
                has_recursive = True
            if "f" in token.lower():
                has_force = True
            # Skip --recursive, --force, etc.
        else:
            targets.append(token)
        i += 1

    if not targets:
        return False, "rm requires at least one target"

    # Dangerous patterns to block
    dangerous_patterns = [
        # System paths
        r"^/+$",                    # / or //
        r"^/etc(/|$)",              # /etc or /etc/...
        r"^/usr(/|$)",              # /usr or /usr/...
        r"^/bin(/|$)",              # /bin
        r"^/sbin(/|$)",             # /sbin
        r"^/lib(/|$)",              # /lib
        r"^/boot(/|$)",             # /boot
        r"^/sys(/|$)",              # /sys
        r"^/proc(/|$)",             # /proc
        r"^/dev(/|$)",              # /dev
        r"^/var(/|$)",              # /var (careful!)
        r"^/opt(/|$)",              # /opt

        # Home directory
        r"^~(/|$)",                 # ~ or ~/...
        r"^\$HOME(/|$)",            # $HOME or $HOME/...
        r"^\${HOME}(/|$)",          # ${HOME}

        # Dangerous wildcards
        r"^\*$",                    # Just *
        r"^/\*",                    # /*
        r"^\.\*$",                  # .*

        # Parent directory escapes (3+ levels)
        r"(\.\./){3,}",             # ../../../ (3 or more levels)
    ]

    # Important project files/dirs to protect
    protected_files = {
        "package.json",
        "package-lock.json",
        ".env",
        ".git",
        ".git/",
        "node_modules",
        "src/",
        "server/",
        "dist/",
        "build/",
    }

    for target in targets:
        # Check dangerous patterns
        for pattern in dangerous_patterns:
            if re.search(pattern, target):
                return False, f"rm target blocked (dangerous path): {target}"

        # Normalize target (remove trailing slashes for comparison)
        normalized = target.rstrip("/")

        # Check for protected files (applies to both rm and rm -r)
        # These are critical project files that should never be deleted
        critical_files = {
            "package.json",
            "package-lock.json",
            ".env",
        }

        if normalized in critical_files or target in critical_files:
            return False, f"rm blocked for critical project file: {target}"

        # If recursive, check for protected project directories
        if has_recursive:
            # Block recursive deletion of important project directories
            if normalized in protected_files or target in protected_files:
                return False, f"rm -r blocked for protected directory: {target}"

            # Block recursive wildcard (rm -rf *)
            if "*" in target and len(target.strip("*")) < 3:
                return False, f"rm -r with broad wildcard blocked: {target}"

            # Allow temp/cache directories
            safe_recursive_dirs = [
                ".playwright-mcp",
                "node_modules/.cache",
                ".cache",
                ".temp",
                ".tmp",
                "temp",
                "tmp",
                ".next/cache",
                ".turbo",
                "coverage",
            ]

            # Check if target starts with any safe directory
            is_safe_dir = any(
                normalized.startswith(safe_dir) or target.startswith(safe_dir + "/")
                for safe_dir in safe_recursive_dirs
            )

            if not is_safe_dir:
                # Block other recursive operations unless they're clearly scoped
                # Allow: rm -rf server/migrations/temp/
                # Block: rm -rf server/ (too broad)
                path_depth = target.count("/")
                if path_depth < 2 and not target.startswith("."):
                    return False, f"rm -r blocked (too broad, use specific path): {target}"

    return True, ""


def get_command_for_validation(cmd: str, segments: list[str]) -> str:
    """
    Find the specific command segment that contains the given command.

    Args:
        cmd: The command name to find
        segments: List of command segments

    Returns:
        The segment containing the command, or empty string if not found
    """
    for segment in segments:
        segment_commands = extract_commands(segment)
        if cmd in segment_commands:
            return segment
    return ""


async def bash_security_hook(input_data, tool_use_id=None, context=None):
    """
    Pre-tool-use hook that validates bash commands using a blocklist.

    Blocks dangerous system commands, allows most development tasks.
    Designed for containerized environments.

    Args:
        input_data: Dict containing tool_name and tool_input
        tool_use_id: Optional tool use ID
        context: Optional context

    Returns:
        Empty dict to allow, or {"decision": "block", "reason": "..."} to block
    """
    if input_data.get("tool_name") != "Bash":
        return {}

    command = input_data.get("tool_input", {}).get("command", "")
    if not command:
        return {}

    # Extract all commands from the command string
    commands = extract_commands(command)

    if not commands:
        # Could not parse - fail safe by blocking
        return {
            "decision": "block",
            "reason": f"Could not parse command for security validation: {command}",
        }

    # Split into segments for per-command validation
    segments = split_command_segments(command)

    # Check each command against the blocklist
    for cmd in commands:
        if cmd in BLOCKED_COMMANDS:
            return {
                "decision": "block",
                "reason": f"Command '{cmd}' is blocked for security reasons (dangerous system command)",
            }

        # Additional validation for sensitive commands
        if cmd in COMMANDS_NEEDING_EXTRA_VALIDATION:
            # Find the specific segment containing this command
            cmd_segment = get_command_for_validation(cmd, segments)
            if not cmd_segment:
                cmd_segment = command  # Fallback to full command

            if cmd == "pkill":
                allowed, reason = validate_pkill_command(cmd_segment)
                if not allowed:
                    return {"decision": "block", "reason": reason}
            elif cmd == "chmod":
                allowed, reason = validate_chmod_command(cmd_segment)
                if not allowed:
                    return {"decision": "block", "reason": reason}
            elif cmd == "rm":
                allowed, reason = validate_rm_command(cmd_segment)
                if not allowed:
                    return {"decision": "block", "reason": reason}

    return {}
