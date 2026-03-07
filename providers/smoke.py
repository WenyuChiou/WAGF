"""Lightweight smoke checks for configured LLM providers."""

from __future__ import annotations

import argparse
import importlib
import os
from dataclasses import dataclass
from typing import Callable, Mapping, Optional

from providers.factory import create_provider


@dataclass
class ProviderSmokeResult:
    provider_name: str
    model: str
    status: str
    detail: str


PROVIDER_SPECS = {
    "ollama": {
        "model": "llama3.2:3b",
        "import_name": "httpx",
        "env_var": None,
    },
    "openai": {
        "model": "gpt-4o-mini",
        "import_name": "openai",
        "env_var": "OPENAI_API_KEY",
    },
    "anthropic": {
        "model": "claude-3-5-sonnet-latest",
        "import_name": "anthropic",
        "env_var": "ANTHROPIC_API_KEY",
    },
    "gemini": {
        "model": "gemini-1.5-flash-latest",
        "import_name": "google.generativeai",
        "env_var": "GOOGLE_API_KEY",
    },
}


def validate_provider_connection(provider_name: str, model: str, env: Mapping[str, str]) -> bool:
    spec = PROVIDER_SPECS[provider_name]
    config = {"type": provider_name, "model": model}
    env_var = spec["env_var"]
    if env_var:
        config["api_key"] = env.get(env_var, "")
    provider = create_provider(config)
    return provider.validate_connection()


def check_provider(
    provider_name: str,
    model: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    importer: Optional[Callable[[str], object]] = None,
    validator: Optional[Callable[[str, str, Mapping[str, str]], bool]] = None,
) -> ProviderSmokeResult:
    env = env or os.environ
    importer = importer or importlib.import_module
    validator = validator or validate_provider_connection

    if provider_name not in PROVIDER_SPECS:
        raise ValueError(f"Unknown provider: {provider_name}")

    spec = PROVIDER_SPECS[provider_name]
    resolved_model = model or spec["model"]

    try:
        importer(spec["import_name"])
    except Exception as exc:
        return ProviderSmokeResult(
            provider_name=provider_name,
            model=resolved_model,
            status="missing_dependency",
            detail=str(exc),
        )

    env_var = spec["env_var"]
    if env_var and not env.get(env_var):
        return ProviderSmokeResult(
            provider_name=provider_name,
            model=resolved_model,
            status="missing_key",
            detail=f"{env_var} not set",
        )

    try:
        ok = validator(provider_name, resolved_model, env)
    except Exception as exc:
        return ProviderSmokeResult(
            provider_name=provider_name,
            model=resolved_model,
            status="error",
            detail=str(exc),
        )

    return ProviderSmokeResult(
        provider_name=provider_name,
        model=resolved_model,
        status="ready" if ok else "unreachable",
        detail="validate_connection() passed" if ok else "validate_connection() returned False",
    )


def run_smoke_checks(provider_names: Optional[list[str]] = None) -> list[ProviderSmokeResult]:
    names = provider_names or list(PROVIDER_SPECS.keys())
    return [check_provider(name) for name in names]


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke check configured LLM providers.")
    parser.add_argument(
        "--providers",
        nargs="*",
        choices=list(PROVIDER_SPECS.keys()),
        help="Subset of providers to check.",
    )
    args = parser.parse_args()

    results = run_smoke_checks(args.providers)
    for result in results:
        print(f"{result.provider_name:10} {result.status:18} {result.model:30} {result.detail}")

    return 0 if all(r.status == "ready" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
