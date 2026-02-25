# Requirements Document

## Introduction

This document outlines the requirements for a Python-based agentic sync layer that connects Jama Connect (a requirements management platform used by regulated engineering teams) with external ticket management tools like Azure DevOps, GitLab, or Jira. The system provides bidirectional synchronization between Jama Connect and target tools, eliminating manual ticket creation and status updates while maintaining a comprehensive audit trail for regulatory compliance (FDA 21 CFR Part 11).

The sync agent polls Jama Connect's activity stream for changes, automatically creates corresponding tickets in target tools, and receives webhook notifications from target tools to update Jama items. All sync actions are logged in an append-only audit log for compliance purposes.

## Requirements

### Requirement 1: Jama Activity Polling

**User Story:** As a regulated engineering team, I want the system to automatically detect new and updated requirements in Jama Connect, so that I don't have to manually monitor Jama for changes.

#### Acceptance Criteria

1. WHEN the system is running THEN it SHALL poll Jama Connect's activity stream endpoint (GET /activities?project={id}) every 60 seconds by default
2. WHEN polling Jama THEN the system SHALL filter activities for the configured project ID
3. WHEN a new requirement item is detected in Jama THEN the system SHALL extract the item ID, type, name, description, priority, and status
4. WHEN Jama API returns a 429 rate limit response THEN the system SHALL implement exponential backoff and retry
5. IF the Jama API rate limit is 10 requests/second with a 100-request queue THEN the system SHALL respect these limits in all API calls
6. WHEN polling fails due to network or API errors THEN the system SHALL log the error and continue polling on the next scheduled interval

### Requirement 2: Automatic Ticket Creation in Target Tools

**User Story:** As a development team member, I want tickets to be automatically created in my project management tool when new requirements are added to Jama, so that I can start working on them without manual ticket creation.

#### Acceptance Criteria

1. WHEN a new requirement is detected in Jama AND no mapping exists for that item THEN the system SHALL create a corresponding ticket in the configured target tool
2. WHEN creating a ticket in the target tool THEN the system SHALL map Jama fields to target tool fields according to the configuration (name→title, description→description, priority→priority, status→status)
3. WHEN a ticket is successfully created in the target tool THEN the system SHALL store a mapping record with jama_item_id, target_tool, target_item_id, target_item_url, and timestamp
4. WHEN a ticket is successfully created THEN the system SHALL log the action to the ActionLog table with action type "create_ticket", full payload, and result status
5. IF ticket creation fails THEN the system SHALL log the error with details and mark the sync_status as "error" in the mapping table
6. WHEN creating a ticket THEN the system SHALL use the abstract connector interface to support multiple target tools

### Requirement 3: Webhook Reception from Target Tools

**User Story:** As a system administrator, I want the sync agent to receive real-time notifications from target tools when tickets are updated, so that Jama stays current without constant polling of the target tool.

#### Acceptance Criteria

1. WHEN the system starts THEN it SHALL expose a FastAPI webhook endpoint at POST /webhooks/{tool_name}
2. WHEN a webhook is received from a target tool THEN the system SHALL validate the tool_name parameter against supported connectors
3. WHEN a valid webhook is received THEN the system SHALL parse the payload to extract the target item ID and updated fields
4. WHEN a webhook contains a ticket status change THEN the system SHALL look up the corresponding Jama item using the mapping table
5. IF no mapping exists for the target item ID THEN the system SHALL log a warning and return HTTP 200 (to prevent webhook retries)
6. WHEN webhook processing fails THEN the system SHALL log the error and return an appropriate HTTP error code

### Requirement 4: Bidirectional Status Synchronization

**User Story:** As a requirements manager, I want Jama item statuses to automatically update when corresponding tickets are closed in the target tool, so that I have accurate traceability without manual updates.

#### Acceptance Criteria

