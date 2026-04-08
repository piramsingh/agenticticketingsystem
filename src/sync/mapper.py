"""
Bidirectional field and status mapping between any two connectors.

Previously hardwired to Jama↔target; now fully tool-agnostic.
Direction strings are "source" and "target" throughout.
"""
import logging
from typing import Any, Dict, Optional

from ..config import AppConfig
from ..models.ticket import TargetItem

logger = logging.getLogger(__name__)


class FieldMapper:
    """
    Transforms fields between source and target connectors using the
    field_mappings and status_mappings defined in AppConfig.

    Field mappings are keyed by the source-side field name and map to the
    target-side field name (e.g. {"name": "summary", "status": "state"}).
    Status mappings are a list of {source, target} pairs.
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.status_mappings = config.status_mappings
        self.field_mappings = config.field_mappings

    # ── Source → Target ───────────────────────────────────────────────────────

    def map_source_to_target(self, source_item: TargetItem) -> Dict[str, Any]:
        """
        Transform a TargetItem from the source connector into a field dict
        suitable for the target connector's create/update methods.

        Args:
            source_item: Item retrieved from the source connector.

        Returns:
            Dict of target-side field names → values.
        """
        source_data = {
            "name":        source_item.title,
            "description": source_item.description,
            "priority":    source_item.priority,
            "status":      source_item.status,
        }

        target_fields: Dict[str, Any] = {}
        for source_field, source_value in source_data.items():
            target_field = self.config.get_field_mapping("source", source_field)
            if target_field is None:
                logger.warning("No mapping for source field '%s', skipping", source_field)
                continue
            if source_field == "status":
                mapped = self._map_status(source_value, "source_to_target")
                target_fields[target_field] = mapped if mapped is not None else source_value
            else:
                target_fields[target_field] = source_value

        # Pass through any extra custom fields the source exposed
        for field_name, field_value in source_item.fields.items():
            target_field = self.config.get_field_mapping("source", field_name)
            if target_field and target_field not in target_fields:
                target_fields[target_field] = field_value

        logger.debug("Mapped source item %s → target fields: %s", source_item.item_id, target_fields)
        return target_fields

    # ── Target → Source ───────────────────────────────────────────────────────

    def map_target_to_source(self, target_item: TargetItem) -> Dict[str, Any]:
        """
        Transform a TargetItem from the target connector back into a field dict
        for the source connector's update method.

        Args:
            target_item: Item retrieved from the target connector.

        Returns:
            Dict of source-side field names → values.
        """
        target_data = {
            "title":       target_item.title,
            "description": target_item.description,
            "priority":    target_item.priority,
            "status":      target_item.status,
        }

        source_fields: Dict[str, Any] = {}
        for attr_name, attr_value in target_data.items():
            # Find the source field that maps to this target attribute
            source_field: Optional[str] = None
            is_status = False
            for src_f, tgt_f in self.field_mappings.items():
                if tgt_f == attr_name or (attr_name == "status" and tgt_f in ("state", "status")):
                    source_field = src_f
                    is_status = (src_f == "status")
                    break

            if source_field is None:
                logger.warning("No mapping for target attribute '%s', skipping", attr_name)
                continue

            if is_status:
                mapped = self._map_status(attr_value, "target_to_source")
                source_fields[source_field] = mapped if mapped is not None else attr_value
            else:
                source_fields[source_field] = attr_value

        # Pass through extra custom fields
        for field_name, field_value in target_item.fields.items():
            source_field = self.config.get_field_mapping("target", field_name)
            if source_field and source_field not in source_fields:
                source_fields[source_field] = field_value

        logger.debug("Mapped target item %s → source fields: %s", target_item.item_id, source_fields)
        return source_fields

    # ── Status mapping ────────────────────────────────────────────────────────

    def map_status(self, status: str, direction: str) -> Optional[str]:
        """
        Public status mapper — delegates to internal helper.

        Args:
            status:    Status string to translate.
            direction: "source_to_target" or "target_to_source".

        Returns:
            Mapped status string or None.
        """
        return self._map_status(status, direction)

    def _map_status(self, status: str, direction: str) -> Optional[str]:
        if direction == "source_to_target":
            mapped = self.config.get_status_mapping("source_to_target", status)
        elif direction == "target_to_source":
            mapped = self.config.get_status_mapping("target_to_source", status)
        else:
            logger.error("Invalid status mapping direction: %s", direction)
            return None

        if mapped is None:
            logger.warning("No status mapping for '%s' in direction '%s'", status, direction)
        return mapped

    # ── Backwards-compat aliases ──────────────────────────────────────────────
    # Old code called map_jama_to_target / map_target_to_jama.

    def map_jama_to_target(self, source_item: TargetItem) -> Dict[str, Any]:
        """Deprecated — use map_source_to_target."""
        return self.map_source_to_target(source_item)

    def map_target_to_jama(self, target_item: TargetItem) -> Dict[str, Any]:
        """Deprecated — use map_target_to_source."""
        return self.map_target_to_source(target_item)
