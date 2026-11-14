"""Run the whole project, step by step, in the right order.

Run from the project folder:  python main.py

Each step is a script in src/. If one step fails, the run stops there
with the error message, so later steps never use broken inputs.
"""

import runpy
import sys
import time
import warnings
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_DIR = PROJECT_DIR / "src"

STEPS = [
    "01_get_data.py",
    "02_build_database.py",
    "03_partner_weights.py",
    "04_descriptives.py",
    "05_regressions.py",
    "06_forecast.py",
    "07_results_summary.py",
]


def main():
    # Let the scripts import common.py and country_codes.py from src/.
    sys.path.insert(0, str(SOURCE_DIR))
    # pandas 2.2.0 prints a notice about a future dependency (pyarrow) on
    # import. It does not affect results, so it is hidden here.
    warnings.filterwarnings("ignore", message=".*Pyarrow will become",
                            category=DeprecationWarning)

    start_all = time.time()
    for step in STEPS:
        print()
        print("=" * 70)
        print("Running", step)
        print("=" * 70)
        start = time.time()
        runpy.run_path(str(SOURCE_DIR / step), run_name="__main__")
        print("Finished", step, "in", round(time.time() - start, 1),
              "seconds")
    print()
    print("All steps finished in", round(time.time() - start_all), "seconds.")


if __name__ == "__main__":
    main()