1. WHEN a target tool ticket status changes via webhook THEN the system SHALL map the target status to the corresponding Jama status using the configuration
2. WHEN a Jama status mapping is found THEN the system SHALL update the Jama item via PUT /items/{id} API call
3. WHEN a Jama item is successfully updated THEN the system SHALL update the last_synced_at timestamp in the mapping table
4. WHEN a Jama item is successfully updated THEN the system SHALL log the action to the ActionLog table with action type "update_status"
5. WHEN a Jama item is updated in Jama (detected via polling) AND a mapping exists THEN the system SHALL update the corresponding target tool ticket status
6. IF sync direction is configured as "jama_to_target" THEN the system SHALL only sync from Jama to target tool
7. IF sync direction is configured as "target_to_jama" THEN the system SHALL only sync from target tool to Jama
8. IF sync direction is configured as "bidirectional" THEN the system SHALL sync in both directions

### Requirement 5: Conflict Detection and Handling

**User Story:** As a system administrator, I want the system to detect when both Jama and the target tool have been updated between sync cycles, so that I can manually resolve conflicts without data loss.

#### Acceptance Criteria

1. WHEN the system detects an update in Jama for an item AND the target tool item has also been updated since last sync THEN the system SHALL flag the mapping as "conflict"
2. WHEN a conflict is detected THEN the system SHALL NOT overwrite either Jama or the target tool
3. WHEN a conflict is detected THEN the system SHALL log the conflict to the ActionLog table with action type "sync_error" and result "conflict"
4. WHEN a conflict is detected THEN the system SHALL include both the Jama and target tool states in the error_detail field
5. WHEN a mapping is in "conflict" status THEN the system SHALL skip automatic sync for that mapping until manually resolved
6. WHEN querying the health endpoint THEN the system SHALL include the count of items in conflict status

### Requirement 6: Regulatory Compliance Audit Trail

**User Story:** As a quality assurance manager in a regulated industry, I want every sync action to be logged in an immutable audit trail, so that I can demonstrate compliance with FDA 21 CFR Part 11 requirements.

#### Acceptance Criteria

1. WHEN any sync action occurs THEN the system SHALL create an entry in the ActionLog table
2. WHEN creating an ActionLog entry THEN the system SHALL include timestamp, action type, source_tool, source_item_id, target_tool, target_item_id, full payload (JSON), result status, and error_detail if applicable
3. WHEN the ActionLog table is created THEN it SHALL be configured as append-only with no update or delete operations allowed
4. WHEN an ActionLog entry is created THEN it SHALL include the complete before and after state in the payload field
5. IF the database schema allows updates or deletes on ActionLog THEN the system SHALL prevent them at the application layer
6. WHEN querying logs via GET /logs THEN the system SHALL support filtering by date range, action type, and result status

### Requirement 7: Configuration Management

**User Story:** As a system administrator, I want to configure sync behavior, field mappings, and tool connections via a YAML file, so that I can adapt the system to different environments without code changes.

#### Acceptance Criteria

1. WHEN the system starts THEN it SHALL load configuration from a config.yaml file
2. WHEN loading configuration THEN the system SHALL validate all settings using Pydantic models
3. IF configuration validation fails THEN the system SHALL log detailed error messages and refuse to start
4. WHEN configuration is loaded THEN it SHALL include Jama connection settings (base URL, credentials, project ID)
5. WHEN configuration is loaded THEN it SHALL include target tool connection settings (base URL, credentials, project/repo ID)
6. WHEN configuration is loaded THEN it SHALL include bidirectional status mapping (Jama status ↔ target tool status)
7. WHEN configuration is loaded THEN it SHALL include field mapping definitions (minimum: name, description, priority, status)
8. WHEN configuration is loaded THEN it SHALL include polling interval (default 60 seconds)
9. WHEN configuration is loaded THEN it SHALL include sync direction setting (jama_to_target, target_to_jama, or bidirectional)

### Requirement 8: REST API for Monitoring and Management

**User Story:** As a system administrator, I want REST API endpoints to monitor sync status and query mappings, so that I can troubleshoot issues and verify system health.

#### Acceptance Criteria

