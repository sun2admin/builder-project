# New-Plugin-Layer Comprehensive Test Suite

Complete test coverage for the `new-plugin-layer` skill, including unit tests, integration tests, and validation across all components.

## Test Suites

### 1. Core Functionality Tests (`test-new-plugin-layer.sh`)
**Coverage:** Basic file validation, JSON structure, and data consistency.

**Test Areas:**
- File existence (plugin-lists.json, standards.json, scripts)
- JSON validity (all marketplace caches and config files)
- Marketplace cache structure validation
- Plugin-lists structure and field completeness
- Distribution count accuracy
- Prebuilt-to-standards consistency
- Marketplace plugin existence (spot checks)
- Size estimation validation
- Edge case handling

**Typical Run Time:** 10-20 seconds
**Entry Point:** `bash .claude/tests/layer-3-plugin/test-new-plugin-layer.sh`

---

### 2. Advanced Plugin Search Tests (`test-plugin-search-advanced.sh`)
**Coverage:** Plugin search functionality across all marketplaces.

**Test Areas:**
- Search term variations (code, plugin, python, docker, git)
- Case-insensitive matching
- Substring matching behavior (anywhere in name/description)
- Wildcard search ("*" returns all plugins)
- Marketplace distribution in results
- Empty and single-character search handling
- Special character handling (dashes, etc.)
- Search performance metrics
- Consistent result ordering

**Typical Run Time:** 15-30 seconds
**Entry Point:** `bash .claude/tests/layer-3-plugin/test-plugin-search-advanced.sh`

---

### 3. State Management & Logic Tests (`test-state-and-logic.sh`)
**Coverage:** Plugin selection tracking, conflict detection, redundancy handling.

**Test Areas:**
- Prebuilt selection state tracking
- Distribution verification
- Marketplace origin validation
- Duplicate plugin detection (conflict detection)
- Sub-component redundancy detection
- Hash generation consistency
- Deduplication across multiple prebuilts
- Type validation (standard, prebuilt-list, custom-build)
- Marketplace count consistency
- Multi-prebuilt accumulation logic

**Typical Run Time:** 10-15 seconds
**Entry Point:** `bash .claude/tests/layer-3-plugin/test-state-and-logic.sh`

---

### 4. File Generation & I/O Tests (`test-file-generation.sh`)
**Coverage:** JSON creation, Dockerfile/workflow generation, file I/O operations.

**Test Areas:**
- Selection JSON serialization
- plugin-manifest.json generation and validation
- Dockerfile generation and instruction validity
- GitHub Actions workflow generation
- README.md creation
- standards.json append operations
- JSON formatting and readability
- File structure preservation
- Error handling for file operations

**Typical Run Time:** 10-15 seconds
**Entry Point:** `bash .claude/tests/layer-3-plugin/test-file-generation.sh`

---

### 5. Integration Tests (`test-integration.sh`)
**Coverage:** End-to-end workflows and component interactions.

**Test Areas:**
- Full plugin selection workflow
- Marketplace data consistency across all steps
- Conflict resolution workflow
- Size estimation calculations
- Multiple prebuilt combination scenarios
- Marketplace selection distribution
- Search results integration into selections
- Build deduplication via hashing
- Standards vs plugin-lists consistency
- Graceful edge case handling

**Typical Run Time:** 15-25 seconds
**Entry Point:** `bash .claude/tests/layer-3-plugin/test-integration.sh`

---

## Running Tests

### Run All Tests
```bash
bash .claude/tests/layer-3-plugin/run-all-tests.sh
```
Executes all five test suites in sequence with comprehensive summary.

### Run Individual Test Suite
```bash
bash .claude/tests/layer-3-plugin/test-new-plugin-layer.sh
bash .claude/tests/layer-3-plugin/test-plugin-search-advanced.sh
bash .claude/tests/layer-3-plugin/test-state-and-logic.sh
bash .claude/tests/layer-3-plugin/test-file-generation.sh
bash .claude/tests/layer-3-plugin/test-integration.sh
```

### Run Tests with Verbose Output
```bash
bash -x .claude/tests/layer-3-plugin/run-all-tests.sh
```

---

## Test Coverage Map

