## ADDED Requirements

### Requirement: Converter package structure
The system SHALL organize format converters into a `converters/` package with separate modules for each model family (OpenAI, Claude, Gemini) and shared concerns (chunks, mappings).

#### Scenario: Package initialization
- **WHEN** importing from the converters package
- **THEN** the package SHALL export all converter functions via `converters/__init__.py`
- **AND** backward-compatible imports SHALL be available from `proxy_helpers.Converters`

### Requirement: Single-responsibility converter modules
Each converter module SHALL handle conversions for exactly one model family. The `converters/openai.py` module SHALL handle OpenAI format conversions, `converters/claude.py` SHALL handle Claude/Bedrock format conversions, and `converters/gemini.py` SHALL handle Gemini format conversions.

#### Scenario: OpenAI converter module
- **WHEN** converting a request to OpenAI format from Claude format
- **THEN** the conversion SHALL be handled by `converters/openai.py:from_claude()`
- **AND** the module SHALL NOT contain Claude-to-Gemini conversion logic

#### Scenario: Claude converter module
- **WHEN** converting a request to Claude format from OpenAI format
- **THEN** the conversion SHALL be handled by `converters/claude.py:from_openai()`
- **AND** the module SHALL NOT contain OpenAI-to-Gemini conversion logic

### Requirement: Converter Protocol definition
The system SHALL define a `Converter` Protocol in `converters/base.py` that specifies the interface for all converter implementations.

#### Scenario: Protocol compliance
- **WHEN** a new converter class is created
- **THEN** it SHALL implement the `Converter` Protocol
- **AND** type checkers SHALL report errors if the protocol is not satisfied

### Requirement: Centralized constant mappings
The system SHALL centralize all shared constants (stop reason mappings, API version strings) in `converters/mappings.py`.

#### Scenario: Stop reason mapping access
- **WHEN** any converter needs to map stop reasons between formats
- **THEN** it SHALL import the mapping from `converters.mappings.STOP_REASON_MAP`
- **AND** there SHALL be no duplicate stop reason mappings in other modules

#### Scenario: API version constant access
- **WHEN** any module needs an API version string
- **THEN** it SHALL import it from `converters.mappings`
- **AND** the constants `API_VERSION_BEDROCK_2023_05_31`, `API_VERSION_2024_12_01_PREVIEW`, and `API_VERSION_2023_05_15` SHALL be defined there

### Requirement: Streaming chunk converters
The system SHALL provide streaming chunk conversion functions in `converters/chunks.py` that handle SSE chunk transformations for all model types.

#### Scenario: Claude streaming chunk conversion
- **WHEN** a Claude streaming response chunk needs conversion to OpenAI format
- **THEN** the conversion SHALL be handled by `converters.chunks.claude_to_openai_chunk()`

#### Scenario: Gemini streaming chunk conversion
- **WHEN** a Gemini streaming response chunk needs conversion to OpenAI format
- **THEN** the conversion SHALL be handled by `converters.chunks.gemini_to_openai_chunk()`

### Requirement: Backward compatibility facade
The system SHALL maintain `proxy_helpers.Converters` as a facade that delegates to the new converter modules during the migration period.

#### Scenario: Legacy import compatibility
- **WHEN** existing code imports `from proxy_helpers import Converters`
- **THEN** all existing method calls SHALL continue to work
- **AND** a deprecation warning MAY be logged
