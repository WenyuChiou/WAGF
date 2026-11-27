from . import main

if __name__ == "__main__":
    code = main()
    if code == 0:
        from . import _entry
        if _entry.LAST_RUN_OUTPUT is not None:
            # Mandatory run records: exit non-zero when they are incomplete.
            from broker.utils.provenance_requirements import enforce_complete
            enforce_complete(_entry.LAST_RUN_OUTPUT)
    raise SystemExit(code)
