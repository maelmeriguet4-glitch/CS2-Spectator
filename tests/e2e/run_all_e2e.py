"""
CS2 Anti-Cheat E2E Master Test Runner.
Discovers and executes the complete 4-tier E2E test suite:
- Tier 1: Feature Coverage (R1-R5)
- Tier 2: Boundary & Corner Cases
- Tier 3: Cross-Feature Interactions
- Tier 4: Real-World Workload Scenarios

Exit Code:
  0 = All tests passed successfully
  1 = One or more tests failed or errored
"""

import argparse
import os
import sys
import time
import unittest

# Ensure repo root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


# Configure UTF-8 for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception as _e:
            import logging
            logging.debug(f"Ignored error: {_e}")


def print_banner():
    print("=" * 78)
    print("[+] CS2 ANTI-CHEAT DESKTOP APPLICATION -- MASTER E2E TEST SUITE")
    print("    Opaque-Box 4-Tier Automated Verification Architecture")
    print("=" * 78)


def run_e2e_suite(tier_filter=None, verbosity=2) -> int:
    """
    Runs the E2E test suite and returns the exit code (0 = success, 1 = failure).
    """
    start_time = time.time()
    e2e_dir = os.path.dirname(__file__)

    tier_files = {
        1: ("Tier 1: Feature Coverage (R1-R5)", "test_tier1_features.py"),
        2: ("Tier 2: Boundary & Corner Cases", "test_tier2_boundaries.py"),
        3: ("Tier 3: Cross-Feature Interactions", "test_tier3_interactions.py"),
        4: ("Tier 4: Real-World Workloads", "test_tier4_real_world.py"),
        5: ("Tier 5: Adversarial Biomechanics & Parser", "test_tier5_adversarial.py"),
    }

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    selected_tiers = [tier_filter] if tier_filter in tier_files else [1, 2, 3, 4, 5]

    print(f"\n[*] Initializing test discovery across {len(selected_tiers)} tiers...")
    for t_num in selected_tiers:
        t_name, t_file = tier_files[t_num]
        file_path = os.path.join(e2e_dir, t_file)
        if os.path.isfile(file_path):
            mod_name = f"tests.e2e.{t_file[:-3]}"
            tier_suite = loader.loadTestsFromName(mod_name)
            suite.addTest(tier_suite)
            print(f"  • {t_name:<42} : {tier_suite.countTestCases()} test cases loaded")

    total_tests = suite.countTestCases()
    print("-" * 78)
    print(f"Total Scheduled Tests: {total_tests}")
    print("-" * 78 + "\n")

    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    elapsed = time.time() - start_time

    print("\n" + "=" * 78)
    print("[REPORT] CS2 ANTI-CHEAT E2E TEST SUITE EXECUTION REPORT")
    print("=" * 78)
    print(f"Total Tests Executed  : {result.testsRun}")
    print(f"Passed Successfully   : {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures              : {len(result.failures)}")
    print(f"Errors                : {len(result.errors)}")
    print(f"Skipped Tests         : {len(result.skipped)}")
    print(f"Execution Duration    : {elapsed:.2f} seconds")
    print("-" * 78)

    if result.wasSuccessful():
        print("[SUCCESS] VERDICT: 100% PASS -- ALL E2E VERIFICATION TIERS VALIDATED")
        print("=" * 78)
        return 0
    else:
        print("[FAIL] VERDICT: FAILURES DETECTED -- E2E TEST SUITE FAILED")
        print("=" * 78)
        return 1


def main():
    print_banner()

    parser = argparse.ArgumentParser(description="CS2 Anti-Cheat Standalone E2E Test Runner")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4, 5], default=None, help="Execute a specific tier only (1-5)")
    parser.add_argument("--quiet", action="store_true", help="Minimal verbosity output")
    args = parser.parse_args()

    verbosity = 1 if args.quiet else 2
    exit_code = run_e2e_suite(tier_filter=args.tier, verbosity=verbosity)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
