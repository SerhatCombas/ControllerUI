"""shared/utils — stateless helpers used across the project.

Contains:
* logging helpers (formatter, structured logging helpers)
* logging_events constants (per `specs/10 §8`)
* localization helpers
* ULID generation
* JSON serialization helpers
* unit conversion (per ADR-011)

These utilities must remain free of business logic, UI dependencies,
and feature-module imports.

References
----------
* `specs/06_data_flow_and_architecture.md` §2.3
* `specs/10_logging_conventions.md`
"""

__all__: list[str] = []
