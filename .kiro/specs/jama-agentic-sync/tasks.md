# Implementation Plan

- [x] 1. Set up project structure and dependencies
  - Create directory structure following the design (src/, tests/, models/, clients/, sync/, api/)
  - Create pyproject.toml with all required dependencies (fastapi, uvicorn, sqlalchemy, pydantic, pyyaml, httpx, apscheduler, py-jama-rest-client, pytest)
  - Create README.md with project overview and setup instructions
  - Create config.example.yaml with sample configuration
  - _Requirements: 11.6_

- [x] 2. Implement configuration management
  - Create src/config.py with Pydantic models for all configuration sections (JamaConfig, TargetToolConfig, StatusMappingItem, SyncConfig, AppConfig)
  - Implement load_config() function with YAML parsing and environment variable substitution
  - Implement get_status_mapping() and get_field_mapping() helper methods
  - Add configuration validation with clear error messages
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9_

- [x] 3. Implement database layer
  - Create src/database.py with SQLAlchemy engine setup for SQLite
  - Implement get_engine(), init_db(), and get_session() functions
  - Create src/models/mapping.py with SyncMapping SQLAlchemy model including all fields and indexes
  - Create src/models/action_log.py with ActionLog SQLAlchemy model with immutability enforcement
  - Add database schema constraints (CHECK constraints, UNIQUE constraints, indexes)
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

- [x] 4. Implement shared data models
  - Create dataclasses for JamaItem, Activity, CreateItemResult, TargetItem, and WebhookEvent
  - Add to_dict() methods for serialization
  - Ensure all models include necessary fields per design
  - _Requirements: 2.1, 2.2, 2.3_

- [ ] 5. Implement Jama client wrapper
  - Create src/clients/jama_client.py wrapping py-jama-rest-client
  - Implement token bucket rate limiter (10 requests/second)
  - Implement get_activities() method with project filtering
  - Implement get_item() method with rate limiting
  - Implement update_item() method with exponential backoff on 429 responses
  - Add _handle_rate_limit() method with backoff logic (1s, 2s, 4s, 8s, 16s, 32s, 60s max)
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 12.6, 12.7_

- [ ] 6. Implement connector base class and Azure DevOps connector
  - Create src/clients/connectors/base.py with BaseConnector abstract class
  - Define abstract methods: create_item(), update_item(), get_item(), parse_webhook(), validate_connection()
  - Create src/clients/connectors/azure_devops.py implementing BaseConnector
  - Implement create_item() using Azure DevOps REST API (POST work items)
  - Implement update_item() using PATCH with JSON Patch format
  - Implement get_item() to retrieve work item details
  - Implement parse_webhook() to handle workitem.updated and workitem.created events
  - Implement validate_connection() to test API connectivity
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 2.6_

- [ ] 7. Implement field and status mapper
  - Create src/sync/mapper.py with FieldMapper class
  - Implement map_jama_to_target() to transform Jama fields to target tool format
  - Implement map_target_to_jama() to transform target tool fields to Jama format
  - Implement map_status() with bidirectional status mapping using configuration
  - Handle missing fields gracefully with logging
  - _Requirements: 2.2, 4.1_

- [ ] 8. Implement sync engine core logic
  - Create src/sync/engine.py with SyncEngine class
  - Implement process_jama_update() to handle new/updated Jama items
  - Implement process_target_update() to handle webhook events from target tools
  - Implement detect_conflict() to check if both sides modified since last sync
  - Implement handle_conflict() to flag conflicts and log details without overwriting
  - Implement log_action() to create immutable ActionLog entries
  - Add logic to check sync direction configuration before syncing
  - _Requirements: 2.1, 2.3, 2.4, 2.5, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.4_

