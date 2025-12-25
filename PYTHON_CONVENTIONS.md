# Python Naming Conventions (PEP 8)

## 1. Variable & Function Names: `lowercase_with_underscores` (snake_case)
```python
# ✅ Good
def get_file_logger():
    pass

user_name = "John"
max_retries = 3

# ❌ Bad
def GetFileLogger():  # camelCase - don't use in Python
    pass

userName = "John"  # camelCase - don't use in Python
```

## 2. Constants: `UPPERCASE_WITH_UNDERSCORES`
```python
# ✅ Good
DEFAULT_LOG_FOLDER = 'logs'
MAX_RETRIES = 3
API_TIMEOUT = 30

# ❌ Bad
default_log_folder = 'logs'  # Should be uppercase for constants
max_retries = 3
```

## 3. Classes: `PascalCase` (CapWords)
```python
# ✅ Good
class BankAccount:
    pass

class HTTPResponseHandler:
    pass

# ❌ Bad
class bank_account:  # Should be PascalCase
    pass

class http_response_handler:  # Should be PascalCase
    pass
```

## 4. Private/Internal: Single Underscore `_prefix`
```python
# ✅ Good - signals "internal use only"
_logging_initialized = False
_setup_lock = threading.Lock()

def _internal_helper():
    pass

class MyClass:
    def _protected_method(self):
        pass
```

## 5. Name-Mangled/Very Private: Double Underscore `__prefix`
```python
# Use rarely - mainly for inheritance protection
class SecureClass:
    def __init__(self):
        self.__private_key = "secret"  # Becomes _SecureClass__private_key
    
    def __internal_method(self):  # Becomes _SecureClass__internal_method
        pass
```

## 6. Dunder Methods (Magic Methods): `__method__`
```python
# Special Python methods with double underscores on both sides
class MyClass:
    def __init__(self):  # Constructor
        pass
    
    def __str__(self):  # String representation
        return "MyClass instance"
    
    def __len__(self):  # For len() function
        return 42
    
    def __call__(self):  # Make instance callable
        pass
    
    def __enter__(self):  # Context manager
        pass
    
    def __exit__(self):  # Context manager cleanup
        pass
```

## 7. Module Names: `lowercase_with_underscores`
```
# ✅ Good
logging_setup.py
request_validator.py
token_manager.py

# ❌ Bad
LoggingSetup.py  # Don't use PascalCase for modules
RequestValidator.py
```

## 8. Package Names: `lowercase` (no underscores if possible)
```
# ✅ Good
mypackage/
utils/
auth/

# ⚠️ Okay (but less preferred)
my_package/

# ❌ Bad
MyPackage/
My-Package/
```

## 9. Boolean Variables: Prefix with `is_`, `has_`, `can_`, `should_`
```python
# ✅ Good - clear that these are booleans
is_valid = True
has_error = False
can_proceed = True
should_retry = False

is_authenticated = False
is_production = True

# ❌ Less clear
valid = True
error = False  # Could be an Exception object
proceed = True
retry = False
```

## 10. Acronyms: Keep Capitalization Consistent
```python
# ✅ Good
HTTPSConnection  # All caps for acronym
XMLParser
URLBuilder
IOError

# ❌ Inconsistent
HttpsConnection
HttpConnection
XmlParser
UrlBuilder
```

## 11. Temporary/Loop Variables: Single Letters (in limited scope)
```python
# ✅ Good for simple loops
for i in range(10):
    print(i)

for x, y in coordinates:
    process(x, y)

# ❌ Bad - too vague in larger scopes
x = get_user_data()  # What is x?
y = process_request()  # What is y?
```

## 12. Exception Variables: Use `as` clause properly
```python
# ✅ Good
try:
    risky_operation()
except ValueError as error:
    logger.error(f"Invalid value: {error}")

# ❌ Bad
except ValueError as e:  # 'e' is too vague
    pass
```

## 13. Collection Variables: Plural names
```python
# ✅ Good - clearly plural
users = []
logs = []
errors = []
config_items = {}

# ❌ Bad - unclear if singular or plural
user_list = []  # Redundant, use 'users'
log_array = []  # Redundant, use 'logs'
error_set = set()  # Redundant, use 'errors'
```

## 14. Type Hints: Use for clarity
```python
# ✅ Good
def get_file_logger(logger_name: str, logger_level: int = logging.INFO) -> logging.Logger:
    pass

def process_users(users: list[str]) -> dict[str, bool]:
    pass

# ❌ Bad - no hints
def get_file_logger(logger_name, logger_level=None):
    pass
```

## 15. Aliases: Use descriptive names
```python
# ✅ Good
import logging as logger
from datetime import datetime as dt
from collections import defaultdict as dd

# ❌ Bad - too vague
import logging as l
from datetime import datetime as d
from collections import defaultdict as x
```

## Summary Table

| Type | Convention | Example |
|------|-----------|---------|
| Variables | `lowercase_with_underscores` | `user_name`, `max_retries` |
| Constants | `UPPERCASE_WITH_UNDERSCORES` | `DEFAULT_TIMEOUT`, `MAX_RETRIES` |
| Classes | `PascalCase` | `UserAccount`, `HTTPHandler` |
| Functions | `lowercase_with_underscores` | `get_user()`, `validate_email()` |
| Private | `_lowercase_with_underscores` | `_internal_helper()` |
| Magic Methods | `__method__` | `__init__()`, `__str__()` |
| Modules | `lowercase_with_underscores` | `logging_setup.py` |
| Packages | `lowercase` | `mypackage/`, `utils/` |
| Booleans | `is_/has_/can_/should_` | `is_valid`, `has_error` |

## Reference
- **PEP 8** - Python Enhancement Proposal 8: Style Guide for Python Code
- https://www.python.org/dev/peps/pep-0008/


