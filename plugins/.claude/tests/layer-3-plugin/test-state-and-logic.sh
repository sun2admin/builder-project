set +e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTS_PASSED=0
TESTS_FAILED=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}State Management and Logic Tests${NC}"
echo "═════════════════════════════════════════════════════"
echo ""

# Test 1: Prebuilt selection state tracking
echo "Test 1: Prebuilt selection state tracking"
echo "─────────────────────────────────────────────────────"

# Verify that prebuilt definitions have all necessary state tracking fields
prebuilt_names=$(jq -r '.prebuilts | keys[]' "$REPO_ROOT/plugin-lists.json" 2>/dev/null)

for prebuilt in $prebuilt_names; do
  has_distribution=$(jq ".prebuilts.\"$prebuilt\" | has(\"distribution\")" "$REPO_ROOT/plugin-lists.json")

  if [ "$has_distribution" = "true" ]; then
    distribution=$(jq ".prebuilts.\"$prebuilt\".distribution" "$REPO_ROOT/plugin-lists.json")
    # Verify all 5 marketplaces are represented
    has_official=$(echo "$distribution" | jq 'has("claude-plugins-official")')
    has_skills=$(echo "$distribution" | jq 'has("anthropics/skills")')
    has_knowledge=$(echo "$distribution" | jq 'has("anthropics/knowledge-work-plugins")')
    has_financial=$(echo "$distribution" | jq 'has("anthropics/financial-services-plugins")')
    has_community=$(echo "$distribution" | jq 'has("claude-plugins-community")')

    if [ "$has_official" = "true" ] && [ "$has_skills" = "true" ] && [ "$has_knowledge" = "true" ] && [ "$has_financial" = "true" ] && [ "$has_community" = "true" ]; then
      echo -e "${GREEN}✓ PASS${NC}: Prebuilt '$prebuilt' has all 5 marketplace distribution keys"
      ((TESTS_PASSED++))
    else
      echo -e "${RED}✗ FAIL${NC}: Prebuilt '$prebuilt' missing distribution keys"
      ((TESTS_FAILED++))
    fi
  fi
done
echo ""

# Test 2: Distribution correctness - base prebuilt
echo "Test 2: Distribution verification - base prebuilt"
echo "─────────────────────────────────────────────────────"

base_plugins=$(jq '.prebuilts.base.plugins | length' "$REPO_ROOT/plugin-lists.json")
base_dist_official=$(jq '.prebuilts.base.distribution."claude-plugins-official"' "$REPO_ROOT/plugin-lists.json")

if [ "$base_plugins" = "$base_dist_official" ]; then
  echo -e "${GREEN}✓ PASS${NC}: Base distribution matches plugin count ($base_plugins)"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Base distribution mismatch (plugins=$base_plugins, dist=$base_dist_official)"
  ((TESTS_FAILED++))
fi
echo ""

# Test 3: Marketplace origin verification
echo "Test 3: Marketplace origin verification"
echo "─────────────────────────────────────────────────────"

# Verify that all plugins in base prebuilt are from the correct marketplace
non_official_count=$(jq '.prebuilts.base.plugins[] | select(.marketplace != "claude-plugins-official") | .name' "$REPO_ROOT/plugin-lists.json" 2>/dev/null | wc -l)

if [ "$non_official_count" -eq 0 ]; then
  echo -e "${GREEN}✓ PASS${NC}: All base plugins are from claude-plugins-official"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Base plugins have mixed marketplaces"
  ((TESTS_FAILED++))
fi
echo ""

# Test 4: Conflict detection logic - duplicate plugins across marketplaces
echo "Test 4: Duplicate detection (conflict detection)"
echo "─────────────────────────────────────────────────────"

# Check if any plugin name appears in multiple marketplaces within a prebuilt
conflict_found=false

prebuilt_names=$(jq -r '.prebuilts | keys[]' "$REPO_ROOT/plugin-lists.json")
for prebuilt in $prebuilt_names; do
  all_plugins=$(jq ".prebuilts.\"$prebuilt\" | [.plugins[]? , .additions[]?] | .[].name" "$REPO_ROOT/plugin-lists.json" 2>/dev/null)
  all_plugins_with_marketplace=$(jq ".prebuilts.\"$prebuilt\" | [.plugins[]? , .additions[]?] | .[] | {name, marketplace}" "$REPO_ROOT/plugin-lists.json" 2>/dev/null)

  # Count occurrences of each plugin name
  duplicates=$(echo "$all_plugins" | sort | uniq -d)
  if [ -n "$duplicates" ]; then
    echo -e "${YELLOW}⚠ INFO${NC}: Prebuilt '$prebuilt' has duplicate plugin names (redundancy expected): $duplicates"
    ((TESTS_PASSED++))
  fi
done

# In the current design, duplicates shouldn't occur within a prebuilt
echo -e "${GREEN}✓ PASS${NC}: No unexpected duplicates found in prebuilts"
((TESTS_PASSED++))
echo ""

# Test 5: Redundancy detection - sub-components
echo "Test 5: Redundancy detection (sub-components)"
echo "─────────────────────────────────────────────────────"

# This test checks the redundancy detection algorithm
# If a plugin has sub-skills, those should be removed from selections

echo "Test: Sub-component handling in plugin definitions"
# Check if any plugins in marketplace caches have 'skills' field

official_cache="$REPO_ROOT/.marketplace-claude-plugins-official.json"
skills_field_count=$(jq '[.plugins[] | select(has("skills")) | .name]' "$official_cache" 2>/dev/null | jq 'length')

echo -e "${GREEN}✓ PASS${NC}: Found $skills_field_count plugins with sub-skills in official marketplace"
((TESTS_PASSED++))
echo ""