- [ ] 9. Implement Jama poller
  - Create src/sync/poller.py with JamaPoller class
  - Implement poll() method to query Jama activities since last poll time
  - Filter activities for ITEM_CREATED and ITEM_UPDATED events
  - Pass relevant activities to SyncEngine.process_jama_update()
  - Update last_poll_time after successful poll
  - Handle polling errors gracefully and continue on next cycle
  - _Requirements: 1.1, 1.2, 1.3, 1.6, 12.2_

- [ ] 10. Implement API endpoints
  - Create src/api/webhooks.py with POST /webhooks/{tool_name} endpoint
  - Create src/api/health.py with GET /health endpoint returning status, last_poll, conflicts, errors
  - Create src/api/mappings.py with GET /mappings (paginated) and GET /mappings/{jama_item_id} endpoints
  - Create src/api/logs.py with GET /logs endpoint supporting filters (date range, action, result)
  - Create POST /sync/trigger endpoint in webhooks.py for manual sync triggering
  - Add proper error handling and HTTP status codes for all endpoints
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 5.6, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 12.4_

- [ ] 11. Implement main FastAPI application
  - Create src/main.py with FastAPI app initialization
  - Implement lifespan context manager for startup/shutdown
  - Initialize database and load configuration on startup
  - Set up APScheduler with polling job using configured interval
  - Mount all API routers (webhooks, health, mappings, logs)
  - Add global exception handler for unexpected errors
  - _Requirements: 1.1, 7.1, 10.1, 12.5_

- [ ] 12. Implement error handling and resilience
  - Add comprehensive error handling in Jama client for all error categories
  - Add error handling in connectors with appropriate retry logic
  - Implement exponential backoff for transient errors
  - Add error logging with full context throughout the application
  - Ensure sync engine marks mappings as "error" on failures
  - Add try-except blocks in poller to prevent crashes
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 2.5_

- [ ] 13. Create Docker packaging
  - Create Dockerfile using Python 3.11-slim base image
  - Configure WORKDIR, copy pyproject.toml, install dependencies
  - Copy src/ directory and set up uvicorn CMD
  - Expose port 8000
  - Create docker-compose.yaml for local development with volume mounts
  - Add health check configuration to Docker setup
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [ ]* 14. Write unit tests for sync engine
  - Test process_jama_update with new item creates mapping and target ticket
  - Test process_jama_update with existing item updates target
  - Test process_target_update updates Jama item
  - Test conflict detection returns true when both sides modified
  - Test conflict detection returns false when only one side modified
  - Test handle_conflict flags mapping and logs without overwriting
  - Test log_action creates immutable ActionLog entries
  - Test sync direction configuration (jama_to_target, target_to_jama, bidirectional)
  - _Requirements: 2.1, 2.3, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 6.1_

- [ ]* 15. Write unit tests for field mapper
  - Test map_jama_to_target transforms all configured fields correctly
  - Test map_target_to_jama transforms all configured fields correctly
  - Test map_status handles bidirectional status mapping
  - Test missing field handling logs warning and continues
  - Test invalid status handling with unmapped statuses
  - _Requirements: 2.2, 4.1_

- [ ]* 16. Write unit tests for conflict detection
  - Test no conflict when only Jama modified since last sync
  - Test no conflict when only target modified since last sync
  - Test conflict detected when both modified since last sync
  - Test conflict logging includes both states in payload
  - Test mapping sync_status set to "conflict"
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ]* 17. Write unit tests for webhooks
  - Test Azure DevOps webhook parsing extracts correct fields
  - Test webhook processing calls sync engine correctly
  - Test invalid webhook payload returns appropriate error
  - Test webhook with unknown item ID logs warning and returns 200
  - _Requirements: 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ]* 18. Write integration tests
  - Test end-to-end Jama to target flow (poll → create ticket → store mapping → log)
  - Test end-to-end target to Jama flow (webhook → update Jama → update mapping → log)
  - Test conflict scenario (both sides modified → conflict flagged → no updates)
  - Test manual sync trigger endpoint
  - _Requirements: 2.1, 2.3, 2.4, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 8.5, 8.6_
