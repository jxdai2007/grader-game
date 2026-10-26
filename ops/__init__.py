"""Operational scripts. `load_env` reads .env / compute.env into the process without printing them."""

from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def load_env() -> None:
    """Existing environment variables win (override=False); a missing file is skipped."""
    for name in (".env", "compute.env"):
        load_dotenv(ROOT / name)
