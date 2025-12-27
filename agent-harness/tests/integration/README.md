# Integration Tests

Comprehensive integration tests for the Universal Agent Harness that verify end-to-end workflows and full system integration.

## Overview

This test suite contains 54 integration tests organized into 4 main test files, covering the complete system lifecycle from initialization through session execution and verification.

## Test Files

### 1. `test_session_lifecycle.py` (11 tests)
Tests the complete session orchestration from start to finish.

**Test Classes:**
- `TestSessionLifecycle` - Full session workflow tests
  - Successful session flow (preflight → agent → verification → state update)
  - Preflight failure handling
  - Checkpoint creation and state tracking
  - Error handling with rollback
  - Session state persistence across runs
  - Feature completion detection
  - Dry run mode
  - Progress tracking
  - Cost tracking

- `TestRunSessionHelper` - Helper function tests
  - Session orchestrator creation
  - Custom configuration handling

### 2. `test_init_workflow.py` (13 tests)
Tests project initialization workflows including new projects, adopting existing codebases, and resuming partial initializations.

**Test Classes:**
- `TestNewProjectInit` - New project creation
  - All required files created
  - Mode detection (auto/new)
  - Default features generation

- `TestAdoptExistingProject` - Existing codebase adoption
  - Detection of existing code
  - Preservation of existing files
  - Package manager file detection

- `TestResumePartialInit` - Partial initialization resumption
  - Existing harness directory handling
  - Validation of initialization results

- `TestInitWithAgent` - Agent execution during init
  - Mocked agent interaction
  - Features creation from agent output

- `TestInitHelper` - Helper function tests
  - init_project helper
  - Callback support

- `TestInitErrorHandling` - Error scenarios
  - Missing spec file
  - Validation errors

### 3. `test_verification_flow.py` (14 tests)
Tests the verification system including feature completion checking, regression detection, and rollback scenarios.

**Test Classes:**
- `TestFeatureVerification` - Feature completion verification
  - Successful verification
  - Test failure handling
  - Lint error detection

- `TestRegressionDetection` - Regression detection system
  - No regressions scenario
  - Regression detection and reporting
  - Standalone regression checking

- `TestFeaturesDiffValidation` - Features.json change validation
  - Single feature marking (valid)
  - Multiple features marking (invalid)
  - Single feature rule enforcement

- `TestQuickVerification` - Quick verification helpers
  - Quick feature verification success/failure
  - Nonexistent feature handling
  - Verify all features

- `TestVerificationWithRollback` - Verification triggering rollback
  - Session rollback on verification failure

### 4. `test_cli_integration.py` (16 tests)
Tests CLI command interactions and workflows.

**Test Classes:**
- `TestCLIInit` - Init command
  - Project creation via CLI
  - Mode option handling
  - Missing spec file errors

- `TestCLIRun` - Run command
  - Session execution
  - Dry run flag
  - Skip preflight flag

- `TestCLIStatus` - Status command
  - Project info display

- `TestCLIWorkflow` - Complete workflows
  - Init → run → status flow
  - Multiple session state increments

- `TestCLIErrorHandling` - Error handling
  - Commands without harness directory
  - Verbose flag
  - Project dir override

- `TestCLIPauseResume` - Pause/resume functionality
  - Command existence checks

- `TestCLICleanup` - Cleanup commands
  - Command existence checks

- `TestCLIVersion` - Version commands
  - Version display
  - Version subcommand

## Fixtures

### `conftest.py` - Shared Fixtures

**Project Setup:**
- `integration_project` - Complete project with all harness files, git repo, features, tests
- `sample_spec_file` - Sample specification file for init testing

**Mocks:**
- `mock_agent_runner` - Mocked AgentRunner (no API calls)
- `mock_claude_api` - Mocked Claude API client
- `mock_test_runner` - Mocked test runner for verification
- `mock_preflight_checks` - Mocked preflight checks
- `mock_checkpoint` - Mocked checkpoint creation and rollback

**Helpers:**
- `create_feature_dict` - Helper to create feature dictionaries
- `cleanup_integration_files` - Cleanup fixture for teardown

## Running Integration Tests

### Run all integration tests:
```bash
poetry run pytest tests/integration/ -v -m integration
```

### Run specific test file:
```bash
poetry run pytest tests/integration/test_session_lifecycle.py -v -m integration
```

### Run specific test class:
```bash
poetry run pytest tests/integration/test_session_lifecycle.py::TestSessionLifecycle -v -m integration
```

### Run specific test:
```bash
poetry run pytest tests/integration/test_session_lifecycle.py::TestSessionLifecycle::test_successful_session_flow -v -m integration
```

## Test Design Principles

### 1. Proper Cleanup
- All tests use `tmp_path` fixture for temporary directories
- Automatic cleanup after each test
- No state leakage between tests

### 2. External Service Mocking
- Claude API calls mocked via `mock_agent_runner`
- Git operations use real git but in temporary directories
- Test runner mocked for verification tests
- No actual API costs during testing

### 3. Independence
- Each test is fully independent
- Tests can run in any order
- No shared mutable state

### 4. Realistic Scenarios
- Tests use realistic project structures
- Feature files match production format
- State files include all required fields
- Git repositories properly initialized

### 5. Comprehensive Coverage
- Happy path tests
- Error scenarios
- Edge cases
- State persistence
- Rollback scenarios

## Known Issues / TODOs

### Minor Compatibility Issues
Some tests have minor data class signature mismatches that need adjustment:

1. **TestBaseline signature** - Tests use deprecated signature, needs update to:
   - `session: int` (required)
   - `timestamp: str` (auto-generated)
   - `passing_tests: list[str]`
   - `total_passing: int`
   - `total_tests: int`

2. **pytest.mark.integration** - Custom mark needs registration in `pyproject.toml`:
   ```toml
   [tool.pytest.ini_options]
   markers = [
       "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
   ]
   ```

3. **Import adjustments** - Some checkpoint imports need updating to match actual module exports

## Test Coverage

The integration tests cover:
- ✅ Session lifecycle (init → preflight → agent → verification → commit)
- ✅ Project initialization (new/adopt/resume modes)
- ✅ Verification system (feature tests, regressions, lint)
- ✅ CLI commands (init, run, status, version)
- ✅ State management (persistence, updates, rollback)
- ✅ Checkpoint system (creation, rollback)
- ✅ Cost tracking
- ✅ Progress logging
- ✅ Error handling and recovery
- ✅ Feature validation

## Contributing

When adding new integration tests:

1. **Use existing fixtures** - Reuse `integration_project`, `mock_agent_runner`, etc.
2. **Follow naming** - `test_<functionality>_<scenario>.py`
3. **Mark with @pytest.mark.integration** - Enables selective running
4. **Use tmp_path** - Never write to actual project directories
5. **Mock external services** - No real API calls
6. **Document test purpose** - Clear docstrings explaining what is being verified
7. **Clean up** - Ensure no files or state left behind

## Architecture Notes

The integration tests verify the following architectural flows:

```
Init Flow:
spec file → detect mode → run agent → create features.json → init state

Session Flow:
load state → preflight → create checkpoint → select feature →
run agent → verify → update state → update costs → commit

Verification Flow:
run feature tests → check regressions → run lint →
pass/fail → trigger rollback if needed

CLI Flow:
parse command → load config → execute operation →
display results → update state
```

Each test file focuses on one primary flow while using mocks to isolate the system under test.
