# Python Function/Method Scoping Guidelines

When to put methods/functions at the module level versus the class level.

## MODULE-LEVEL FUNCTIONS (Standalone Functions)

### Use module-level functions when:

#### 1. **Utility/Helper Functions** - Pure utilities with no state dependency
- No dependencies on instance variables
- Stateless operations that can be used independently
- Pure functions that always return the same output for same input
- **Example**: Data validation, format checking, simple transformations

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

#### 2. **Stateless Operations** - Operations that don't require object context
- Data transformations and conversions (parsing, encoding, formatting)
- Mathematical calculations or algorithmic operations
- String manipulations and validations
- Filter/search operations on data

```python
# ✅ GOOD: Module-level transformation
def extract_model_name(full_model_path: str) -> str:
    """Extract model name from deployment path."""
    return full_model_path.split("/")[-1]

# ✅ GOOD: Module-level validation
def validate_token_format(token: str) -> bool:
    """Check if token has valid format."""
    return token.startswith("Bearer ") and len(token) > 10
```

#### 3. **Shared by Multiple Classes** - Logic used across different classes
- Utilities that multiple classes need
- Avoids code duplication and tight coupling
- Improves maintainability
- Single source of truth for the logic

```python
# ✅ GOOD: Shared utility at module level
def normalize_model_name(name: str) -> str:
    """Remove common prefixes from model names."""
    prefixes = ["anthropic--", "google--", "openai--"]
    result = name
    for prefix in prefixes:
        if result.startswith(prefix):
            result = result.replace(prefix, "")
    return result

# Can be used by SubAccountConfig, ProxyConfig, RequestValidator, etc.
```

#### 4. **Configuration/Setup Functions** - One-time initialization
- Configuration loading and parsing
- Initialization that happens once at startup
- Should be at module level for clarity and reusability

```python
# ✅ GOOD: Module-level config loading
def load_service_key_from_file(filepath: str) -> Dict[str, str]:
    """Load and parse SAP service key from JSON file."""
    with open(filepath) as f:
        return json.load(f)

# Then used in class methods:
class SubAccountConfig:
    def load_service_key(self):
        key_data = load_service_key_from_file(self.service_key_json)
        self.service_key = ServiceKey(**key_data)
```

#### 5. **Convenience/Readability** - When it improves code clarity
- Small, focused functions with clear, specific names
- Easier to test independently
- Can be reused in multiple places
- Reduces class complexity

```python
# ✅ GOOD: Clear, focused module-level function
def is_streaming_request(payload: Dict[str, Any]) -> bool:
    """Determine if request is for streaming response."""
    return payload.get("stream", False) is True
```

### Examples from Your Codebase:

**Could be improved to module-level:**
```python
# Current structure in proxy_helpers.py
class Detector:
    @staticmethod
    def is_claude_model(model):
        return any(keyword in model for keyword in [...])

# Better as module-level:
def is_claude_model(model: str) -> bool:
    """Check if the model is a Claude model."""
    return any(keyword in model for keyword in 
               ["haiku", "claude", "clau", "sonnet", "sonne"])
```

---

## CLASS-LEVEL METHODS (Instance and Static Methods)

### Use class methods when:

#### 1. **Instance Methods** - Need to access/modify object state
- Methods that read or modify instance variables
- Operations that depend on the current state of the object
- Methods that represent behaviors of that specific object
- **Required pattern** for dataclasses with state

```python
# ✅ GOOD: Instance method modifying state
@dataclass
class SubAccountConfig:
    service_key: Optional[ServiceKey] = None
    
    def load_service_key(self):
        """Load and store service key for this account."""
        # Modifies self.service_key - must be instance method
        key_data = load_config(self.service_key_json)
        self.service_key = ServiceKey(...)

# ✅ GOOD: Instance method reading state
    def get_available_models(self) -> List[str]:
        """Get list of models for this subaccount."""
        # Reads self.normalized_models
        return list(self.normalized_models.keys())
```

#### 2. **Stateful Operations** - Maintaining or transforming object state
- Any method that changes instance variables
- Complex initialization that depends on initial state
- Methods that track or accumulate state
- Lazy initialization patterns

