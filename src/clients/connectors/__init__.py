# Shim — re-exports from the new canonical location.
# Remove this file once all internal imports are updated.
from src.connectors.base import BaseConnector
from src.connectors.azure_devops import AzureDevOpsConnector

__all__ = ["BaseConnector", "AzureDevOpsConnector"]
