#!/bin/bash
# Comprehensive test suite runner for new-plugin-layer skill
# Executes all test suites and provides summary
# Run: bash tests/run-all-tests.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")"))")"
REPO_ROOT="$CLAUDE_DIR/commands/new-plugin-layer"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m'

TOTAL_PASSED=0
TOTAL_FAILED=0
TESTS_RUN=()
FAILED_SUITES=()

echo -e "${MAGENTA}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${MAGENTA}║${NC}   New-Plugin-Layer Comprehensive Test Suite Runner    ${MAGENTA}║${NC}"
echo -e "${MAGENTA}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Running all test suites to validate skill functionality..."
echo ""

# Helper function to run a test suite
run_test_suite() {
  local test_script=$1
  local suite_name=$2

  echo -e "${BLUE}┌─────────────────────────────────────────────────────────┐${NC}"
  echo -e "${BLUE}│${NC} $suite_name"
  echo -e "${BLUE}└─────────────────────────────────────────────────────────┘${NC}"

  if [ ! -f "$test_script" ]; then
    echo -e "${RED}✗ Test script not found: $test_script${NC}"
    ((TOTAL_FAILED++))
    FAILED_SUITES+=("$suite_name (script not found)")
    return 1
  fi

  # Make the script executable
  chmod +x "$test_script"

  # Run the test script and capture output
  if output=$(bash "$test_script" 2>&1); then
    echo "$output"
    TESTS_RUN+=("✓ $suite_name")
  else
    echo "$output"
    exit_code=$?
    TESTS_RUN+=("✗ $suite_name (exit code: $exit_code)")
    FAILED_SUITES+=("$suite_name")
    ((TOTAL_FAILED++))
  fi

  echo ""
}

# Run each test suite
run_test_suite "$SCRIPT_DIR/test-new-plugin-layer.sh" "Core Functionality Tests"
run_test_suite "$SCRIPT_DIR/test-plugin-search-advanced.sh" "Advanced Plugin Search Tests"
run_test_suite "$SCRIPT_DIR/test-state-and-logic.sh" "State Management & Logic Tests"
run_test_suite "$SCRIPT_DIR/test-file-generation.sh" "File Generation & I/O Tests"
run_test_suite "$SCRIPT_DIR/test-integration.sh" "Integration Tests"

# Final summary
echo -e "${MAGENTA}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${MAGENTA}║${NC}                    Test Execution Summary             ${MAGENTA}║${NC}"
echo -e "${MAGENTA}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# List all executed suites
echo -e "${YELLOW}Test Suites Executed:${NC}"
for suite in "${TESTS_RUN[@]}"; do
  echo "  $suite"
done
echo ""

# Display summary statistics
echo -e "${YELLOW}Test Results:${NC}"
if [ ${#FAILED_SUITES[@]} -eq 0 ]; then
  echo -e "  ${GREEN}✓ All test suites passed${NC}"
  echo ""
  echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
  echo -e "${GREEN}SUCCESS: All functionality tests passed!${NC}"
  echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
  exit 0
else
  echo -e "  ${RED}✗ Some test suites failed:${NC}"
  for suite in "${FAILED_SUITES[@]}"; do
    echo -e "    ${RED}✗${NC} $suite"
  done
  echo ""
  echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
  echo -e "${RED}FAILURE: Some tests failed. Review output above.${NC}"
  echo -e "${RED}═══════════════════════════════════════════════════════════${NC}"
  exit 1
fi
