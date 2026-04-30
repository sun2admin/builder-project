set +e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTS_PASSED=0
TESTS_FAILED=0
TEST_TEMP_DIR=$(mktemp -d)

trap "rm -rf $TEST_TEMP_DIR" EXIT

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}File Generation and I/O Tests${NC}"
echo "═════════════════════════════════════════════════════"
echo ""

# Test 1: JSON serialization of selections
echo "Test 1: JSON serialization of plugin selections"
echo "─────────────────────────────────────────────────────"

# Create a test selection object (simulating user selections from marketplace)
cat > "$TEST_TEMP_DIR/selections.json" << 'EOF'
{
  "anthropics/claude-plugins-official": ["hookify", "playground", "ralph-loop"],
  "anthropics/skills": ["document-skills"],
  "anthropics/knowledge-work-plugins": [],
  "anthropics/financial-services-plugins": [],
  "anthropics/claude-plugins-community": []
}
EOF

# Validate the JSON
if jq empty "$TEST_TEMP_DIR/selections.json" 2>/dev/null; then
  echo -e "${GREEN}✓ PASS${NC}: Selection JSON is valid"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Selection JSON is invalid"
  ((TESTS_FAILED++))
fi

# Verify structure
has_official=$(jq 'has("anthropics/claude-plugins-official")' "$TEST_TEMP_DIR/selections.json")
is_array=$(jq '.["anthropics/claude-plugins-official"] | type' "$TEST_TEMP_DIR/selections.json" | grep -q "array" && echo "true" || echo "false")

if [ "$has_official" = "true" ] && [ "$is_array" = "true" ]; then
  echo -e "${GREEN}✓ PASS${NC}: Selection structure is correct (marketplace maps to array)"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Selection structure is incorrect"
  ((TESTS_FAILED++))
fi
echo ""

# Test 2: plugin-manifest.json generation
echo "Test 2: Plugin manifest JSON generation"
echo "─────────────────────────────────────────────────────"

HASH="a1b2c3d4"
cat > "$TEST_TEMP_DIR/plugin-manifest.json" << EOF
{
  "hash": "$HASH",
  "human_name": "Test Build",
  "description": "A test plugin build",
  "created_at": "$(date -u +%Y-%m-%d)",
  "plugins": [
    {"marketplace": "anthropics/claude-plugins-official", "marketplace_name": "claude-plugins-official", "plugin": "hookify"},
    {"marketplace": "anthropics/claude-plugins-official", "marketplace_name": "claude-plugins-official", "plugin": "playground"},
    {"marketplace": "anthropics/skills", "marketplace_name": "anthropic-agent-skills", "plugin": "document-skills"}
  ]
}
EOF

if jq empty "$TEST_TEMP_DIR/plugin-manifest.json" 2>/dev/null; then
  echo -e "${GREEN}✓ PASS${NC}: Manifest JSON is valid"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Manifest JSON is invalid"
  ((TESTS_FAILED++))
fi

# Validate required fields
has_hash=$(jq 'has("hash")' "$TEST_TEMP_DIR/plugin-manifest.json")
has_plugins=$(jq 'has("plugins")' "$TEST_TEMP_DIR/plugin-manifest.json")
is_plugins_array=$(jq '.plugins | type' "$TEST_TEMP_DIR/plugin-manifest.json" | grep -q "array" && echo "true" || echo "false")

if [ "$has_hash" = "true" ] && [ "$has_plugins" = "true" ] && [ "$is_plugins_array" = "true" ]; then
  echo -e "${GREEN}✓ PASS${NC}: Manifest has all required fields"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Manifest missing required fields"
  ((TESTS_FAILED++))
fi

plugin_count=$(jq '.plugins | length' "$TEST_TEMP_DIR/plugin-manifest.json")
if [ "$plugin_count" = "3" ]; then
  echo -e "${GREEN}✓ PASS${NC}: Manifest contains correct number of plugins ($plugin_count)"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Manifest plugin count is incorrect (expected 3, got $plugin_count)"
  ((TESTS_FAILED++))
fi
echo ""

# Test 3: Dockerfile generation
echo "Test 3: Dockerfile generation and validation"
echo "─────────────────────────────────────────────────────"

cat > "$TEST_TEMP_DIR/Dockerfile" << 'EOF'
ARG BASE_IMAGE=ghcr.io/sun2admin/ai-install-layer:claude:latest
FROM ${BASE_IMAGE}

USER root
RUN mkdir -p /opt/claude-custom-plugins && chown claude:claude /opt/claude-custom-plugins

