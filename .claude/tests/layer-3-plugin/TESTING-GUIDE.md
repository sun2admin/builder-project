# New-Plugin-Layer Skill Testing Guide

## Overview

Comprehensive test suite created to validate all functionality of the `new-plugin-layer` skill. This guide explains what tests were created, how to run them, and how to interpret results.

## What Tests Were Created

### 1. **Core Functionality Tests** (`test-new-plugin-layer.sh`)
- **Lines:** 700+ lines of test code
- **Test Cases:** 80+ individual assertions
- **Coverage:**
  - File existence validation (plugin-lists.json, standards.json, plugin-search.sh)
  - JSON file validation (all 6 marketplace cache files + config files)
  - Plugin-lists structure and completeness
  - Distribution accuracy (sums, counts, marketplace mapping)
  - Prebuilt consistency
  - Size estimation validation
  - Marketplace plugin availability (spot checks)
  
**Run Time:** 10-20 seconds

### 2. **Advanced Plugin Search Tests** (`test-plugin-search-advanced.sh`)
- **Lines:** 170+ lines of test code  
- **Test Cases:** 12+ search scenarios
- **Coverage:**
  - Search term variations (code, plugin, python, docker, git, etc.)
  - Case-insensitive matching validation
  - Substring matching behavior verification
  - Wildcard search ("*" returns all plugins)
  - Marketplace distribution in results
  - Empty and single-character searches
  - Special character handling
  - Search performance metrics (<5 seconds expected)

**Run Time:** 15-30 seconds

### 3. **State Management & Logic Tests** (`test-state-and-logic.sh`)
- **Lines:** 380+ lines of test code
- **Test Cases:** 20+ logic validations
- **Coverage:**
  - Prebuilt selection state tracking
  - Distribution verification per marketplace
  - Marketplace origin validation
  - Duplicate detection (conflict detection)
  - Sub-component redundancy detection
  - Hash generation consistency
  - Prebuilt deduplication logic
  - Type validation (standard, prebuilt-list, custom-build)
  - Multi-prebuilt accumulation correctness

**Run Time:** 10-15 seconds

### 4. **File Generation & I/O Tests** (`test-file-generation.sh`)
- **Lines:** 460+ lines of test code
- **Test Cases:** 25+ file operation validations
- **Coverage:**
  - JSON serialization of selections
  - plugin-manifest.json generation
  - Dockerfile generation and validation
  - GitHub Actions workflow generation
  - README.md creation
  - standards.json append operations
  - JSON formatting and readability
  - File structure preservation
  - Multi-file coordination

**Run Time:** 10-15 seconds

### 5. **Integration Tests** (`test-integration.sh`)
- **Lines:** 380+ lines of test code
- **Test Cases:** 18+ end-to-end scenarios
- **Coverage:**
  - Full plugin selection workflow
  - Marketplace data consistency
  - Conflict resolution flow
  - Size estimation calculations
  - Multiple prebuilt combinations
  - Selection distribution across marketplaces
  - Search-to-selection integration
  - Build deduplication via hashing
  - Standards/plugin-lists consistency
  - Error condition handling

**Run Time:** 15-25 seconds

### 6. **Test Runner** (`run-all-tests.sh`)
- **Lines:** 100+ lines
- **Purpose:** Execute all test suites in sequence with comprehensive summary
- **Features:**
  - Runs all 5 test suites
  - Aggregates results
  - Provides overall pass/fail status
  - Color-coded output
  - Detailed failure reporting

## Test Statistics

**Total Test Suite Size:** 2,000+ lines of code  
**Total Test Cases:** 150+ assertions  
**Coverage Areas:** 12 major components/features  
**Estimated Runtime:** 60-90 seconds (all tests)  

| Component | Tests | Coverage |
|---|---|---|
| Plugin Search | 12+ | Search functionality across all marketplaces |
| State Tracking | 10+ | Selection management and distribution |
| File Generation | 15+ | JSON, Dockerfile, workflows, config files |
| Data Consistency | 20+ | Marketplace data integrity and relationships |
| Logic Validation | 15+ | Hashing, deduplication, conflict detection |
| Integration | 18+ | End-to-end workflows and interactions |

## Running the Tests

### Quick Start
```bash
# Run all tests in sequence
bash tests/run-all-tests.sh

# Run individual test suite
bash tests/test-new-plugin-layer.sh
bash tests/test-plugin-search-advanced.sh
bash tests/test-state-and-logic.sh
bash tests/test-file-generation.sh
bash tests/test-integration.sh
```

### Interpreting Results

**Success Output:**
```
═══════════════════════════════════════════════════════════
SUCCESS: All functionality tests passed!
═══════════════════════════════════════════════════════════
```

**Failure Output:**
```
═══════════════════════════════════════════════════════════
FAILURE: Some tests failed. Review output above.
═══════════════════════════════════════════════════════════
  ✗ Test Suite Name (exit code: 1)
```

### Test Output Format

Each test case shows:
- `✓ PASS` - Test passed
- `✗ FAIL` - Test failed
- `⚠ WARN` - Warning (not a failure)
- `✓ INFO` - Informational (not a test result)