1. WHEN the system is running THEN it SHALL expose GET /health endpoint returning sync status, last poll time, and error count
2. WHEN the system is running THEN it SHALL expose GET /mappings endpoint with pagination support
3. WHEN the system is running THEN it SHALL expose GET /mappings/{jama_item_id} endpoint returning the mapping for a specific Jama item
4. WHEN the system is running THEN it SHALL expose GET /logs endpoint with query filters for date range, action type, and status
5. WHEN the system is running THEN it SHALL expose POST /sync/trigger endpoint for manually triggering a sync cycle
6. WHEN POST /sync/trigger is called THEN the system SHALL immediately poll Jama and process any pending updates
7. WHEN any API endpoint is called THEN the system SHALL return appropriate HTTP status codes and error messages

### Requirement 9: Extensible Connector Architecture

**User Story:** As a developer, I want the target tool connector to be implemented as an abstract base class, so that I can easily add support for new tools like GitLab or Jira without modifying core sync logic.

#### Acceptance Criteria

1. WHEN designing the connector architecture THEN the system SHALL define an abstract base class for target tool connectors
2. WHEN the abstract base class is defined THEN it SHALL include methods for create_item, update_item, get_item, and parse_webhook
3. WHEN implementing a new connector THEN it SHALL inherit from the base class and implement all required methods
4. WHEN the system starts THEN it SHALL support at least one reference implementation (Azure DevOps Server connector)
5. WHEN a sync operation occurs THEN the system SHALL use the connector interface without knowledge of the specific target tool
6. WHEN adding a new connector THEN it SHALL NOT require changes to the sync engine or core logic

### Requirement 10: Data Persistence and Schema

**User Story:** As a system operator, I want sync mappings and audit logs to be stored in a local SQLite database, so that the system can track relationships and maintain history without external dependencies.

#### Acceptance Criteria

1. WHEN the system starts THEN it SHALL create or connect to a SQLite database
2. WHEN the database is initialized THEN it SHALL create a SyncMapping table with columns: id, jama_item_id, jama_project_id, jama_item_type, target_tool, target_item_id, target_item_url, last_synced_at, sync_status
3. WHEN the database is initialized THEN it SHALL create an ActionLog table with columns: id, timestamp, action, source_tool, source_item_id, target_tool, target_item_id, payload (JSON), result, error_detail
4. WHEN using the database THEN the system SHALL use SQLAlchemy as the ORM layer
5. WHEN a sync_status is set THEN it SHALL be one of: active, conflict, or error
6. WHEN an ActionLog result is set THEN it SHALL be one of: success, failed, or conflict
7. WHEN the database schema is created THEN the ActionLog table SHALL have constraints preventing updates and deletes

### Requirement 11: Deployment and Packaging

**User Story:** As a DevOps engineer, I want the sync agent to be packaged as a Docker container, so that I can deploy it consistently across different environments.

#### Acceptance Criteria

1. WHEN building the project THEN it SHALL include a Dockerfile for containerization
2. WHEN the Docker container is built THEN it SHALL use Python 3.11 or later as the base image
3. WHEN the Docker container runs THEN it SHALL start the FastAPI application and scheduler
4. WHEN the Docker container is configured THEN it SHALL support mounting config.yaml as a volume
5. WHEN the Docker container is configured THEN it SHALL support mounting the SQLite database directory as a volume for persistence
6. WHEN the project is packaged THEN it SHALL use pyproject.toml for dependency management

### Requirement 12: Error Handling and Resilience

**User Story:** As a system administrator, I want the sync agent to handle errors gracefully and continue operating, so that temporary failures don't require manual intervention.

#### Acceptance Criteria

1. WHEN any API call fails THEN the system SHALL log the error with full context
2. WHEN a Jama API call fails THEN the system SHALL continue with the next scheduled poll
3. WHEN a target tool API call fails THEN the system SHALL mark the mapping as "error" and log details
4. WHEN a webhook processing fails THEN the system SHALL return an appropriate HTTP error code and log the failure
5. WHEN the system encounters an unexpected exception THEN it SHALL log the stack trace and continue operating
6. WHEN Jama API returns 429 rate limit THEN the system SHALL implement exponential backoff starting at 1 second, doubling up to 60 seconds
7. WHEN exponential backoff reaches maximum wait time THEN the system SHALL log a warning and skip the current sync cycle
