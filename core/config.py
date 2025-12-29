"""
Configuration Management
========================

Centralized configuration for YokeFlow.
Supports YAML configuration files with sensible defaults.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
import yaml

# Load environment variables from .env file in agent root directory
# CRITICAL: Do NOT load from CWD, which might be a generated project directory
from dotenv import load_dotenv

# Get agent root directory (parent of core/ where this config.py file is located)
_agent_root = Path(__file__).parent.parent
_agent_env_file = _agent_root / ".env"

# Load from agent's .env only, not from any project directory
load_dotenv(dotenv_path=_agent_env_file)


@dataclass
class ModelConfig:
    """Configuration for Claude models."""
    initializer: str = field(default_factory=lambda: os.getenv(
        "DEFAULT_INITIALIZER_MODEL",
        "claude-opus-4-5-20251101"
    ))
    coding: str = field(default_factory=lambda: os.getenv(
        "DEFAULT_CODING_MODEL",
        "claude-sonnet-4-5-20250929"
    ))


@dataclass
class TimingConfig:
    """Configuration for timing and delays."""
    auto_continue_delay: int = 3  # seconds between sessions
    web_ui_poll_interval: int = 5  # seconds for UI refresh
    web_ui_port: int = 3000


@dataclass
class SecurityConfig:
    """Configuration for security settings."""
    additional_blocked_commands: List[str] = field(default_factory=list)


@dataclass
class DatabaseConfig:
    """Configuration for database settings."""
    database_url: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL",
        "postgresql://agent:agent_dev_password@localhost:5432/yokeflow"
    ))


@dataclass
class ProjectConfig:
    """Configuration for project settings."""
    default_generations_dir: str = "generations"
    max_iterations: Optional[int] = None  # None = unlimited


@dataclass
class ReviewConfig:
    """Configuration for review and prompt improvement settings."""
    min_reviews_for_analysis: int = 5  # Minimum deep reviews required for prompt improvement analysis


@dataclass
class SandboxConfig:
    """Configuration for sandbox settings."""
    type: str = "none"  # Options: "none", "docker", "e2b"

    # Docker-specific settings
    docker_image: str = "yokeflow-sandbox:latest"
    docker_network: str = "bridge"
    docker_memory_limit: str = "2g"
    docker_cpu_limit: str = "2.0"
    docker_ports: List[str] = field(default_factory=lambda: [
        # Empty by default - no port forwarding needed when Playwright runs inside container
        # Add ports here only if you need manual browser debugging: e.g., "5173:5173"
    ])

    # E2B-specific settings
    e2b_api_key: Optional[str] = field(default_factory=lambda: os.getenv("E2B_API_KEY"))
    e2b_tier: str = "free"  # "free" or "pro"


@dataclass
class Config:
    """Main configuration class."""
    models: ModelConfig = field(default_factory=ModelConfig)
    timing: TimingConfig = field(default_factory=TimingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    project: ProjectConfig = field(default_factory=ProjectConfig)
    review: ReviewConfig = field(default_factory=ReviewConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)

    @classmethod
    def load_from_file(cls, config_path: Path) -> 'Config':
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to YAML config file

        Returns:
            Config instance with values from file merged with defaults
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r') as f:
            data = yaml.safe_load(f) or {}

        # Create config with defaults, then override with file values
        config = cls()

        # Override model settings
        if 'models' in data:
            if 'initializer' in data['models']:
                config.models.initializer = data['models']['initializer']
            if 'coding' in data['models']:
                config.models.coding = data['models']['coding']

        # Override timing settings
        if 'timing' in data:
            if 'auto_continue_delay' in data['timing']:
                config.timing.auto_continue_delay = data['timing']['auto_continue_delay']
            if 'web_ui_poll_interval' in data['timing']:
                config.timing.web_ui_poll_interval = data['timing']['web_ui_poll_interval']
            if 'web_ui_port' in data['timing']:
                config.timing.web_ui_port = data['timing']['web_ui_port']

        # Override security settings
        if 'security' in data:
            if 'additional_blocked_commands' in data['security']:
                config.security.additional_blocked_commands = data['security']['additional_blocked_commands']

        # Override database settings
        if 'database' in data:
            if 'database_url' in data['database']:
                config.database.database_url = data['database']['database_url']

        # Override project settings
        if 'project' in data:
            if 'default_generations_dir' in data['project']:
                config.project.default_generations_dir = data['project']['default_generations_dir']
            if 'max_iterations' in data['project']:
                config.project.max_iterations = data['project']['max_iterations']

        # Override review settings
        if 'review' in data:
            if 'min_reviews_for_analysis' in data['review']:
                config.review.min_reviews_for_analysis = data['review']['min_reviews_for_analysis']

        # Override sandbox settings
        if 'sandbox' in data:
            if 'type' in data['sandbox']:
                config.sandbox.type = data['sandbox']['type']
            if 'docker_image' in data['sandbox']:
                config.sandbox.docker_image = data['sandbox']['docker_image']
            if 'docker_network' in data['sandbox']:
                config.sandbox.docker_network = data['sandbox']['docker_network']
            if 'docker_memory_limit' in data['sandbox']:
                config.sandbox.docker_memory_limit = data['sandbox']['docker_memory_limit']
            if 'docker_cpu_limit' in data['sandbox']:
                config.sandbox.docker_cpu_limit = data['sandbox']['docker_cpu_limit']
            if 'e2b_api_key' in data['sandbox']:
                config.sandbox.e2b_api_key = data['sandbox']['e2b_api_key']
            if 'e2b_tier' in data['sandbox']:
                config.sandbox.e2b_tier = data['sandbox']['e2b_tier']

        return config

    @classmethod
    def load_default(cls) -> 'Config':
        """
        Load default configuration.

        Looks for config files in this order:
        1. .yokeflow.yaml in current directory
        2. .yokeflow.yaml in home directory
        4. Default values (no file)

        Returns:
            Config instance
        """
        # Check current directory for new name
        current_dir_config = Path('.yokeflow.yaml')
        if current_dir_config.exists():
            return cls.load_from_file(current_dir_config)

        # Check home directory for new name
        home_config = Path.home() / '.yokeflow.yaml'
        if home_config.exists():
            return cls.load_from_file(home_config)

        # Use defaults
        return cls()

    def to_yaml(self) -> str:
        """
        Convert configuration to YAML string.

        Returns:
            YAML representation of config
        """
        data = {
            'models': {
                'initializer': self.models.initializer,
                'coding': self.models.coding,
            },
            'timing': {
                'auto_continue_delay': self.timing.auto_continue_delay,
                'web_ui_poll_interval': self.timing.web_ui_poll_interval,
                'web_ui_port': self.timing.web_ui_port,
            },
            'security': {
                'additional_blocked_commands': self.security.additional_blocked_commands,
            },
            'database': {
                'database_url': self.database.database_url,
            },
            'project': {
                'default_generations_dir': self.project.default_generations_dir,
                'max_iterations': self.project.max_iterations,
            },
            'review': {
                'min_reviews_for_analysis': self.review.min_reviews_for_analysis,
            },
            'sandbox': {
                'type': self.sandbox.type,
                'docker_image': self.sandbox.docker_image,
                'docker_network': self.sandbox.docker_network,
                'docker_memory_limit': self.sandbox.docker_memory_limit,
                'docker_cpu_limit': self.sandbox.docker_cpu_limit,
                'e2b_api_key': self.sandbox.e2b_api_key,
                'e2b_tier': self.sandbox.e2b_tier,
            },
        }
        return yaml.dump(data, default_flow_style=False, sort_keys=False)