```python
# ✅ GOOD: Instance method transforming state
class ProxyConfig:
    model_to_subaccounts: Dict[str, List[str]] = field(default_factory=dict)

    def build_model_mapping(self):
        """Build model-to-subaccounts mapping."""
        # Modifies self.model_to_subaccounts
        self.model_to_subaccounts = {}
        for subaccount_name, subaccount in self.subaccounts.items():
            for model in subaccount.parsed_models_url_list.keys():
                if model not in self.model_to_subaccounts:
                    self.model_to_subaccounts[model] = []
                self.model_to_subaccounts[model].append(subaccount_name)
```

#### 3. **Related Behavior** - Methods logically grouped with data
- When object represents a single concept with multiple behaviors
- Methods are core to understanding that concept
- Data and behavior belong together
- Example: A Config object groups data with initialization logic

```python
# ✅ GOOD: Related behaviors grouped in class
@dataclass
class TokenInfo:
    token: Optional[str] = None
    expiry: float = 0
    lock: threading.Lock = field(default_factory=threading.Lock)
    
    def is_valid(self) -> bool:
        """Check if stored token is still valid."""
        return self.token is not None and time.time() < self.expiry
    
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return time.time() >= self.expiry
    
    def set_token(self, token: str, expiry: float):
        """Update stored token and expiry."""
        with self.lock:
            self.token = token
            self.expiry = expiry
```

#### 4. **Static Methods** - Utility functions needing logical grouping
- When you have 5+ related utility functions
- Grouping in a class creates better namespace organization
- Avoids polluting module namespace with many similar functions
- Logically cohesive utilities
- **Your example**: `Converters` class with 20+ conversion methods

```python
# ✅ GOOD: Related utilities grouped as static methods
class Converters:
    """API format conversion utilities."""
    
    @staticmethod
    def convert_openai_to_claude(payload):
        """Convert OpenAI format to Claude API format."""
        ...
    
    @staticmethod
    def convert_openai_to_gemini(payload):
        """Convert OpenAI format to Gemini format."""
        ...
    
    @staticmethod
    def convert_claude_to_openai(response, model):
        """Convert Claude response to OpenAI format."""
        ...
    
    # ... many more related conversions

# ❌ AVOID: Polluting module with many similar functions
def convert_openai_to_claude(payload):
    ...
def convert_openai_to_gemini(payload):
    ...
def convert_claude_to_openai(response, model):
    ...
# ... 15 more functions scattered in module
```

#### 5. **Inheritance/Polymorphism** - Need to override in subclasses
- Methods that will be overridden by subclasses
- Abstract base classes and interface definitions
- Template method pattern implementations
- **Must be class methods** for polymorphism to work

```python
# ✅ GOOD: Class method for inheritance/polymorphism
class LLMProvider:
    """Base class for LLM providers."""
    
    def send_request(self, payload: Dict) -> Dict:
        """Send request to LLM. Override in subclass."""
        raise NotImplementedError

class ClaudeProvider(LLMProvider):
    def send_request(self, payload: Dict) -> Dict:
        """Send request to Claude API."""
        # Specific implementation for Claude
        ...
```

#### 6. **Encapsulation** - Hiding implementation details
- Private methods (`_internal_helper()`) for internal use
- Prevents accidental direct access to helper logic
- Reduces module namespace pollution
- Better information hiding

```python
# ✅ GOOD: Private methods for internal use
class RequestValidator:
    def validate_request(self, request: Dict) -> bool:
        """Public method for validation."""
        return (self._check_auth(request) and 
                self._check_format(request) and
                self._check_permissions(request))
    
    def _check_auth(self, request: Dict) -> bool:
        """Private helper: check authentication."""
        ...
    
    def _check_format(self, request: Dict) -> bool:
        """Private helper: check request format."""
        ...
    
    def _check_permissions(self, request: Dict) -> bool:
        """Private helper: check user permissions."""
        ...
```

#### 7. **Thread-Safety/Locking** - Protecting shared state
- Methods that need synchronization with locks
- Operations on thread-safe shared resources
- Class provides synchronized access to state

```python
# ✅ GOOD: Class method with thread-safety
class TokenInfo:
    lock: threading.Lock = field(default_factory=threading.Lock)
    token: Optional[str] = None
    
    def set_token_safely(self, token: str):
        """Thread-safe token update."""
        with self.lock:
            self.token = token
```

