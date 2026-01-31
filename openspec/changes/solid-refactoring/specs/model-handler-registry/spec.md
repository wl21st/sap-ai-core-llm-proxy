## ADDED Requirements

### Requirement: Model handler registry
The system SHALL provide a `ModelHandlerRegistry` class in `handlers/registry.py` that maintains a registry of model handlers and selects the appropriate handler based on model name.

#### Scenario: Handler registration
- **WHEN** a model handler class is decorated with `@ModelHandlerRegistry.register(detector_fn)`
- **THEN** the handler SHALL be added to the registry
- **AND** the detector function SHALL be used to match models to this handler

#### Scenario: Handler selection
- **WHEN** `ModelHandlerRegistry.get_handler(model)` is called
- **THEN** the registry SHALL return the first handler whose detector function returns True for the model
- **AND** if no detector matches, a `DefaultHandler` SHALL be returned

### Requirement: Model handler protocol
The system SHALL define a `ModelHandler` Protocol that specifies the interface all model handlers must implement.

#### Scenario: Handler interface
- **WHEN** a class implements `ModelHandler`
- **THEN** it SHALL provide a `handle_request(request, config, ctx)` method
- **AND** it SHALL provide a `handle_streaming(request, config, ctx)` method
- **AND** it SHALL provide a `get_converter()` method that returns the appropriate converter

### Requirement: Claude model handler
The system SHALL provide a `ClaudeHandler` class registered with `Detector.is_claude_model` that handles all Claude model requests.

#### Scenario: Claude 3.7/4 request handling
- **WHEN** a request is made for a Claude 3.7 or 4.x model
- **THEN** the `ClaudeHandler` SHALL use the `/converse` endpoint
- **AND** the response SHALL be converted using Claude 3.7/4 converters

#### Scenario: Claude 3.5 request handling
- **WHEN** a request is made for a Claude 3.5 or earlier model
- **THEN** the `ClaudeHandler` SHALL use the `/invoke` endpoint
- **AND** the response SHALL be converted using legacy Claude converters

### Requirement: Gemini model handler
The system SHALL provide a `GeminiHandler` class registered with `Detector.is_gemini_model` that handles all Gemini model requests.

#### Scenario: Gemini request handling
- **WHEN** a request is made for a Gemini model
- **THEN** the `GeminiHandler` SHALL use the `/generateContent` endpoint
- **AND** the response SHALL be converted using Gemini converters

### Requirement: OpenAI model handler
The system SHALL provide an `OpenAIHandler` class registered with `Detector.is_openai_model` that handles GPT and other OpenAI-compatible models.

#### Scenario: OpenAI request handling
- **WHEN** a request is made for a GPT or OpenAI-compatible model
- **THEN** the `OpenAIHandler` SHALL use the `/chat/completions` endpoint
- **AND** no format conversion SHALL be required for the response

### Requirement: Default handler fallback
The system SHALL provide a `DefaultHandler` class that handles requests for models not matched by any registered detector.

#### Scenario: Unknown model handling
- **WHEN** a request is made for an unrecognized model
- **THEN** the `DefaultHandler` SHALL attempt to process it as an OpenAI-compatible model
- **AND** the system SHALL log a warning about the unrecognized model

### Requirement: Eliminate if/elif chains
After migration, the system SHALL NOT contain if/elif chains for model type detection in request handling code. All model-specific logic SHALL be encapsulated in handler classes.

#### Scenario: Adding a new model provider
- **WHEN** a developer needs to add support for a new model provider (e.g., Mistral)
- **THEN** they SHALL only need to create a new handler class with `@ModelHandlerRegistry.register()`
- **AND** they SHALL NOT need to modify existing handler or blueprint code
