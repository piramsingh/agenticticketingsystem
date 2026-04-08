# Shim — re-exports from the new canonical location.
# Remove this file once all internal imports are updated.
from src.connectors.base import BaseConnector

__all__ = ["BaseConnector"]
