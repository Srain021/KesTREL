"""Team Edition subpackage.

Only imported by CLI handlers under `kestrel team ...`. Code in this package
must check `settings.features` before invoking side effects; it MUST NOT
assume Pro safety guarantees (no rate limiting, no strict scope).

Decision log: PRODUCT_LINES.md Part 9.
"""
