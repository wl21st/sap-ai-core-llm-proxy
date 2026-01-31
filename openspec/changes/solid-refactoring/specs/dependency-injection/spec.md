## ADDED Requirements

### Requirement: Flask application context for configuration
The system SHALL store `ProxyConfig` and `ProxyGlobalContext` in Flask's application context (`current_app.config`) instead of module-level global variables.

#### Scenario: Configuration storage at startup
- **WHEN** the Flask application is created via `create_app()`
- **THEN** `proxy_config` SHALL be stored in `current_app.config['proxy_config']`
- **AND** `proxy_ctx` SHALL be stored in `current_app.config['proxy_ctx']`

#### Scenario: Configuration access in routes
- **WHEN** a blueprint route handler needs access to configuration
- **THEN** it SHALL retrieve it via `current_app.config['proxy_config']`
- **AND** it SHALL NOT access module-level `_proxy_config` global

### Requirement: Remove module-level global state
The system SHALL NOT use module-level global variables (`_proxy_config`, `_ctx`) in blueprint modules after migration.

#### Scenario: Blueprint module initialization
- **WHEN** a blueprint module is imported
- **THEN** it SHALL NOT define module-level `_proxy_config: ProxyConfig = None`
- **AND** it SHALL NOT define module-level `_ctx: ProxyGlobalContext = None`
- **AND** it SHALL NOT require an `init_module()` function to be called

### Requirement: Handler dependency injection
Model handlers SHALL receive dependencies (config, context) as method parameters rather than accessing global state.

#### Scenario: Handler method signature
- **WHEN** a model handler's `handle_request()` method is called
- **THEN** it SHALL receive `config: ProxyConfig` as a parameter
- **AND** it SHALL receive `ctx: ProxyGlobalContext` as a parameter
- **AND** it SHALL NOT import or access global configuration

### Requirement: Test isolation support
The dependency injection pattern SHALL enable isolated unit testing of blueprints and handlers.

#### Scenario: Blueprint unit testing
- **WHEN** testing a blueprint route in isolation
- **THEN** the test SHALL be able to override `app.config['proxy_config']` with a mock
- **AND** the test SHALL NOT require modifying global state
- **AND** multiple tests SHALL be able to run in parallel without state conflicts

#### Scenario: Handler unit testing
- **WHEN** testing a model handler in isolation
- **THEN** the test SHALL be able to pass mock config and context to the handler
- **AND** the handler SHALL NOT require global state to be initialized

### Requirement: Thread safety
The configuration access pattern SHALL be thread-safe for concurrent request handling.

#### Scenario: Concurrent requests
- **WHEN** multiple requests are processed concurrently
- **THEN** each request SHALL access the same `proxy_config` instance
- **AND** request-specific state SHALL NOT leak between requests
- **AND** Flask's `current_app` context SHALL provide proper isolation
