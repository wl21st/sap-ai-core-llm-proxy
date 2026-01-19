# Spec: Failover

## ADDED Requirements

### Requirement: Circuit Breaker Pattern

The system SHALL implement circuit breaker pattern to prevent cascading failures when endpoints are unhealthy.

#### Scenario: Circuit breaker opens after threshold failures
- **GIVEN** a circuit breaker with failure_threshold=5
- **AND** an endpoint fails with 5 consecutive errors
- **WHEN** 6th request is made to the endpoint
- **THEN** circuit breaker SHALL be in "open" state
- **AND** request SHALL be rejected without attempting the endpoint
- **AND** circuit breaker SHALL log state transition to "open"

#### Scenario: Circuit breaker closes after timeout
- **GIVEN** a circuit breaker in "open" state
- **AND** timeout duration of 60 seconds has elapsed
- **WHEN** a request is made
- **THEN** circuit breaker SHALL transition to "half-open" state
- **AND** next request SHALL be attempted to verify endpoint health
- **AND** circuit breaker SHALL log state transition to "half-open"

#### Scenario: Circuit breaker resets on success
- **GIVEN** a circuit breaker in "half-open" state
- **AND** a request succeeds
- **WHEN** the successful request completes
- **THEN** circuit breaker SHALL transition to "closed" state
- **AND** failure counter SHALL be reset
- **AND** subsequent requests SHALL proceed normally

#### Scenario: Circuit breaker remains open on continued failure
- **GIVEN** a circuit breaker in "half-open" state
- **AND** a request fails
- **WHEN** the failed request completes
- **THEN** circuit breaker SHALL transition back to "open" state
- **AND** failure counter SHALL reset
- **AND** timeout SHALL restart

### Requirement: Health Check

The system SHALL perform health checks to detect unavailable endpoints before routing requests.

#### Scenario: Health check passes
- **GIVEN** an endpoint URL "https://api.example.com/invoke"
- **WHEN** health check is performed
- **THEN** request SHALL be sent with HEAD method or minimal GET
- **AND** response with status < 500 SHALL indicate healthy endpoint
- **AND** endpoint SHALL be marked as available for routing

#### Scenario: Health check fails
- **GIVEN** an endpoint URL "https://api.example.com/invoke"
- **AND** endpoint is unresponsive
- **WHEN** health check is performed
- **THEN** request SHALL timeout or receive error status
- **AND** endpoint SHALL be marked as unavailable
- **AND** circuit breaker SHALL increment failure count

#### Scenario: Health check timeout
- **GIVEN** an endpoint URL "https://api.example.com/invoke"
- **AND** health check timeout is set to 5 seconds
- **WHEN** endpoint does not respond within 5 seconds
- **THEN** health check SHALL fail with timeout error
- **AND** endpoint SHALL be marked as unavailable
- **AND** circuit breaker SHALL increment failure count

### Requirement: Automatic Failover

The system SHALL automatically failover to alternative endpoints when primary endpoint is unavailable.

#### Scenario: Failover within subaccount (multiple URLs)
- **GIVEN** subaccount "sub1" with deployment URLs ["url1", "url2", "url3"]
- **AND** "url1" is unhealthy (circuit breaker open)
- **WHEN** request is routed to "sub1"
- **THEN** load balancer SHALL skip "url1"
- **AND** load balancer SHALL select "url2" as alternative
- **AND** request SHALL proceed to "url2"
- **AND** logging SHALL indicate failover occurred

#### Scenario: Failover across subaccounts
- **GIVEN** model "claude-3.5-sonnet" deployed in subaccounts ["sub1", "sub2"]
- **AND** "sub1" has all URLs unhealthy (circuit breakers open)
- **WHEN** request is routed to "claude-3.5-sonnet"
- **THEN** load balancer SHALL skip "sub1"
- **AND** load balancer SHALL select "sub2" as alternative
- **AND** request SHALL proceed to "sub2"
- **AND** logging SHALL indicate failover occurred

#### Scenario: No available endpoints
- **GIVEN** model "claude-3.5-sonnet" deployed in subaccounts ["sub1", "sub2"]
- **AND** all URLs in all subaccounts are unhealthy
- **WHEN** request is routed to "claude-3.5-sonnet"
- **THEN** load balancer SHALL raise ValueError
- **AND** error message SHALL indicate no available endpoints
- **AND** logging SHALL indicate all endpoints unavailable

### Requirement: Circuit Breaker Configuration

The system SHALL allow configurable circuit breaker thresholds and timeouts.

#### Scenario: Configure failure threshold
- **GIVEN** a circuit breaker configuration
- **WHEN** failure_threshold is set to 10
- **THEN** circuit breaker SHALL open after 10 consecutive failures
- **AND** circuit breaker SHALL not open after fewer than 10 failures

#### Scenario: Configure timeout duration
- **GIVEN** a circuit breaker configuration
- **WHEN** timeout_duration is set to 120 seconds
- **THEN** circuit breaker SHALL remain open for 120 seconds
- **AND** circuit breaker SHALL transition to half-open after 120 seconds

#### Scenario: Configure health check interval
- **GIVEN** a circuit breaker configuration
- **WHEN** health_check_interval is set to 30 seconds
- **THEN** health checks SHALL be performed every 30 seconds for half-open state
- **AND** health checks SHALL not be performed more frequently

### Requirement: Endpoint State Tracking

The system SHALL track endpoint health state across requests.

#### Scenario: Track successful requests
- **GIVEN** an endpoint with no prior state
- **WHEN** a request succeeds
- **THEN** endpoint SHALL be marked as healthy
- **AND** circuit breaker failure counter SHALL be reset
- **AND** endpoint SHALL be available for subsequent requests

#### Scenario: Track failed requests
- **GIVEN** an endpoint with no prior state
- **WHEN** a request fails with 5xx status or timeout
- **THEN** circuit breaker failure counter SHALL increment
- **AND** endpoint SHALL be marked as unhealthy if threshold reached
- **AND** logging SHALL record failure details

#### Scenario: Track concurrent failures
- **GIVEN** an endpoint with failure_counter=3
- **AND** failure_threshold=5
- **WHEN** 2 concurrent requests fail
- **THEN** failure counter SHALL be incremented atomically for each failure
- **AND** final failure_counter SHALL be 5
- **AND** circuit breaker SHALL open after both failures processed
