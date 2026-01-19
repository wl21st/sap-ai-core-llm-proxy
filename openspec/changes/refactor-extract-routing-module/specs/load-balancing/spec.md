# Spec: Load Balancing

## ADDED Requirements

### Requirement: Hierarchical Round-Robin Load Balancing

The system SHALL provide hierarchical round-robin load balancing across subaccounts and deployment URLs.

#### Scenario: Select subaccount using round-robin
- **GIVEN** a model "claude-3.5-sonnet" deployed in subaccounts ["sub1", "sub2", "sub3"]
- **WHEN** 3 consecutive requests are made for "claude-3.5-sonnet"
- **THEN** first request SHALL select "sub1"
- **AND** second request SHALL select "sub2"
- **AND** third request SHALL select "sub3"
- **AND** fourth request SHALL cycle back to "sub1"

#### Scenario: Select deployment URL using round-robin within subaccount
- **GIVEN** a model "gpt-4o" deployed in subaccount "sub1" with URLs ["url1", "url2", "url3"]
- **WHEN** 3 consecutive requests are made for "gpt-4o" and "sub1" is selected
- **THEN** first request SHALL select "url1"
- **AND** second request SHALL select "url2"
- **AND** third request SHALL select "url3"
- **AND** fourth request SHALL cycle back to "url1"

#### Scenario: Independent counters for different models
- **GIVEN** models "claude-3.5-sonnet" and "gpt-4o" both deployed
- **WHEN** a request is made for "claude-3.5-sonnet"
- **THEN** the round-robin counter for "claude-3.5-sonnet" SHALL increment
- **AND** the round-robin counter for "gpt-4o" SHALL remain unchanged

#### Scenario: Independent counters for subaccount-level selection
- **GIVEN** subaccount "sub1" with models "claude-3.5-sonnet" and "gpt-4o"
- **WHEN** requests are made for both models in "sub1"
- **THEN** the URL-level counter for "sub1:claude-3.5-sonnet" SHALL increment independently
- **AND** the URL-level counter for "sub1:gpt-4o" SHALL increment independently

### Requirement: Thread-Safe Load Balancing

The system SHALL ensure all load balancing counters are thread-safe under concurrent access.

#### Scenario: Concurrent requests increment counter safely
- **GIVEN** 10 concurrent threads requesting the same model
- **WHEN** all threads call load balancer simultaneously
- **THEN** all counter increments SHALL be serialized without race conditions
- **AND** each thread SHALL receive a unique (modulo total count) endpoint selection
- **AND** no endpoint SHALL be selected by more than expected number of threads

#### Scenario: Lock acquisition for counter access
- **GIVEN** a load balancer with shared counters
- **WHEN** any thread accesses or modifies a counter
- **THEN** the operation SHALL be protected by a `threading.Lock`
- **AND** the lock SHALL be released after the operation completes

### Requirement: Model Fallback

The system SHALL provide automatic fallback to alternative models when requested model is not available.

#### Scenario: Claude model fallback
- **GIVEN** a request for model "claude-3.7-opus" which is not deployed
- **AND** fallback model "anthropic--claude-4.5-sonnet" is deployed
- **WHEN** load balancer cannot find "claude-3.7-opus"
- **THEN** load balancer SHALL attempt to use "anthropic--claude-4.5-sonnet"
- **AND** logging SHALL indicate fallback occurred
- **AND** request SHALL succeed with the fallback model

#### Scenario: Gemini model fallback
- **GIVEN** a request for model "gemini-1.5-flash" which is not deployed
- **AND** fallback model "gemini-2.5-pro" is deployed
- **WHEN** load balancer cannot find "gemini-1.5-flash"
- **THEN** load balancer SHALL attempt to use "gemini-2.5-pro"
- **AND** logging SHALL indicate fallback occurred
- **AND** request SHALL succeed with the fallback model

#### Scenario: GPT model fallback
- **GIVEN** a request for model "gpt-5" which is not deployed
- **AND** fallback model "gpt-4o" is deployed as DEFAULT_GPT_MODEL
- **WHEN** load balancer cannot find "gpt-5"
- **THEN** load balancer SHALL attempt to use "gpt-4o"
- **AND** logging SHALL indicate fallback occurred
- **AND** request SHALL succeed with the fallback model

#### Scenario: No fallback available
- **GIVEN** a request for model "unknown-model" which is not deployed
- **AND** no fallback models are deployed
- **WHEN** load balancer cannot find "unknown-model" or any fallback
- **THEN** load balancer SHALL raise ValueError with descriptive message
- **AND** error message SHALL indicate model and all attempted fallbacks

### Requirement: Load Balancing Strategy Pattern

The system SHALL support pluggable load balancing strategies through a strategy pattern.

#### Scenario: Round-robin strategy selection
- **GIVEN** a LoadBalancer configured with RoundRobinStrategy
- **WHEN** `select_endpoint()` is called
- **THEN** endpoint SHALL be selected using round-robin algorithm
- **AND** `get_name()` SHALL return "round-robin"

#### Scenario: Least-connections strategy (stub)
- **GIVEN** a LoadBalancer configured with LeastConnectionsStrategy
- **WHEN** `select_endpoint()` is called
- **THEN** endpoint with fewest active connections SHALL be selected
- **AND** `get_name()` SHALL return "least-connections"

#### Scenario: Weighted strategy (stub)
- **GIVEN** a LoadBalancer configured with WeightedStrategy
- **WHEN** `select_endpoint()` is called
- **THEN** endpoint SHALL be selected based on configured weights
- **AND** `get_name()` SHALL return "weighted"

#### Scenario: Strategy injection at runtime
- **GIVEN** a LoadBalancer instance
- **WHEN** strategy is changed to a different LoadBalancingStrategy implementation
- **THEN** subsequent `select_endpoint()` calls SHALL use the new strategy
- **AND** no restart or reconfiguration is required