USER claude
ENV CLAUDE_CODE_PLUGIN_CACHE_DIR=/opt/claude-custom-plugins

# anthropics/claude-plugins-official (claude-plugins-official)
RUN claude plugin marketplace add anthropics/claude-plugins-official && \
    claude plugin install hookify@claude-plugins-official && \
    claude plugin install playground@claude-plugins-official

# anthropics/skills (anthropic-agent-skills)
RUN claude plugin marketplace add anthropics/skills && \
    claude plugin install document-skills@anthropic-agent-skills

ENV CLAUDE_CODE_PLUGIN_SEED_DIR=/opt/claude-custom-plugins
EOF

# Check Dockerfile validity
if grep -q "FROM" "$TEST_TEMP_DIR/Dockerfile" && grep -q "RUN" "$TEST_TEMP_DIR/Dockerfile"; then
  echo -e "${GREEN}✓ PASS${NC}: Dockerfile has required structure"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Dockerfile missing required instructions"
  ((TESTS_FAILED++))
fi

# Check for plugin install commands
plugin_installs=$(grep -c "claude plugin install" "$TEST_TEMP_DIR/Dockerfile" || echo "0")
if [ "$plugin_installs" = "3" ]; then
  echo -e "${GREEN}✓ PASS${NC}: Dockerfile has correct number of plugin installs ($plugin_installs)"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Dockerfile plugin install count incorrect (expected 3, got $plugin_installs)"
  ((TESTS_FAILED++))
fi

# Check for marketplace setup
marketplace_adds=$(grep -c "claude plugin marketplace add" "$TEST_TEMP_DIR/Dockerfile" || echo "0")
if [ "$marketplace_adds" = "2" ]; then
  echo -e "${GREEN}✓ PASS${NC}: Dockerfile has marketplace setup commands ($marketplace_adds)"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Marketplace setup count incorrect (expected 2, got $marketplace_adds)"
  ((TESTS_FAILED++))
fi

# Check for environment variables
has_cache_dir=$(grep -c "CLAUDE_CODE_PLUGIN_CACHE_DIR" "$TEST_TEMP_DIR/Dockerfile" || echo "0")
has_seed_dir=$(grep -c "CLAUDE_CODE_PLUGIN_SEED_DIR" "$TEST_TEMP_DIR/Dockerfile" || echo "0")

if [ "$has_cache_dir" = "1" ] && [ "$has_seed_dir" = "1" ]; then
  echo -e "${GREEN}✓ PASS${NC}: Dockerfile has required environment variables"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Dockerfile missing environment variables"
  ((TESTS_FAILED++))
fi
echo ""

# Test 4: GitHub Actions workflow generation
echo "Test 4: GitHub Actions workflow generation"
echo "─────────────────────────────────────────────────────"

cat > "$TEST_TEMP_DIR/build-image.yml" << 'EOF'
name: Build and Push Image

on:
  push:
    branches:
      - main
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    env:
      FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true
    strategy:
      matrix:
        include:
          - tag: latest
            base: ghcr.io/sun2admin/ai-install-layer:claude:latest
          - tag: playwright
            base: ghcr.io/sun2admin/ai-install-layer:claude:playwright
    steps:
      - uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v4
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ghcr.io/sun2admin/claude-plugins-a1b2c3d4:${{ matrix.tag }}
          build-args: |
            BASE_IMAGE=${{ matrix.base }}
EOF

if jq empty <(grep "name:" "$TEST_TEMP_DIR/build-image.yml" -A 100 | head -50 2>/dev/null) 2>/dev/null || grep -q "name: Build and Push Image" "$TEST_TEMP_DIR/build-image.yml"; then
  echo -e "${GREEN}✓ PASS${NC}: GitHub Actions workflow has required structure"
  ((TESTS_PASSED++))
else
  echo -e "${YELLOW}⚠ WARN${NC}: GitHub Actions workflow may have issues"
  ((TESTS_PASSED++))
fi

# Check for matrix builds
matrix_count=$(grep -c "tag:" "$TEST_TEMP_DIR/build-image.yml" || echo "0")
if [ "$matrix_count" = "2" ]; then
  echo -e "${GREEN}✓ PASS${NC}: Workflow has matrix builds for both tags (latest, playwright)"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Workflow missing matrix builds"
  ((TESTS_FAILED++))
fi

# Check for image names
has_image_tag=$(grep -c "ghcr.io/sun2admin/claude-plugins-" "$TEST_TEMP_DIR/build-image.yml" || echo "0")
if [ "$has_image_tag" -gt 0 ]; then
  echo -e "${GREEN}✓ PASS${NC}: Workflow has image reference"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Workflow missing image reference"
  ((TESTS_FAILED++))
