#!/bin/bash
# Comprehensive test suite for new-plugin-layer skill
# Tests plugin search, marketplace data validation, state tracking, and consistency checks
# Run: bash tests/test-new-plugin-layer.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")"))")"
REPO_ROOT="$CLAUDE_DIR/commands/new-plugin-layer"
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}New-Plugin-Layer Test Suite${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo ""

# Test core files exist
echo -e "${BLUE}Core File Validation${NC}"
for file in plugin-lists.json standards.json scripts/plugin-search.sh; do
  if [ -f "$REPO_ROOT/$file" ]; then
    echo -e "${GREEN}✓ PASS${NC}: $file exists"
    ((TESTS_PASSED++))
  else
    echo -e "${RED}✗ FAIL${NC}: $file NOT FOUND"
    ((TESTS_FAILED++))
  fi
done
echo ""

# Test marketplace caches
echo -e "${BLUE}Marketplace Cache Validation${NC}"
for marketplace in claude-plugins-official skills knowledge-work-plugins financial-services-plugins claude-plugins-community; do
  cache_file="$REPO_ROOT/.marketplace-${marketplace}.json"
  if [ -f "$cache_file" ] && jq empty "$cache_file" 2>/dev/null; then
    plugin_count=$(jq '.plugins | length' "$cache_file" 2>/dev/null || echo "0")
    echo -e "${GREEN}✓ PASS${NC}: .marketplace-${marketplace}.json ($plugin_count plugins)"
    ((TESTS_PASSED++))
  else
    echo -e "${RED}✗ FAIL${NC}: .marketplace-${marketplace}.json invalid or missing"
    ((TESTS_FAILED++))
  fi
done
echo ""

# Test JSON files validity
echo -e "${BLUE}JSON File Validation${NC}"
for jsonfile in plugin-lists.json standards.json; do
  if jq empty "$REPO_ROOT/$jsonfile" 2>/dev/null; then
    echo -e "${GREEN}✓ PASS${NC}: $jsonfile is valid JSON"
    ((TESTS_PASSED++))
  else
    echo -e "${RED}✗ FAIL${NC}: $jsonfile is invalid JSON"
    ((TESTS_FAILED++))
  fi
done
echo ""

# Test prebuilt counts
echo -e "${BLUE}Prebuilt Count Validation${NC}"
prebuilts=$(jq -r '.prebuilts | keys[]' "$REPO_ROOT/plugin-lists.json" 2>/dev/null)
for prebuilt in $prebuilts; do
  total=$(jq ".prebuilts.\"$prebuilt\".total" "$REPO_ROOT/plugin-lists.json" 2>/dev/null)
  dist_sum=$(jq ".prebuilts.\"$prebuilt\".distribution | add" "$REPO_ROOT/plugin-lists.json" 2>/dev/null)
  
  if [ "$total" = "$dist_sum" ]; then
    echo -e "${GREEN}✓ PASS${NC}: Prebuilt '$prebuilt' distribution sum correct ($dist_sum)"
    ((TESTS_PASSED++))
  else
    echo -e "${RED}✗ FAIL${NC}: Prebuilt '$prebuilt' distribution mismatch"
    ((TESTS_FAILED++))
  fi
done
echo ""

# Test search functionality
echo -e "${BLUE}Plugin Search Validation${NC}"
cd "$REPO_ROOT"
search_results=$(bash scripts/plugin-search.sh "code" . 2>/dev/null | grep "•" | wc -l)
if [ "$search_results" -gt 0 ]; then
  echo -e "${GREEN}✓ PASS${NC}: Search returns results (found $search_results for 'code')"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Search returned no results"
  ((TESTS_FAILED++))
fi
echo ""

# Summary
echo -e "${YELLOW}═══════════════════════════════════════════════════${NC}"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
  echo -e "${GREEN}All core tests passed!${NC}"
  exit 0
else
  echo -e "${RED}Some tests failed.${NC}"
  exit 1
fi
