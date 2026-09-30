"""Legacy Phase 1 Master Test Runner (Redirect Wrapper).

Maintained for backwards compatibility. Delegates directly to the canonical
suite in 'evaluation/run_aegis_master_test.py'.
"""

import sys
from pathlib import Path

from evaluation.run_aegis_master_test import run_master_verification

if __name__ == "__main__":
    success = run_master_verification()
    sys.exit(0 if success else 1)
