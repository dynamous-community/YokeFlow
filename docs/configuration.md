# Configuration File Guide

The autonomous coding agent supports YAML configuration files for managing settings without command-line flags.

## Quick Start

1. **Copy the example config:**
   ```bash
   cp .autonomous-coding.yaml.example .autonomous-coding.yaml
   ```

2. **Edit settings** in `.autonomous-coding.yaml`

3. **Run the agent** (config is automatically detected):
   ```bash
   python autonomous_agent.py --project-dir my_project
   ```

## Configuration File Locations

The agent looks for configuration files in this order:

1. **Custom path** via `--config` flag:
   ```bash
   python autonomous_agent.py --config my-config.yaml --project-dir my_project
   ```

2. **Current directory**: `.autonomous-coding.yaml`
   - Project-specific settings
   - Checked first

3. **Home directory**: `~/.autonomous-coding.yaml`
   - Global defaults for all projects
   - Checked if no local config exists

4. **Built-in defaults**
   - Used if no config file found
   - See [config.py](../config.py) for default values

## Configuration Options

### Models

Control which Claude models are used:

```yaml
models:
  initializer: claude-opus-4-5-20251101   # For planning/initialization
  coding: claude-sonnet-4-5-20250929      # For implementation
```

**Recommended:**
- **Opus** for initialization (better planning)
- **Sonnet** for coding (faster, more cost-effective)

### Timing

Control delays and intervals:

```yaml
timing:
  auto_continue_delay: 3      # Seconds between sessions
  web_ui_poll_interval: 5     # Web UI refresh interval
  web_ui_port: 5001           # Web dashboard port
```

### Security

Add custom blocked commands:

```yaml
security:
  additional_blocked_commands:
    - my-dangerous-script
    - custom-deploy-tool
```

These are added to the built-in blocklist in [security.py](../security.py).

### Project

Project-level settings:

```yaml
project:
  default_generations_dir: generations   # Where to store projects
  max_iterations: null                    # Default iteration limit (null = unlimited)
```

## Priority Order

Settings are applied in this order (highest priority first):

1. **Command-line arguments** (always win)
   ```bash
   python autonomous_agent.py --model claude-opus-4-5-20251101 --project-dir my_project
   ```

2. **Configuration file** (--config or auto-detected)
   ```yaml
   models:
     coding: claude-sonnet-4-5-20250929
   ```

3. **Built-in defaults** (fallback)
   ```python
   # From config.py
   initializer: "claude-opus-4-5-20251101"
   coding: "claude-sonnet-4-5-20250929"
   ```

## Examples

### Example 1: Basic Config

Create `.autonomous-coding.yaml` in project directory:

```yaml
models:
  initializer: claude-opus-4-5-20251101
  coding: claude-sonnet-4-5-20250929

timing:
  auto_continue_delay: 5  # Slower pace
```

Run agent (uses config automatically):
```bash
python autonomous_agent.py --project-dir my_project
```

### Example 2: Override Config

Config file has Sonnet for coding, but you want Opus:

```bash
python autonomous_agent.py --project-dir my_project --coding-model claude-opus-4-5-20251101
```

CLI argument overrides config file.

### Example 3: Global Defaults

Create `~/.autonomous-coding.yaml` for all projects:

```yaml
models:
  initializer: claude-opus-4-5-20251101
  coding: claude-sonnet-4-5-20250929

project:
  default_generations_dir: my-projects
  max_iterations: 10  # Safety limit
```

Every project uses these defaults unless overridden.

### Example 4: Project-Specific Config

Different settings for a specific project:

```bash
cd my-special-project
```

Create `.autonomous-coding.yaml`:
```yaml
models:
  coding: claude-opus-4-5-20251101  # Use Opus for this complex project

timing:
  auto_continue_delay: 10  # Slower for debugging
```

This project uses Opus, other projects use global defaults.

## Validation

The config system validates settings on load:

- Invalid YAML → error message
- Missing file (--config specified) → error
- Missing file (auto-detect) → use defaults
- Invalid model names → passed through (API will validate)

## Debugging

See which config was loaded:

```bash
python autonomous_agent.py --project-dir my_project
# Output: "Loaded configuration from: .autonomous-coding.yaml (current directory)"
```

Possible outputs:
- `Loaded configuration from: <path>` (config found)
- `Using default configuration (no config file found)` (using defaults)

## Advanced Usage

### Per-Project Config Template

Create a config template for new projects:

```bash
# In your project template
cp .autonomous-coding.yaml.example new-project/.autonomous-coding.yaml
cd new-project
# Edit settings
python ../autonomous_agent.py --project-dir .
```

### Config Generator

Generate a config from current defaults:

```python
from config import Config

config = Config()
with open('.autonomous-coding.yaml', 'w') as f:
    f.write(config.to_yaml())
```

### Multiple Config Files

Use different configs for different scenarios:

```bash
# Development config
python autonomous_agent.py --config dev-config.yaml --project-dir my_project

# Production config
python autonomous_agent.py --config prod-config.yaml --project-dir my_project
```

## Best Practices

1. **Use global config** (`~/.autonomous-coding.yaml`) for personal defaults
2. **Use local config** (`.autonomous-coding.yaml`) for project-specific needs
3. **Add to .gitignore** if config contains sensitive paths
4. **Version control** `.autonomous-coding.yaml.example` as a template
5. **Document** any non-standard settings in project README

## See Also

- [config.py](../config.py) - Configuration implementation
- [.autonomous-coding.yaml.example](../.autonomous-coding.yaml.example) - Full example with comments
- [autonomous_agent.py](../autonomous_agent.py) - How config is loaded and used
