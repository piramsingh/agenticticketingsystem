"""
Configuration management — tool-agnostic schema with Pydantic validation.

New schema uses a list of ConnectorConfig entries (one per tool) with a
SyncConfig that references them by name. Auth is a discriminated union so
each tool type can declare its own credential format.

Legacy aliases (JamaConfig, TargetToolConfig) are kept at the bottom so
existing scripts using the old config format don't immediately break.
"""
import os
import re
from typing import Any, Dict, List, Literal, Optional, Union
from pathlib import Path

import yaml
from pydantic import BaseModel, SecretStr, field_validator, model_validator


# ── Auth models (one per credential style) ────────────────────────────────────

class PatAuth(BaseModel):
    """Personal Access Token — used by Azure DevOps."""
    type: Literal["pat"] = "pat"
    token: SecretStr


class ApiTokenAuth(BaseModel):
    """Email + API token — used by Jira Cloud."""
    type: Literal["api_token"] = "api_token"
    email: str
    token: SecretStr


class BasicAuth(BaseModel):
    """Username + password — used by Jama Connect."""
    type: Literal["basic"] = "basic"
    username: str
    password: SecretStr


# Discriminated union — Pydantic picks the right auth model from the "type" field
AnyAuth = Union[PatAuth, ApiTokenAuth, BasicAuth]


# ── Per-connector config ───────────────────────────────────────────────────────

class ConnectorConfig(BaseModel):
    """
    Configuration for one connector instance.

    Example:
        name: jira-prod
        tool_type: jira
        base_url: https://myco.atlassian.net
        project: MYPROJ
        auth:
          type: api_token
          email: me@myco.com
          token: ${JIRA_TOKEN}
    """
    name: str           # logical label used in sync.source / sync.target
    tool_type: str      # "azure_devops" | "jira" | "jama"
    base_url: str
    project: str        # project key, name, or ID depending on tool
    auth: AnyAuth
    extra: Dict[str, str] = {}   # tool-specific overrides (e.g. jama project_id)

    @field_validator('base_url')
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        if not v.startswith(('http://', 'https://')):
            raise ValueError('base_url must start with http:// or https://')
        return v.rstrip('/')


# ── Sync config ───────────────────────────────────────────────────────────────

class StatusMappingItem(BaseModel):
    """Maps a status value from source tool to target tool."""
    source: str
    target: str


class SyncConfig(BaseModel):
    """Controls sync behaviour between two named connectors."""
    source: str     # name of the source ConnectorConfig
    target: str     # name of the target ConnectorConfig
    polling_interval: int = 60
    direction: Literal[
        "source_to_target", "target_to_source", "bidirectional"
    ] = "bidirectional"

    @field_validator('polling_interval')
    @classmethod
    def validate_interval(cls, v: int) -> int:
        if v < 10:
            raise ValueError('polling_interval must be at least 10 seconds')
        return v


# ── Root config ───────────────────────────────────────────────────────────────

class AppConfig(BaseModel):
    """Root configuration model — validated on load."""
    connectors: List[ConnectorConfig]
    sync: SyncConfig
    status_mappings: List[StatusMappingItem] = []
    field_mappings: Dict[str, str] = {}

    @model_validator(mode='after')
    def validate_sync_references(self) -> 'AppConfig':
        names = {c.name for c in self.connectors}
        if self.sync.source not in names:
            raise ValueError(
                f"sync.source '{self.sync.source}' not found in connectors. "
                f"Available: {sorted(names)}"
            )
        if self.sync.target not in names:
            raise ValueError(
                f"sync.target '{self.sync.target}' not found in connectors. "
                f"Available: {sorted(names)}"
            )
        return self

    def get_connector_config(self, name: str) -> ConnectorConfig:
        for c in self.connectors:
            if c.name == name:
                return c
        raise KeyError(f"No connector named '{name}'")

    def get_source_config(self) -> ConnectorConfig:
        return self.get_connector_config(self.sync.source)

    def get_target_config(self) -> ConnectorConfig:
        return self.get_connector_config(self.sync.target)

    def get_status_mapping(self, direction: str, status: str) -> Optional[str]:
        """
        Resolve a status value across tools.

        Args:
            direction: "source_to_target" or "target_to_source"
            status: Status value to map

        Returns:
            Mapped status string, or None if not configured
        """
        for m in self.status_mappings:
            if direction == "source_to_target" and m.source == status:
                return m.target
            if direction == "target_to_source" and m.target == status:
                return m.source
        return None

    def get_field_mapping(self, direction: str, field: str) -> Optional[str]:
        """
        Resolve a field name across tools.

        Args:
            direction: "source" (source→target lookup) or "target" (reverse)
            field: Field name to map

        Returns:
            Mapped field name, or None if not configured
        """
        if direction == 'source':
            return self.field_mappings.get(field)
        elif direction == 'target':
            for src_f, tgt_f in self.field_mappings.items():
                if tgt_f == field:
                    return src_f
        return None


# ── Loader ────────────────────────────────────────────────────────────────────

def _substitute_env_vars(data: Any) -> Any:
    """Recursively replace ${VAR_NAME} with environment variable values."""
    if isinstance(data, dict):
        return {k: _substitute_env_vars(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_substitute_env_vars(item) for item in data]
    elif isinstance(data, str):
        for var_name in re.findall(r'\$\{([^}]+)\}', data):
            env_value = os.getenv(var_name)
            if env_value is None:
                raise ValueError(f"Environment variable '{var_name}' is not set")
            data = data.replace(f'${{{var_name}}}', env_value)
        return data
    return data


def load_config(path: str = "config.yaml") -> AppConfig:
    """
    Load and validate a YAML configuration file.

    Supports ${ENV_VAR} substitution in any string value.

    Args:
        path: Path to the YAML config file

    Returns:
        Validated AppConfig instance

    Raises:
        FileNotFoundError: Config file does not exist
        ValueError: Config is invalid or references unset env vars
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        with open(config_path) as f:
            raw = yaml.safe_load(f)
        data = _substitute_env_vars(raw)
        return AppConfig(**data)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file: {e}")
    except Exception as e:
        raise ValueError(f"Config validation failed: {e}")


# ── Legacy aliases (backwards compatibility) ───────────────────────────────────
# These allow old code that references JamaConfig / TargetToolConfig to keep
# working. They will be removed in a future cleanup pass.

class JamaConfig(BaseModel):
    """Deprecated — use ConnectorConfig with tool_type='jama' instead."""
    base_url: str
    username: str
    password: SecretStr
    project_id: int

    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if not v.startswith(('http://', 'https://')):
            raise ValueError('base_url must start with http:// or https://')
        return v.rstrip('/')


class TargetToolConfig(BaseModel):
    """Deprecated — use ConnectorConfig instead."""
    tool_type: Literal["azure_devops", "gitlab", "jira"]
    base_url: str
    pat: SecretStr
    project: str

    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if not v.startswith(('http://', 'https://')):
            raise ValueError('base_url must start with http:// or https://')
        return v.rstrip('/')