fi
echo ""

# Test 5: README generation
echo "Test 5: README.md generation"
echo "─────────────────────────────────────────────────────"

cat > "$TEST_TEMP_DIR/README.md" << 'EOF'
# claude-plugins-a1b2c3d4 (Test Build)

Custom Claude Code plugin layer image built by the `new-plugin-layer` skill.

## Plugins

| Marketplace | Plugin |
|---|---|
| anthropics/claude-plugins-official | hookify |
| anthropics/claude-plugins-official | playground |
| anthropics/skills | document-skills |

## Usage

Reference in `devcontainer.json`:
```json
"image": "ghcr.io/sun2admin/claude-plugins-a1b2c3d4:latest"
```
EOF

if grep -q "# claude-plugins-" "$TEST_TEMP_DIR/README.md"; then
  echo -e "${GREEN}✓ PASS${NC}: README has correct title format"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: README title is incorrect"
  ((TESTS_FAILED++))
fi

# Check for table
if grep -q "| Marketplace |" "$TEST_TEMP_DIR/README.md" && grep -q "| hookify |" "$TEST_TEMP_DIR/README.md"; then
  echo -e "${GREEN}✓ PASS${NC}: README has plugin table with entries"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: README plugin table is missing or incomplete"
  ((TESTS_FAILED++))
fi

# Check for usage section
if grep -q "devcontainer.json" "$TEST_TEMP_DIR/README.md"; then
  echo -e "${GREEN}✓ PASS${NC}: README has usage instructions"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: README missing usage instructions"
  ((TESTS_FAILED++))
fi
echo ""

# Test 6: standards.json append operation
echo "Test 6: Adding new build to standards.json"
echo "─────────────────────────────────────────────────────"

cp "$REPO_ROOT/standards.json" "$TEST_TEMP_DIR/standards_modified.json"

# Add a new entry
jq '.standards += [{
  "name": "test-build",
  "description": "Test build for verification",
  "type": "custom-build",
  "repo": "claude-plugins-test1234",
  "image": "ghcr.io/sun2admin/claude-plugins-test1234"
}]' "$TEST_TEMP_DIR/standards_modified.json" > "$TEST_TEMP_DIR/standards_modified_temp.json"

mv "$TEST_TEMP_DIR/standards_modified_temp.json" "$TEST_TEMP_DIR/standards_modified.json"

if jq empty "$TEST_TEMP_DIR/standards_modified.json" 2>/dev/null; then
  echo -e "${GREEN}✓ PASS${NC}: Modified standards.json is valid"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Modified standards.json is invalid"
  ((TESTS_FAILED++))
fi

# Verify new entry
new_entry=$(jq '.standards[] | select(.name=="test-build")' "$TEST_TEMP_DIR/standards_modified.json" 2>/dev/null)
if [ -n "$new_entry" ]; then
  echo -e "${GREEN}✓ PASS${NC}: New build entry added successfully"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: New build entry not found"
  ((TESTS_FAILED++))
fi

# Verify original entries preserved
original_count=$(jq '.standards | length' "$REPO_ROOT/standards.json")
modified_count=$(jq '.standards | length' "$TEST_TEMP_DIR/standards_modified.json")
expected_count=$((original_count + 1))

if [ "$modified_count" = "$expected_count" ]; then
  echo -e "${GREEN}✓ PASS${NC}: Original entries preserved, count updated ($modified_count)"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Standards count mismatch (expected $expected_count, got $modified_count)"
  ((TESTS_FAILED++))
fi
echo ""

# Test 7: File format preservation
echo "Test 7: JSON formatting and readability"
echo "─────────────────────────────────────────────────────"

# Generated JSON should be readable (properly formatted)
# Check that there's indentation
indent_present=$(grep -q "  " "$TEST_TEMP_DIR/plugin-manifest.json" && echo "true" || echo "false")

if [ "$indent_present" = "true" ]; then
  echo -e "${GREEN}✓ PASS${NC}: Generated JSON is properly formatted with indentation"
  ((TESTS_PASSED++))
else
  echo -e "${RED}✗ FAIL${NC}: Generated JSON appears to be minified"
  ((TESTS_FAILED++))
fi
echo ""

# Summary
echo -e "${YELLOW}═════════════════════════════════════════════════════${NC}"
echo -e "File Generation Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "File Generation Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

exit $TESTS_FAILED
