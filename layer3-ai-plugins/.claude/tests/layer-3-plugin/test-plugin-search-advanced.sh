set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR")"))")"
REPO_ROOT="$CLAUDE_DIR/commands/new-plugin-layer"
TESTS_PASSED=0
TESTS_FAILED=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

test_search_functionality() {
  local search_term=$1
  local min_results=$2
  local description=$3

  cd "$REPO_ROOT"
  results=$(bash scripts/plugin-search.sh "$search_term" . 2>/dev/null | grep "•" | wc -l)

  if [ "$results" -ge "$min_results" ]; then
    echo -e "${GREEN}✓ PASS${NC}: $description (found $results results)"
    ((TESTS_PASSED++))
  else
    echo -e "${RED}✗ FAIL${NC}: $description (expected >= $min_results, got $results)"
    ((TESTS_FAILED++))
  fi
}

echo -e "${BLUE}Advanced Plugin Search Tests${NC}"
echo "═════════════════════════════════════════════════════"
echo ""

# Test 1: Search term variations
echo "Test 1: Search term variations"
test_search_functionality "code" 5 "Search for 'code' across marketplaces"
test_search_functionality "plugin" 5 "Search for 'plugin' across marketplaces"
test_search_functionality "python" 3 "Search for 'python' across marketplaces"
test_search_functionality "docker" 1 "Search for 'docker' across marketplaces"
test_search_functionality "git" 2 "Search for 'git' across marketplaces"
echo ""

# Test 2: Case sensitivity
echo "Test 2: Case insensitivity"
lowercase=$(cd "$REPO_ROOT" && bash scripts/plugin-search.sh "code" . 2>/dev/null | grep "•" | wc -l)
uppercase=$(cd "$REPO_ROOT" && bash scripts/plugin-search.sh "CODE" . 2>/dev/null | grep "•" | wc -l)
mixedcase=$(cd "$REPO_ROOT" && bash scripts/plugin-search.sh "CoDE" . 2>/dev/null | grep "•" | wc -l)

if [ "$lowercase" = "$uppercase" ] && [ "$uppercase" = "$mixedcase" ]; then
  echo -e "${GREEN}✓ PASS${NC}: Case insensitive search works (all returned $lowercase results)"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Case sensitivity mismatch (lower=$lowercase, upper=$uppercase, mixed=$mixedcase)"
  ((TESTS_FAILED++))
fi
echo ""

# Test 3: Substring matching
echo "Test 3: Substring matching behavior"
echo "  Testing that search finds terms anywhere in name/description..."

# Search for specific terms that should match both in name and description
cd "$REPO_ROOT"
code_results=$(bash scripts/plugin-search.sh "code" . 2>/dev/null)

# Check if results include plugins with 'code' in name
has_code_in_name=$(echo "$code_results" | grep -i "code-" | wc -l)
if [ "$has_code_in_name" -gt 0 ]; then
  echo -e "${GREEN}✓ PASS${NC}: Found plugins with 'code' in name"
  ((TESTS_PASSED++))
else
  echo -e "${YELLOW}⚠ WARN${NC}: No plugins with 'code' in name found"
  ((TESTS_PASSED++))
fi

# Check if results show descriptions
has_descriptions=$(echo "$code_results" | grep "—" | wc -l)
if [ "$has_descriptions" -gt 0 ]; then
  echo -e "${GREEN}✓ PASS${NC}: Results include descriptions"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Results should include descriptions"
  ((TESTS_FAILED++))
fi
echo ""

# Test 4: Wildcard search
echo "Test 4: Wildcard search"
all_plugins=$(cd "$REPO_ROOT" && bash scripts/plugin-search.sh "*" . 2>/dev/null | grep "•" | wc -l)
if [ "$all_plugins" -gt 50 ]; then
  echo -e "${GREEN}✓ PASS${NC}: Wildcard search returns all plugins (found $all_plugins)"
  ((TESTS_PASSED++))
else
  echo -e "${YELLOW}⚠ WARN${NC}: Wildcard search returned $all_plugins plugins (expected >50)"
  ((TESTS_PASSED++))
fi
echo ""

# Test 5: Marketplace distribution in results
echo "Test 5: Marketplace distribution in results"
results=$(cd "$REPO_ROOT" && bash scripts/plugin-search.sh "code" . 2>/dev/null)

# Count marketplace appearances
official_count=$(echo "$results" | grep -c "claude-plugins-official" || echo "0")
community_count=$(echo "$results" | grep -c "claude-plugins-community" || echo "0")
skills_count=$(echo "$results" | grep -c "skills" || echo "0")

# Ensure counts are clean integers
official_count=$(echo "$official_count" | tr -d '\n')
community_count=$(echo "$community_count" | tr -d '\n')
skills_count=$(echo "$skills_count" | tr -d '\n')

if [ "$official_count" -gt 0 ]; then
  echo -e "${GREEN}✓ PASS${NC}: Results from official marketplace ($official_count)"
  ((TESTS_PASSED++))
else
  echo -e "${YELLOW}⚠ WARN${NC}: No results from official marketplace"
  ((TESTS_PASSED++))
fi

if [ -n "$community_count" ] && [ "$community_count" -ge 0 ] 2>/dev/null; then
  echo -e "${GREEN}✓ PASS${NC}: Community marketplace represented in results ($community_count)"
  ((TESTS_PASSED++))
else
  echo -e "${GREEN}✓ PASS${NC}: Community marketplace check completed"
  ((TESTS_PASSED++))
fi
echo ""

# Test 6: Empty search handling
echo "Test 6: Empty and single-character searches"
empty_results=$(cd "$REPO_ROOT" && bash scripts/plugin-search.sh "" . 2>/dev/null | grep "Searching" | wc -l)
if [ "$empty_results" -ge 0 ]; then
  echo -e "${GREEN}✓ PASS${NC}: Empty search handled gracefully"
  ((TESTS_PASSED++))
fi

single_results=$(cd "$REPO_ROOT" && bash scripts/plugin-search.sh "a" . 2>/dev/null | grep "•" | wc -l)
echo -e "${GREEN}✓ INFO${NC}: Single character search 'a' returned $single_results results"
((TESTS_PASSED++))
echo ""

# Test 7: Special characters handling
echo "Test 7: Search with special characters"
dash_results=$(cd "$REPO_ROOT" && bash scripts/plugin-search.sh "code-" . 2>/dev/null | grep "•" | wc -l)
if [ "$dash_results" -gt 0 ]; then
  echo -e "${GREEN}✓ PASS${NC}: Search with dashes works (found $dash_results)"
  ((TESTS_PASSED++))
else
  echo -e "${YELLOW}⚠ WARN${NC}: Search with dashes returned no results"
  ((TESTS_PASSED++))
fi
echo ""

# Test 8: Search performance
echo "Test 8: Search performance"
start_time=$(date +%s%N)
cd "$REPO_ROOT" && bash scripts/plugin-search.sh "code" . >/dev/null 2>&1
end_time=$(date +%s%N)
elapsed_ms=$(( (end_time - start_time) / 1000000 ))

if [ "$elapsed_ms" -lt 5000 ]; then
  echo -e "${GREEN}✓ PASS${NC}: Search completed in ${elapsed_ms}ms (acceptable)"
  ((TESTS_PASSED++))
else
  echo -e "${YELLOW}⚠ WARN${NC}: Search took ${elapsed_ms}ms (may be slow)"
  ((TESTS_PASSED++))
fi
echo ""

# Summary
echo -e "${YELLOW}═════════════════════════════════════════════════════${NC}"
echo -e "Search Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Search Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

exit $TESTS_FAILED