### Common Test Failures

| Symptom | Likely Cause | Fix |
|---|---|---|
| "File not found" | Missing marketplace cache or config | Run init-marketplace-cache.sh |
| "Invalid JSON" | Corrupted JSON in marketplace cache | Regenerate cache files |
| "Distribution mismatch" | plugin-lists.json out of sync | Verify distribution sums equal total |
| "Search returns 0 results" | Empty marketplace cache | Check .marketplace-*.json files |

## When to Run Tests

### Before Deployment
Always run the full test suite before deploying changes:
```bash
bash tests/run-all-tests.sh
```

### After Code Changes
Run tests after modifying:
- Plugin selection logic
- Marketplace data handling
- File generation code
- State management
- Search functionality

### In CI/CD Pipeline
Tests can be integrated into GitHub Actions:
```yaml
- name: Run Tests
  run: bash tests/run-all-tests.sh
```

## Test Philosophy

These tests validate:

✓ **Data Integrity** - All JSON files maintain correct structure  
✓ **Functionality** - Core operations work correctly  
✓ **Consistency** - Multiple data representations stay in sync  
✓ **Robustness** - Edge cases handled gracefully  
✓ **Performance** - Operations complete within acceptable time  

These tests do NOT validate:

✗ GitHub API interactions (too external)  
✗ Docker image builds (out of scope)  
✗ User interface/UX (tested manually)  
✗ Real marketplace data freshness (dynamic)  

## Test Maintenance

### Adding New Tests
1. Create new test file: `tests/test-<feature>.sh`
2. Use existing test functions:
   - `test_case()` - Label a test section
   - `assert_true()` - Test a condition
   - `assert_equals()` - Test equality
   - `assert_file_exists()` - Test file existence
   - `assert_json_valid()` - Test JSON validity

3. Add to run-all-tests.sh:
   ```bash
   run_test_suite "$SCRIPT_DIR/test-<feature>.sh" "Feature Name Tests"
   ```

### Updating Test Data
- **Marketplace caches** (`.marketplace-*.json`): Auto-generated, don't edit manually
- **plugin-lists.json**: Update when prebuilts change
- **standards.json**: Update when builds are created

### Debugging Failed Tests
```bash
# Run with verbose output
bash -x tests/test-new-plugin-layer.sh 2>&1 | head -100

# Check specific file
jq empty /workspace/claude/plugin-lists.json

# Validate marketplace data
jq '.plugins | length' /workspace/claude/.marketplace-claude-plugins-official.json
```

## Test Coverage Map

### Core Functionality
- ✓ File I/O (read/write JSON)
- ✓ JSON parsing and validation
- ✓ Data structure integrity
- ✓ Marketplace data loading

### Plugin Search
- ✓ Substring matching
- ✓ Case-insensitive search
- ✓ All 5 marketplaces queried
- ✓ Result formatting

### State Management
- ✓ Selection tracking
- ✓ Distribution mapping
- ✓ Prebuilt loading
- ✓ Multi-prebuilt combination

### Consistency
- ✓ Plugin-lists ↔ standards.json
- ✓ Distribution counts
- ✓ Marketplace origins
- ✓ Type validation

### Logic
- ✓ Conflict detection (duplicates)
- ✓ Redundancy detection (sub-skills)
- ✓ Hash generation
- ✓ Build deduplication

### File Generation
- ✓ JSON output
- ✓ Dockerfile syntax
- ✓ GitHub Actions workflows
- ✓ README generation

## Related Files

**Test Infrastructure:**
- `/workspace/claude/tests/` - Test suite directory
- `/workspace/claude/tests/README.md` - Test documentation
- `/workspace/claude/tests/TESTING-GUIDE.md` - This file

**Skill Files:**
- `/workspace/claude/.claude/commands/new-plugin-layer.md` - Skill spec
- `/workspace/claude/plugin-lists.json` - Prebuilt definitions
- `/workspace/claude/standards.json` - Named builds
- `/workspace/claude/scripts/plugin-search.sh` - Search implementation
- `/workspace/claude/.marketplace-*.json` - Marketplace caches (6 files)

## Future Improvements

### Potential Test Additions
- GitHub API interaction tests (with mocking)
- Docker build validation tests
- Performance benchmarking tests
- Concurrency/race condition tests
- Memory usage tests

### Test Optimization
- Parallel test execution
- Test result caching
- Faster search tests with smaller sample data
- Mocked GitHub API for faster CI

## Support

For test failures or issues:

1. **Check test output** - Most failures have clear error messages
2. **Verify data files** - Ensure marketplace caches are valid JSON
3. **Review test logic** - Read the specific test that's failing
4. **Check git status** - Ensure you're on the right branch

Example:
```bash
# Validate all JSON files
for f in *.json .marketplace-*.json; do
  jq empty "$f" && echo "✓ $f" || echo "✗ $f INVALID"
done
```

---

**Last Updated:** 2026-04-22  
**Test Suite Version:** 1.0  
**Total Coverage:** 12 major components, 150+ test cases
