# Python Coding Conventions & Scoping Guidelines

This document outlines the coding standards, naming conventions (PEP 8), and scoping guidelines for the `sap-ai-core-llm-proxy` codebase.

---

## 1. PEP 8 Naming Conventions

### Variables & Functions: `snake_case`
```python
# ✅ Good
def get_file_logger():
    pass

user_name = "Alice"
max_retries = 3

# ❌ Bad
def GetFileLogger():  # Don't use camelCase/PascalCase for functions
    pass

userName = "Alice"
```

### Constants: `UPPER_SNAKE_CASE`
```python
# ✅ Good
DEFAULT_LOG_FOLDER = "logs"
MAX_RETRIES = 3
API_TIMEOUT = 30

# ❌ Bad
default_log_folder = "logs"
```

### Classes & Pydantic Models: `PascalCase`
```python
# ✅ Good
class SubAccountConfig(BaseModel):
    pass

class TokenManager:
    pass

# ❌ Bad
class sub_account_config:
    pass
```

### Private / Internal Members: `_leading_underscore`
```python
# ✅ Good - signals internal module/class use
_logging_initialized = False
_setup_lock = threading.Lock()

def _internal_helper():
    pass

class MyService:
    def _protected_method(self):
        pass
```

### Packages & Modules: `lowercase_with_underscores`
```
# ✅ Good
auth/
routers/
token_manager.py
request_validator.py

# ❌ Bad
AuthModule/
TokenManager.py
```

### Boolean Variables: `is_`, `has_`, `can_`, `should_`
```python
# ✅ Good
is_valid = True
has_error = False
can_proceed = True
should_retry = False
```

### Type Hints: Required for All Signatures
```python
# ✅ Good
def get_file_logger(logger_name: str, logger_level: int = logging.INFO) -> logging.Logger:
    pass

def process_users(users: list[str]) -> dict[str, bool]:
    pass
```

---

## 2. Module-Level vs. Class-Level Scoping

### Use Module-Level (Standalone) Functions For:

#### 1. Pure Helper & Utility Functions
Stateless operations that do not depend on instance state.
```python
# ✅ GOOD: Module-level utility
def is_valid_model_name(model: str) -> bool:
    """Validate that model name matches expected pattern."""
    return bool(model) and len(model) > 0

# ❌ BAD: Unnecessary class wrapping
class ModelValidator:
    @staticmethod
    def is_valid_model_name(model: str) -> bool:
        return bool(model) and len(model) > 0
```

#### 2. Format Transformations & Parsing
Converting requests/responses between provider schemas (OpenAI ↔ Claude ↔ Gemini).
```python
# ✅ GOOD: Module-level transformation
def extract_model_name(full_model_path: str) -> str:
    """Extract model name from deployment path."""
    return full_model_path.split("/")[-1]

def normalize_model_name(name: str) -> str:
    """Remove common vendor prefixes."""
    for prefix in ("anthropic--", "google--", "openai--"):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name
```

#### 3. Shared Utilities Across Multiple Classes
Functions required across routers, validators, and handlers should live in `utils/` or dedicated modules to prevent tight coupling.

#### 4. Startup / Configuration Parsers
One-time initialization functions (e.g. JSON loading, cert resolution).

---

### Use Class-Level Methods / Instances For:

#### 1. State Management & Lifecycle
When maintaining state across multiple requests (e.g., token caching, round-robin counters, connection pooling).
```python
class TokenManager:
    def __init__(self, service_key: ServiceKey):
        self.service_key = service_key
        self._token: Optional[str] = None
        self._expiry: float = 0.0
        self._lock = threading.Lock()

    def get_token(self) -> str:
        with self._lock:
            # thread-safe token retrieval and refresh
            ...
```

#### 2. Dependency Injection & Service Encapsulation
FastAPI dependency providers (such as `ProxyGlobalContext`) that manage shared services and lifecycle.

---

## 3. Error Handling & Thread Safety

1. **Always use try-except with appropriate logging**:
   ```python
   try:
       result = risky_operation()
   except ValueError as error:
       logger.error("Invalid value encountered: %s", error, exc_info=True)
       raise
   ```
2. **Handle HTTP 429 with conservative retry**:
   Use `tenacity` retry decorators with exponential backoff on upstream rate limit errors.
3. **Thread Safety**:
   Always protect shared mutable state with `threading.Lock()` or immutable data structures.
