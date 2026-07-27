# Configuration & Dependency Injection

## Configuration Architecture
The system uses `pydantic-settings` to enforce strict validation across all environment variables.
Settings are modularized into categories (App, Email, Database, etc.) and injected globally.

### Feature Flags
Located in `src/config/feature_flags.py`, flags allow seamless enabling/disabling of core components.
Prefix flags with `FEATURE_` in the `.env` (e.g., `FEATURE_ENABLE_AI=false`).

### Adding New Configurations
1. Define the attribute and type in the relevant Config class in `src/config/settings.py`.
2. Add validation rules (e.g., `Field(ge=10)`).
3. Ensure the `.env.example` file is updated.

## Dependency Injection (DI)
Located in `src/utils/di.py`, the lightweight container manages object lifecycles.

### Usage
```python
from src.utils.di import container

container.register_singleton(IMailClient, implementation=GmailClient)
client = container.resolve(IMailClient)
```

- **Singleton**: One instance shared globally.
- **Transient**: New instance created on every resolution.
