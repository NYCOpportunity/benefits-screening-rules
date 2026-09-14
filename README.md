# Benefits Screening Rules

Refactor of the Benefits Screening program rules code in Python

## File Map

```
benefits-screening-rules/
├── src/
│   ├── models/
│   │   ├── enums.py                           # Fixed-value enums (income types, etc.)
│   │   └── schemas.py                         # Schemas for AggregateEligibilityRequest
│   ├── rules/
│   │   ├── program_rules/                     # Individual program rule implementations
│   │   ├── aggregate_eligibility_helper.py    # Funcs for AggregateEligibilityRequest
│   │   ├── base_rule.py                       # Parent class for program_rules
│   │   ├── calculate_eligibility.py           # Main eligibility calculation logic
│   │   └── registry.py                        # Auto-registers all rules
│   ├── utils/
│   │   └── drools_converter.py                # Backwards compatibility for Drools JSON
│   ├── validation/
│   │   └── parse_request.py                 # Parse JSON into typed request models
│   └── main.py                                # Application entry point
├── tests/
│   ├── data/
│   │   ├── legacy-drools-payloads/            # Legacy Drools JSON test files
│   │   └── payloads/                          # Expected JSON payload test files
│   ├── e2e/
│   │   └── test_load_gateway.py               # E2E, load & performance tests
│   ├── integration/                           # Integration test suite
│   ├── unit/
│   │   ├── rules/                             # Program rule unit tests
│   │   └── validations/                       # Request validation tests
│   └── utils/                                 # Test utilities
├── pyproject.toml                             # Python project configuration
├── pytest.ini                                 # PyTest configuration
├── README.md                                  # Project documentation
└── uv.lock                                    # Dependency lock file
```

## Flow Diagram 

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Receive JSON   │───▶│  parse_request  │───▶│ calculate_      │───▶│   get_rules()   │───▶│ Evaluate Rules  │───▶│   Return 200    │
│    Payload      │    │ (parse_request  │    │  eligibility    │    │  (registry.py)  │    │ (program_rules/)│    │ Eligible Program│
│   (main.py)     │    │      .py)       │    │ (calculate_     │    │                 │    │                 │    │      List       │
└─────────┬───────┘    └─────────────────┘    │ eligibility.py) │    └─────────────────┘    └─────────────────┘    └─────────────────┘
          │  ▲                                └─────────────────┘
          │  │  (if legacy
          ▼  │   Drools JSON format)
┌─────────────────┐
│ convert_drools_ │
│  to_api_format  │
│   (drools_      │
│  converter.py)  │
└─────────────────┘

```

## Setup Instructions

1. **Install uv package manager:**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   **Note:** Can also install it with pip: `pip install uv` or brew: `brew install uv`

2. **Install dependencies and create virtual environment:**
   ```bash
   uv sync
   ```

3. **Activate the virtual environment:**
   ```bash
   source .venv/bin/activate
   ```

4. **Set  `.env` file by copying `.env.example`:**

```bash
GATEWAY_URL=your-api-gateway-url
```

5. **Run the application:**
   ```bash
   uv run python src/main.py
   ```

## Test Instructions

Run tests using uv with PyTest:
```bash
uv run pytest tests/
```

### E2E Load Tests

**Basic load test:**
```bash
uv run tests/e2e/test_load_gateway.py
```
**Available (optional) flags:**
- `--legacy-drools`: Use legacy format payloads vs converted payloads
- `--sequential`: Test each payload separately vs mixed load test
- `--num-requests N`: Total requests to send
- `--workers N`: Concurrent threads

## Deployment

Automated deployment via branch merges:

- **Staging:** Merge to `stg` → deploys to staging Lambda
- **Production:** Merge to `prod` → deploys to production Lambda

**Workflow:** Feature branch → PR → `stg` → test → `prod`


## How to add a rule
1. Create a new file under [`program_rules`](src/rules/program_rules) titled as the program code, and modify the program and description to match the new rule. I recommend just duplicating an existing file and renaming it. 
2. Write the rule logic `evaluate` method. This method will take in an `AggregateEligibilityRequest` under the `request` parameter, use this to write the rule logic. Feel free to create helper functions within the class to compute values, but `evaluate` must return true or false
3. Your new rule will be auto-registered under the registry system, allowing it to be iterated through when checking all rules. It will also be auto-registered in the unit test, make sure to update the data for expected values on different test requests. 
