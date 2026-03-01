## ADDED Requirements

### Requirement: Application Lifespan Management
The application SHALL use `contextlib.asynccontextmanager` to handle startup and shutdown events, ensuring configuration and resources are loaded before serving requests.

#### Scenario: Startup Sequence
- **WHEN** application starts
- **THEN** it SHALL load configuration from file
- **AND** it SHALL initialize the Global Context (tokens, SDK clients)
- **AND** it SHALL configure logging

### Requirement: Dependency Injection for Global Context
The application SHALL provide `ProxyConfig` and `ProxyGlobalContext` via FastAPI's dependency injection system, replacing global variables.

#### Scenario: Route Access to Config
- **WHEN** a route handler requires configuration
- **THEN** it SHALL receive it as a function argument injected by `Depends()`

### Requirement: FastAPI Application Factory
The application SHALL expose a `create_app()` factory or equivalent main entry point that constructs the `FastAPI` app instance with all routers and middleware attached.

#### Scenario: App Creation
- **WHEN** the application is initialized
- **THEN** it SHALL register all `APIRouter` instances (chat, messages, embeddings, models)
- **AND** it SHALL register exception handlers (HTTP 429, 500)

### Requirement: Dependency Injection for Authentication
The application SHALL provide request validation via a `Depends(verify_request_token)` dependency that raises `HTTPException(401)` for invalid tokens.

#### Scenario: Protected Route Access
- **WHEN** a client calls a protected endpoint without a valid token
- **THEN** the application SHALL return 401 Unauthorized
- **AND** the route handler SHALL NOT be executed