| Component | Tests |
|---|---|
| **File I/O** | test-new-plugin-layer (✓), test-file-generation (✓), test-integration (✓) |
| **JSON Validation** | test-new-plugin-layer (✓), test-file-generation (✓), test-state-and-logic (✓) |
| **Plugin Search** | test-plugin-search-advanced (✓), test-integration (✓) |
| **State Tracking** | test-state-and-logic (✓), test-integration (✓) |
| **Marketplace Data** | test-new-plugin-layer (✓), test-integration (✓) |
| **Conflict Detection** | test-state-and-logic (✓), test-integration (✓) |
| **Redundancy Detection** | test-state-and-logic (✓) |
| **Hash Generation** | test-state-and-logic (✓), test-integration (✓) |
| **Dockerfile Generation** | test-file-generation (✓) |
| **GitHub Actions** | test-file-generation (✓) |
| **README Generation** | test-file-generation (✓) |
| **Multi-Prebuilt Logic** | test-state-and-logic (✓), test-integration (✓) |

---

## Key Validation Patterns

### Marketplace Cache Validation
- All 5 marketplace cache files exist and contain valid JSON
- Each marketplace has `name` and `plugins` fields
- Plugin counts are consistent with declarations

### Plugin-Lists Consistency
- All prebuilt definitions have required fields
- Distribution maps sum correctly to total
- Plugin references match marketplace origins
- Includes/additions relationships are valid

### State Tracking
- Selections map tracks plugins by marketplace
- Distribution counts match plugin allocations
- Prebuilt combinations don't double-count base plugins
- Hash generation is deterministic and unique per selection

### File Generation
- Generated JSON is valid and properly formatted
- Dockerfile contains required marketplace setup and plugin installs
- GitHub Actions workflow has matrix builds for latest and playwright
- README includes usage instructions

---

## Troubleshooting

### Test Failures
1. **"File not found"** → Check that all required files exist in `.claude/commands/new-plugin-layer/`
2. **"Invalid JSON"** → Use `jq empty <file>` to identify specific issues
3. **"Search returns no results"** → Check marketplace cache files are populated
4. **"Distribution mismatch"** → Verify plugin-lists.json distribution sums equal totals

### Performance Issues
- Search tests may take 20-30s if marketplace caches are large
- Use individual test scripts if running all tests is slow
- Cache files are read-only; no generation overhead

---

## Maintenance

### When to Run
- Before deploying changes to the `new-plugin-layer` skill
- After updating marketplace cache files
- When adding new prebuilt definitions
- As part of CI/CD pipeline

### Adding New Tests
1. Create test file: `tests/test-<feature>.sh`
2. Use existing test framework functions (assert_true, assert_equals, etc.)
3. Add to run-all-tests.sh execution list
4. Document in this README

### Updating Test Data
- Marketplace caches (`.marketplace-*.json`): Auto-generated, don't edit manually
- plugin-lists.json: Update when prebuilts change, keep distribution sums correct
- standards.json: Update when builds are created

---

## Test Statistics

**Total Test Suites:** 5
**Estimated Total Test Cases:** 80+
**Average Runtime:** 60-90 seconds (all tests)
**Coverage Areas:** 12 major components
**Lines of Test Code:** 1000+

---

## Related Files

- `.claude/commands/new-plugin-layer/plugin-lists.json` - Prebuilt definitions with marketplace distributions
- `.claude/commands/new-plugin-layer/standards.json` - Named builds and saves
- `.claude/commands/new-plugin-layer/.marketplace-*.json` - Marketplace plugin caches (5 files)
- `.claude/commands/new-plugin-layer/` - new-plugin-layer command/skill

---

## Test Philosophy

These tests validate:
1. **Data Integrity** - All JSON files maintain correct structure and relationships
2. **Functionality** - Core operations (search, selection, hashing) work correctly
3. **Consistency** - Multiple representations of the same data stay in sync
4. **Robustness** - Edge cases and error conditions are handled gracefully
5. **Performance** - Operations complete within acceptable timeframes

Tests are **not** intended to validate:
- GitHub API interactions (too external)
- Docker image builds (out of scope)
- User interface/UX (tested manually)
- Real marketplace data freshness (dynamic)

---

## Exit Codes

- `0` - All tests passed
- `1` - One or more test suites failed

Individual test scripts exit with the count of failed tests (0 = all passed).
