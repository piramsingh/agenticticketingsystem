"""Field and status mapping between Jama Connect and target tools"""
import logging
from typing import Dict, Any

from src.config import AppConfig
from src.models.data_models import JamaItem, TargetItem


logger = logging.getLogger(__name__)


class FieldMapper:
    """
    Handles bidirectional field and status mapping between Jama Connect and target tools.
    
    This class transforms data between Jama's field structure and target tool field structures
    using the mappings defined in the configuration. It handles missing fields gracefully
    and logs warnings when fields cannot be mapped.
    """
    
    def __init__(self, config: AppConfig):
        """
        Initialize the field mapper with configuration.
        
        Args:
            config: Application configuration containing field and status mappings
        """
        self.config = config
        self.status_mappings = config.status_mappings
        self.field_mappings = config.field_mappings
    
    def map_jama_to_target(self, jama_item: JamaItem) -> Dict[str, Any]:
        """
        Transform Jama item fields to target tool format.
        
        Maps Jama field names to target tool field names according to the configuration.
        Handles missing fields gracefully by logging warnings and continuing.
        
        Args:
            jama_item: Jama item to transform
            
        Returns:
            Dictionary of target tool fields ready for API submission
        """
        target_fields = {}
        
        # Map standard fields using field_mappings configuration
        jama_data = {
            'name': jama_item.name,
            'description': jama_item.description,
            'priority': jama_item.priority,
            'status': jama_item.status
        }
        
        for jama_field, jama_value in jama_data.items():
            target_field = self.config.get_field_mapping('jama', jama_field)
            
            if target_field is None:
                logger.warning(
                    f"No mapping found for Jama field '{jama_field}', skipping"
                )
                continue
            
            # Special handling for status field - needs status mapping
            if jama_field == 'status':
                mapped_status = self.map_status(jama_value, 'jama_to_target')
                if mapped_status is not None:
                    target_fields[target_field] = mapped_status
                else:
                    logger.warning(
                        f"No status mapping found for Jama status '{jama_value}', "
                        f"using original value"
                    )
                    target_fields[target_field] = jama_value
            else:
                target_fields[target_field] = jama_value
        
        # Include any additional custom fields from jama_item.fields
        for field_name, field_value in jama_item.fields.items():
            target_field = self.config.get_field_mapping('jama', field_name)
            if target_field and target_field not in target_fields:
                target_fields[target_field] = field_value
        
        logger.debug(
            f"Mapped Jama item {jama_item.id} to target fields: {target_fields}"
        )
        
        return target_fields
    
    def map_target_to_jama(self, target_item: TargetItem) -> Dict[str, Any]:
        """
        Transform target tool fields to Jama format.
        
        Maps target tool field names to Jama field names according to the configuration.
        Handles missing fields gracefully by logging warnings and continuing.
        
        Args:
            target_item: Target tool item to transform
            
        Returns:
            Dictionary of Jama fields ready for API submission
        """
        jama_fields = {}
        
        # Build a mapping of TargetItem attribute names to their values
        # We need to map these to the configured target field names first
        target_item_data = {
            'title': target_item.title,
            'description': target_item.description,
            'priority': target_item.priority,
            'status': target_item.status
        }
        
        # For each TargetItem attribute, find its configured target field name,
        # then map that to the Jama field name
        for item_attr, item_value in target_item_data.items():
            # First, find what the configured target field name is for this attribute
            # For most cases, the attribute name matches the configured field name
            # But we need to handle the case where 'status' maps to 'state' in config
            
            # Find the Jama field that maps to this target attribute
            jama_field = None
            is_status_field = False
            
            for jama_f, target_f in self.field_mappings.items():
                # Check if this target field matches our attribute
                # Handle both direct matches and semantic matches (status/state)
                if target_f == item_attr or (item_attr == 'status' and target_f == 'state'):
                    jama_field = jama_f
                    is_status_field = (jama_f == 'status')
                    break
            
            if jama_field is None:
                logger.warning(
                    f"No mapping found for target attribute '{item_attr}', skipping"
                )
                continue
            
            # Special handling for status field - needs status mapping
            if is_status_field:
                mapped_status = self.map_status(item_value, 'target_to_jama')
                if mapped_status is not None:
                    jama_fields[jama_field] = mapped_status
                else:
                    logger.warning(
                        f"No status mapping found for target status '{item_value}', "
                        f"using original value"
                    )
                    jama_fields[jama_field] = item_value
            else:
                jama_fields[jama_field] = item_value
        
        # Include any additional custom fields from target_item.fields
        for field_name, field_value in target_item.fields.items():
            jama_field = self.config.get_field_mapping('target', field_name)
            if jama_field and jama_field not in jama_fields:
                jama_fields[jama_field] = field_value
        
        logger.debug(
            f"Mapped target item {target_item.item_id} to Jama fields: {jama_fields}"
        )
        
        return jama_fields
    
    def map_status(self, status: str, direction: str) -> str | None:
        """
        Map status between systems with direction awareness.
        
        Performs bidirectional status mapping using the status_mappings configuration.
        
        Args:
            status: Status value to map
            direction: Mapping direction ('jama_to_target' or 'target_to_jama')
            
        Returns:
            Mapped status value or None if no mapping found
        """
        if direction == 'jama_to_target':
            mapped = self.config.get_status_mapping('jama', status)
            if mapped is None:
                logger.warning(
                    f"No status mapping found for Jama status '{status}' "
                    f"in direction {direction}"
                )
            return mapped
        
        elif direction == 'target_to_jama':
            mapped = self.config.get_status_mapping('target', status)
            if mapped is None:
                logger.warning(
                    f"No status mapping found for target status '{status}' "
                    f"in direction {direction}"
                )
            return mapped
        
        else:
            logger.error(f"Invalid mapping direction: {direction}")
            return None
