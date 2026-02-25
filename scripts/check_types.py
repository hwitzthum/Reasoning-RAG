#!/usr/bin/env python3
"""Type checking verification script.

Runs mypy on the app directory with strict mode to verify type annotations.

Usage:
    python scripts/check_types.py
"""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Run mypy type checker on the app directory."""
    print("Running mypy type checker (strict mode)...")
    print("=" * 50)

    project_root = Path(__file__).parent.parent
    app_dir = project_root / "app"

    # Run mypy
    result = subprocess.run(
        ["mypy", str(app_dir)],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    # Print output
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Exit with mypy's exit code
    if result.returncode == 0:
        print("\n✓ Type checking passed!")
        print("\nAll public functions have proper type hints.")
        print("Code is compatible with mypy --strict mode.")
    else:
        print("\n✗ Type checking failed!")
        print("\nPlease fix the type errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
