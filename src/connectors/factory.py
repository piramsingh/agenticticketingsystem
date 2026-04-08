"""
Connector factory — decorator registry pattern.

Usage:
    from src.connectors.factory import build as build_connector

    connector = build_connector(config.get_source_config())

To add a new tool, register a builder function:
    @register("mytool")
    def _build_mytool(cfg: ConnectorConfig) -> BaseConnector:
        return MyToolConnector(cfg.base_url, cfg.auth.token.get_secret_value(), cfg.project)
"""
from typing import Callable, Dict

from .base import BaseConnector
from ..config import ConnectorConfig


_REGISTRY: Dict[str, Callable[[ConnectorConfig], BaseConnector]] = {}


def register(tool_type: str) -> Callable:
    """
    Decorator that registers a builder function for a given tool_type string.

    Args:
        tool_type: The value of ConnectorConfig.tool_type this builder handles.

    Returns:
        The decorated function (unchanged).

    Example:
        @register("jira")
        def _build_jira(cfg: ConnectorConfig) -> BaseConnector: ...
    """
    def decorator(fn: Callable) -> Callable:
        _REGISTRY[tool_type] = fn
        return fn
    return decorator


def build(config: ConnectorConfig) -> BaseConnector:
    """
    Instantiate the right connector for the given ConnectorConfig.

    Args:
        config: A validated ConnectorConfig from AppConfig.connectors.

    Returns:
        A fully initialised BaseConnector subclass instance.

    Raises:
        ValueError: If config.tool_type is not registered.
    """
    builder = _REGISTRY.get(config.tool_type)
    if builder is None:
        raise ValueError(
            f"Unknown tool_type '{config.tool_type}'. "
            f"Available: {sorted(_REGISTRY)}"
        )
    return builder(config)


# ── Built-in builders ─────────────────────────────────────────────────────────

@register("azure_devops")
def _build_azure(cfg: ConnectorConfig) -> BaseConnector:
    from .azure_devops import AzureDevOpsConnector
    return AzureDevOpsConnector(
        base_url=cfg.base_url,
        pat=cfg.auth.token.get_secret_value(),      # type: ignore[union-attr]
        project=cfg.project,
    )


@register("jira")
def _build_jira(cfg: ConnectorConfig) -> BaseConnector:
    from .jira import JiraConnector
    return JiraConnector(
        base_url=cfg.base_url,
        email=cfg.auth.email,                       # type: ignore[union-attr]
        api_token=cfg.auth.token.get_secret_value(), # type: ignore[union-attr]
        project=cfg.project,
    )


@register("jama")
def _build_jama(cfg: ConnectorConfig) -> BaseConnector:
    from .jama import JamaConnector
    project_id = int(cfg.extra.get("project_id", cfg.project))
    return JamaConnector(
        base_url=cfg.base_url,
        username=cfg.auth.username,                 # type: ignore[union-attr]
        password=cfg.auth.password.get_secret_value(), # type: ignore[union-attr]
        project_id=project_id,
    )
