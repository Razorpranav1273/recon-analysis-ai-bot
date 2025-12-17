"""
Configuration Reader for Recon Analysis Bot
Based on the poc_risk_agent config reader pattern.
"""

import os
import tomllib
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


class ConfigReader:
    """
    Configuration reader that supports default and environment-specific configs.
    Supports environment variable overrides and nested configuration access.
    """

    def __init__(self, key_delimiter: str = "."):
        self._config = {}
        self._key_delimiter = key_delimiter

        # Set config path relative to project root
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self._config_path = os.path.join(current_dir, "config")

        # Determine environment (default to 'dev')
        self._config_name = os.getenv("APP_ENV") or "dev"
        self._config_file = f"{self._config_name}.toml"
        self._default_config_file = "default.toml"

    def _get_env_config_file(self) -> str:
        """Get path to environment-specific config file."""
        return os.path.join(self._config_path, self._config_file)

    def _get_default_config_file(self) -> str:
        """Get path to default config file."""
        return os.path.join(self._config_path, self._default_config_file)

    def _merge_dicts(self, src: Dict, target: Dict) -> None:
        """Recursively merge source dict into target dict."""
        for k, v in src.items():
            if isinstance(v, dict) and k in target:
                self._merge_dicts(v, target[k])
            else:
                target[k] = v

    def _merge_with_env_prefix(self, key: str) -> str:
        """Convert config key to environment variable name."""
        key = key.replace(".", "_")
        return key.upper()

    def _search_dict(self, d: Dict, keys: list) -> Any:
        """Search for nested configuration value."""
        if not keys:
            return d

        for key in keys:
            val = self._find_insensitive(key, d)
            if val is not None and not isinstance(val, dict):
                return val
            elif val:
                return self._search_dict(val, keys[1:])
            else:
                return None

    def _find_insensitive(self, key: str, source: Dict) -> Any:
        """Find key in dict with case-insensitive matching."""
        real_key = next(
            (real for real in source.keys() if real.lower() == key.lower()), None
        )
        return source.get(real_key)

    def _expand_env_vars(self, value: Any) -> Any:
        """Recursively expand environment variables in config values."""
        if isinstance(value, str):
            # Check for ${VAR} pattern
            if value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                return os.getenv(env_var, value)
            return value
        elif isinstance(value, dict):
            return {k: self._expand_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._expand_env_vars(item) for item in value]
        return value

    def get(self, key: str) -> Any:
        """
        Get configuration value by key.

        Priority order:
        1. Environment variables
        2. Configuration files (env-specific + default)
        3. Nested configuration paths

        Args:
            key: Configuration key (supports dot notation for nested access)

        Returns:
            Configuration value or None if not found
        """
        # Check environment variables first
        val = os.getenv(self._merge_with_env_prefix(key))
        if val is not None:
            return val

        # Check from loaded config
        val = self._find_insensitive(key, self._config)
        if val is not None:
            return self._expand_env_vars(val)

        # Handle nested configuration paths
        if self._key_delimiter in key:
            path = key.split(self._key_delimiter)

            source = self.get(path[0])
            if source is not None and isinstance(source, dict):
                val = self._search_dict(source, path[1:])
                if val is not None:
                    return self._expand_env_vars(val)

        return None

    def get_all(self) -> Dict:
        """Get all configuration as dictionary."""
        return self._expand_env_vars(self._config)

    def read_config(self) -> "ConfigReader":
        """
        Read configuration files.

        Returns:
            Self for method chaining

        Raises:
            FileNotFoundError: If environment-specific config file is not found
        """
        cfg = {}
        self._config = {}

        # Read default config first
        default_config_path = self._get_default_config_file()
        if os.path.exists(default_config_path):
            logger.info(f"[CONFIG] Reading default config: {default_config_path}")
            with open(default_config_path, "rb") as fp:
                cfg.update(tomllib.load(fp))
        else:
            logger.warning(f"[CONFIG] Default config not found: {default_config_path}")

        # Read environment-specific config
        env_config_path = self._get_env_config_file()
        if os.path.exists(env_config_path):
            logger.info(f"[CONFIG] Reading environment config: {env_config_path}")
            with open(env_config_path, "rb") as fp:
                env_cfg = tomllib.load(fp)
                self._merge_dicts(env_cfg, cfg)
        else:
            logger.warning(f"[CONFIG] Environment config not found: {env_config_path}")

        self._merge_dicts(cfg, self._config)

        return self

    def get_or_default(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with default fallback.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        val = self.get(key)
        return val if val is not None else default


# Global config reader instance
_config_reader = None


def get_config() -> ConfigReader:
    """
    Get global configuration reader instance.

    Returns:
        Configured ConfigReader instance
    """
    global _config_reader
    if _config_reader is None:
        _config_reader = ConfigReader().read_config()
    return _config_reader


# Convenience functions
def get_config_value(key: str, default: Any = None) -> Any:
    """
    Get configuration value using global config reader.

    Args:
        key: Configuration key
        default: Default value if key not found

    Returns:
        Configuration value or default
    """
    return get_config().get_or_default(key, default)

