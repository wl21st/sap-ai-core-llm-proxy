# Spec: Model Detection

## ADDED Requirements

### Requirement: Model Type Detection

The system SHALL provide detection of model types from model name strings for routing and format conversion.

#### Scenario: Detect Claude models
- **GIVEN** a model name string "claude-3.5-sonnet"
- **WHEN** `Detector.is_claude_model()` is called
- **THEN** the function SHALL return True
- **AND** given model name "anthropic--claude-4.5-sonnet", SHALL return True
- **AND** given model name "sonnet", SHALL return True (keyword match)
- **AND** given model name "opus", SHALL return True (keyword match)
- **AND** given model name "haiku", SHALL return True (keyword match)
- **AND** given model name "anthropic--claude", SHALL return True
- **AND** given model name "gpt-4o", SHALL return False

#### Scenario: Detect Claude 3.7 and 4.x models
- **GIVEN** a model name string "claude-3.7-sonnet"
- **WHEN** `Detector.is_claude_37_or_4()` is called
- **THEN** the function SHALL return True
- **AND** given model name "claude-3-7-sonnet", SHALL return True
- **AND** given model name "claude-4", SHALL return True
- **AND** given model name "claude-sonnet-4", SHALL return True
- **AND** given model name "claude-4.5-sonnet", SHALL return True
- **AND** given model name "claude-3.5-sonnet", SHALL return False

#### Scenario: Detect Gemini models
- **GIVEN** a model name string "gemini-2.5-pro"
- **WHEN** `Detector.is_gemini_model()` is called
- **THEN** the function SHALL return True
- **AND** given model name "models/gemini-2.5-pro", SHALL return True
- **AND** given model name "gemini-1.5-pro", SHALL return True
- **AND** given model name "claude-3.5-sonnet", SHALL return False
- **AND** given model name "gpt-4o", SHALL return False

#### Scenario: Handle empty or None model names
- **GIVEN** a None or empty string as model name
- **WHEN** any detection method is called
- **THEN** the function SHALL return False
- **AND** the function SHALL not raise an exception

#### Scenario: Case-insensitive model detection
- **GIVEN** a model name with mixed case "Claude-3.5-SONNET"
- **WHEN** `Detector.is_claude_model()` is called
- **THEN** the function SHALL return True
- **AND** given "GEMINI-2.5-PRO", SHALL return True for Gemini detection
- **AND** detection SHALL be case-insensitive for all providers

### Requirement: Model Detection Constants

The system SHALL provide constants for model name patterns to support detection logic.

#### Scenario: Access Claude detection constants
- **GIVEN** the `Detector` class is imported
- **WHEN** `Detector.CLAUDE_PREFIXES` is accessed
- **THEN** the value SHALL be a tuple of strings
- **AND** SHALL include "claude-"
- **AND** SHALL include "anthropic--claude-"
- **AND** when `Detector.CLAUDE_KEYWORDS` is accessed
- **AND** the value SHALL be ("sonnet", "opus", "haiku")
- **AND** when `Detector.CLAUDE_37_4_PATTERNS` is accessed
- **AND** the value SHALL be ("claude-3-7", "claude-3.7", "claude-4", "claude-sonnet-4")

#### Scenario: Access Gemini detection constants
- **GIVEN** the `Detector` class is imported
- **WHEN** `Detector.GEMINI_PREFIXES` is accessed
- **THEN** the value SHALL be a tuple of strings
- **AND** SHALL include "gemini-"
- **AND** SHALL include "models/gemini-"

#### Scenario: Use detection constants for extension
- **GIVEN** new model detection logic is needed
- **WHEN** detection constants are used in conditional logic
- **THEN** the constants SHALL be accessible as class attributes
- **AND** the constants SHALL be immutable (tuples)
- **AND** the constants SHALL be used consistently across the codebase
