"""Configuration management with Pydantic models and YAML loading"""
import os
import re
from typing import Dict, List, Literal
from pathlib import Path

import yaml
from pydantic import BaseModel, SecretStr, field_validator


class JamaConfig(BaseModel):
    """Jama Connect connection settings"""
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
    """Target tool connection settings"""
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


class StatusMappingItem(BaseModel):
    """Bidirectional status mapping between Jama and target tool"""
    jama: str
    target: str


class SyncConfig(BaseModel):
    """Sync behavior settings"""
    polling_interval: int = 60
    direction: Literal["jama_to_target", "target_to_jama", "bidirectional"] = "bidirectional"

    @field_validator('polling_interval')
    @classmethod
    def validate_polling_interval(cls, v: int) -> int:
        if v < 10:
            raise ValueError('polling_interval must be at least 10 seconds')
        return v


class AppConfig(BaseModel):
    """Root configuration model combining all settings"""
    jama: JamaConfig
    target_tool: TargetToolConfig
    sync: SyncConfig
    status_mappings: List[StatusMappingItem]
    field_mappings: Dict[str, str]

    def get_status_mapping(self, source: str, status: str) -> str | None:
        """
        Resolve status mapping from source system to target system.
        
        Args:
            source: Source system ('jama' or 'target')
            status: Status value to map
            
        Returns:
            Mapped status value or None if not found
        """
        if source == 'jama':
            for mapping in self.status_mappings:
                if mapping.jama == status:
                    return mapping.target
        elif source == 'target':
            for mapping in self.status_mappings:
                if mapping.target == status:
                    return mapping.jama
        return None

    def get_field_mapping(self, source: str, field: str) -> str | None:
        """
        Resolve field mapping from source system to target system.
        
        Args:
            source: Source system ('jama' or 'target')
            field: Field name to map
            
        Returns:
            Mapped field name or None if not found
        """
        if source == 'jama':
            return self.field_mappings.get(field)
        elif source == 'target':
            # Reverse lookup for target to jama
            for jama_field, target_field in self.field_mappings.items():
                if target_field == field:
                    return jama_field
        return None


def _substitute_env_vars(data: dict) -> dict:
    """
    Recursively substitute environment variables in configuration.
    Supports ${VAR_NAME} syntax.
    
    Args:
        data: Configuration dictionary
        
    Returns:
        Configuration with environment variables substituted
    """
    if isinstance(data, dict):
        return {k: _substitute_env_vars(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_substitute_env_vars(item) for item in data]
    elif isinstance(data, str):
        # Match ${VAR_NAME} pattern
        pattern = r'\$\{([^}]+)\}'
        matches = re.findall(pattern, data)
        for var_name in matches:
            env_value = os.getenv(var_name)
            if env_value is None:
                raise ValueError(f"Environment variable {var_name} not set")
            data = data.replace(f"${{{var_name}}}", env_value)
        return data
    else:
        return data


def load_config(path: str = "config.yaml") -> AppConfig:
    """
    Load and validate YAML configuration file.
    
    Args:
        path: Path to configuration file
        
    Returns:
        Validated AppConfig instance
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If configuration is invalid
    """
    config_path = Path(path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    
    try:
        with open(config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
        
        # Substitute environment variables
        config_data = _substitute_env_vars(raw_config)
        
        # Validate with Pydantic
        config = AppConfig(**config_data)
        
        return config
        
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in configuration file: {e}")
    except Exception as e:
        raise ValueError(f"Configuration validation failed: {e}")