---

## DECISION FLOWCHART

```
Does the function need access to instance state?
├─ YES (reads or modifies self.*) 
│   └─> Use INSTANCE METHOD
│
├─ MAYBE (could work either way)
│   └─ Is it a core behavior of this object?
│       ├─ YES → Use CLASS METHOD (static or instance)
│       └─ NO  → Use MODULE-LEVEL FUNCTION
│
└─ NO (completely stateless)
    └─ Are there 5+ related utility functions?
        ├─ YES → Group as STATIC METHODS in a class
        └─ NO  → Use MODULE-LEVEL FUNCTION
```

---

## QUICK REFERENCE TABLE

| Scenario | Use | Why | Example |
|----------|-----|-----|---------|
| Pure utility, no state | Module function | Simpler, more reusable | `validate_email(email: str)` |
| Related utilities (5+) | Static methods in class | Better organization | `Converters.convert_*()` |
| Reads/modifies `self.*` | Instance method | Must access state | `SubAccountConfig.load_service_key()` |
| Core object behavior | Instance method | Part of object identity | `TokenInfo.is_expired()` |
| Needs inheritance | Instance/class method | Polymorphism requirement | `LLMProvider.send_request()` |
| Internal helper logic | Private instance method | Encapsulation | `self._validate_format()` |
| Thread-safe access | Instance method | Synchronization needed | `TokenInfo.set_token_safely()` |

---

## PROJECT-SPECIFIC RECOMMENDATIONS

Based on your codebase and AGENTS.md conventions:

### Current Good Practices ✅
- **Instance methods in dataclasses**: Excellent use in `config/models.py`
  - `SubAccountConfig.load_service_key()`
  - `SubAccountConfig.normalize_model_names()`
  - `ProxyConfig.initialize()`
  - `ProxyConfig.build_model_mapping()`

- **Static method grouping**: Good use in `proxy_helpers.py`
  - `Converters` class organizes 20+ conversion functions
  - `Detector` class groups detection logic

### Potential Improvements 🔄

1. **Detector class → Module-level functions**
   ```python
   # Instead of static methods, consider module-level:
   # proxy_helpers.py
   
   def is_claude_model(model: str) -> bool:
       """Check if the model is a Claude model."""
       return any(keyword in model for keyword in 
                  ["haiku", "claude", "sonnet"])
   
   def is_gemini_model(model: str) -> bool:
       """Check if the model is a Gemini model."""
       return any(keyword in model.lower() for keyword in
                  ["gemini", "gemini-1.5", "gemini-2.5"])
   ```
   - **Reasoning**: Pure utilities, no shared state, used for simple checks
   - **Benefit**: Cleaner, more functional approach

2. **Keep Converters as class**
   ```python
   class Converters:
       """API format conversion utilities."""
       # 20+ conversion methods
   ```
   - **Reasoning**: Cohesive group of related transformations
   - **Benefit**: Clear namespace, easy to extend, logical grouping

3. **Request validation → Instance methods**
   - If you need to validate multiple requests against same config, make it instance-based
   - Allows per-validator customization

### Guidelines for New Code

When writing new functions/methods, ask yourself in order:

1. **Does it need `self`?** (instance variables)
   - YES → Instance method
   - NO → Continue

2. **Is it logically part of this object?** (belongs with the data)
   - YES → Static method in the class (or instance method)
   - NO → Continue

3. **Are there related functions (3+)?** (could be grouped)
   - YES → Consider grouping as static methods in a class
   - NO → Module-level function

4. **Will it be reused in many places?**
   - YES → Module-level function for easy access
   - NO → Either works, choose based on clarity

---

## Key Principles

1. **Cohesion**: Group related things together
   - Methods that share state → same class
   - Related utilities (5+) → same class as statics
   - Unrelated utilities → module-level

2. **Coupling**: Minimize dependencies
   - Module functions reduce coupling
   - Use instance methods when state is needed
   - Avoid static methods when instance method works better

3. **Clarity**: Code should be self-documenting
   - Names should clearly indicate purpose
   - Grouping should make sense semantically
   - Don't over-engineer simple utilities

4. **Reusability**: Make code easy to use
   - Module-level functions are easier to import and reuse
   - Class methods are better for related operations
   - Choose based on actual usage patterns