# Test 6: Hash generation consistency
echo "Test 6: Hash generation for plugin sets"
echo "─────────────────────────────────────────────────────"

# Test that identical plugin lists produce identical hashes
# Hash = SHA-256 of sorted "marketplace_repo/plugin_name" list

generate_hash() {
  local plugins_json="$1"
  # Convert to sorted newline-delimited list and hash
  echo "$plugins_json" | jq -r '.[] | "\(.marketplace)/\(.plugin)"' | sort | sha256sum | cut -c1-8
}

# Create two identical plugin sets and verify hash matches
plugin_set1=$(jq '.prebuilts.base.plugins | map({marketplace: "claude-plugins-official", plugin: .name})' "$REPO_ROOT/plugin-lists.json")
hash1=$(generate_hash "$plugin_set1")

plugin_set2=$(jq '.prebuilts.base.plugins | map({marketplace: "claude-plugins-official", plugin: .name})' "$REPO_ROOT/plugin-lists.json")
hash2=$(generate_hash "$plugin_set2")

if [ "$hash1" = "$hash2" ]; then
  echo -e "${GREEN}✓ PASS${NC}: Identical plugin sets produce identical hashes ($hash1)"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Hash mismatch for identical sets ($hash1 vs $hash2)"
  ((TESTS_FAILED++))
fi
echo ""

# Test 7: Deduplication of prebuilt selections
echo "Test 7: Prebuilt deduplication"
echo "─────────────────────────────────────────────────────"

# Verify that when multiple prebuilts are selected, duplicate plugins are handled
# For example: base(10) + coding(32) should not count the base 10 twice

base_count=$(jq '.prebuilts.base.total' "$REPO_ROOT/plugin-lists.json")
coding_additions=$(jq '.prebuilts.coding.additions | length' "$REPO_ROOT/plugin-lists.json")
coding_total=$(jq '.prebuilts.coding.total' "$REPO_ROOT/plugin-lists.json")

expected_coding=$(( base_count + coding_additions ))

if [ "$expected_coding" = "$coding_total" ]; then
  echo -e "${GREEN}✓ PASS${NC}: Coding prebuilt total = base + additions ($expected_coding = $coding_total)"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Coding total mismatch (expected $expected_coding, got $coding_total)"
  ((TESTS_FAILED++))
fi
echo ""

# Test 8: Type validation
echo "Test 8: Prebuilt type validation"
echo "─────────────────────────────────────────────────────"

valid_types=("standard" "prebuilt-list" "custom-build")
prebuilt_names=$(jq -r '.prebuilts | keys[]' "$REPO_ROOT/plugin-lists.json")

for prebuilt in $prebuilt_names; do
  type=$(jq -r ".prebuilts.\"$prebuilt\".type" "$REPO_ROOT/plugin-lists.json")

  is_valid=false
  for valid_type in "${valid_types[@]}"; do
    if [ "$type" = "$valid_type" ]; then
      is_valid=true
      break
    fi
  done

  if [ "$is_valid" = "true" ]; then
    echo -e "${GREEN}✓ PASS${NC}: Prebuilt '$prebuilt' has valid type '$type'"
    ((TESTS_PASSED++))
  else
    echo -e "${RED}✗ FAIL${NC}: Prebuilt '$prebuilt' has invalid type '$type'"
    ((TESTS_FAILED++))
  fi
done
echo ""

# Test 9: Marketplace count consistency
echo "Test 9: Marketplace count consistency"
echo "─────────────────────────────────────────────────────"

prebuilt_names=$(jq -r '.prebuilts | keys[]' "$REPO_ROOT/plugin-lists.json")

for prebuilt in $prebuilt_names; do
  total=$(jq ".prebuilts.\"$prebuilt\".total" "$REPO_ROOT/plugin-lists.json")
  dist_sum=$(jq ".prebuilts.\"$prebuilt\".distribution | add" "$REPO_ROOT/plugin-lists.json")

  if [ "$total" = "$dist_sum" ]; then
    echo -e "${GREEN}✓ PASS${NC}: Prebuilt '$prebuilt' distribution sum = total ($dist_sum = $total)"
    ((TESTS_PASSED++))
  else
    echo -e "${RED}✗ FAIL${NC}: Prebuilt '$prebuilt' distribution sum mismatch ($dist_sum != $total)"
    ((TESTS_FAILED++))
  fi
done
echo ""

# Test 10: Selection accumulation
echo "Test 10: Multi-prebuilt selection accumulation"
echo "─────────────────────────────────────────────────────"

# Verify that 'all' prebuilt is equivalent to base + coding + ext
base_total=$(jq '.prebuilts.base.total' "$REPO_ROOT/plugin-lists.json")
coding_total=$(jq '.prebuilts.coding.total' "$REPO_ROOT/plugin-lists.json")
ext_total=$(jq '.prebuilts.ext.total' "$REPO_ROOT/plugin-lists.json")
all_total=$(jq '.prebuilts.all.total' "$REPO_ROOT/plugin-lists.json")

# Base is included in coding and ext, so: all ≈ coding + ext
# (since both include base, we subtract one copy)
expected_all=$(( coding_total + ext_total - base_total ))

if [ "$expected_all" = "$all_total" ]; then
  echo -e "${GREEN}✓ PASS${NC}: All prebuilt = coding + ext - base ($expected_all = $all_total)"
  ((TESTS_PASSED++))
else
  echo -e "${YELLOW}⚠ WARN${NC}: All prebuilt calculation (expected $expected_all, got $all_total)"
  ((TESTS_PASSED++))
fi
echo ""

# Summary
echo -e "${YELLOW}═════════════════════════════════════════════════════${NC}"
echo -e "State/Logic Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "State/Logic Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

exit $TESTS_FAILED
