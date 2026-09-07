"""Event management sub-package.

Modules:
    manager     — EnvironmentEventManager
    exceptions  — EventPersistence lifecycle-policy enum (the
                  dispatch-safety exception + metrics classes it used
                  to carry were removed 2026-09 as dead code — see
                  that module's docstring)
    generators/ — domain-specific event generators (see that
                  sub-package's own docstring; the generic impact /
                  policy generators + MAEventManager were removed
                  2026-09 as dead code)
"""
