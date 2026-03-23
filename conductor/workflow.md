# SolarIntel v2 — Development Workflow

## Development Methodology

### Test-Driven Development (TDD) — Mandatory

All implementation follows the Red-Green-Refactor cycle:

1. **Red**: Write a failing test that describes the desired behaviour
2. **Green**: Write the minimum code to make the test pass
3. **Refactor**: Clean up while keeping tests green

No production code is written without a corresponding test. This applies to:
- All FastAPI route handlers
- All service-layer functions (simulation, AI, PDF)
- All React components with user interaction
- All utility functions

### Architecture Decision Process

Major architectural decisions must be:
1. Documented as an ADR (Architecture Decision Record) in `docs/adr/`
2. Validated with an Opus 4.6 agent session before implementation
3. Approved via PR review before merging

## Git Workflow

### Branch Strategy

```
main          ← production-ready, protected
develop       ← integration branch (default PR target)
feature/<track-id>-<slug>   ← feature work (e.g. feature/INFRA-001-docker)
fix/<issue>   ← bug fixes
chore/<slug>  ← tooling, deps, docs
```

### Commit Conventions

Format: `<type>(<scope>): <imperative summary>`

Types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`, `ci`

Examples:
```
feat(sim): add pvlib irradiance calculation service
fix(auth): correct JWT expiry header parsing
test(pdf): add report layout snapshot tests
chore(deps): bump pvlib to 0.11.1
```

### Pull Request Rules

Every PR must:
- Target `develop` (not `main` directly)
- Reference the track ID in the title: `[SIM-001] Add pvlib simulation endpoint`
- Include a short description of what changed and why
- Pass all CI gates before merge (see CI Gates below)
- Have at least one reviewer approval
- Not exceed 400 lines changed (split large tracks into sub-PRs)

## CI Gates (GitHub Actions)

All gates run on every PR and push to `develop`/`main`.

### Python Backend Gates

| Gate | Tool | Command | Failure Action |
|------|------|---------|---------------|
| Lint | ruff | `ruff check .` | Block merge |
| Format | ruff | `ruff format --check .` | Block merge |
| Type check | mypy | `mypy app --strict` | Block merge |
| Unit tests | pytest | `pytest tests/ -x --cov=app --cov-fail-under=80` | Block merge |
| SAST | bandit | `bandit -r app/` | Block merge on HIGH severity |

### Frontend Gates

| Gate | Tool | Command | Failure Action |
|------|------|---------|---------------|
| Lint | ESLint | `eslint src/` | Block merge |
| Format | Prettier | `prettier --check src/` | Block merge |
| Type check | tsc | `tsc --noEmit` | Block merge |
| E2E tests | Playwright | `playwright test` | Block merge |

### Integration Gate

| Gate | Tool | Notes |
|------|------|-------|
| Docker build | docker compose build | Ensures images build cleanly |
| API contract | schemathesis | Runs against OpenAPI spec |

## Code Quality Standards

### Python

- **Max file length**: 300 lines per `.py` file. Larger files must be split by responsibility.
- **Type hints**: All function parameters and return types must be annotated.
- **Docstrings**: Google format on all public functions and classes.
- **Naming**: `snake_case` for variables/functions/modules, `PascalCase` for classes, `UPPER_SNAKE` for constants.
- **Imports**: `isort` ordering enforced by ruff (stdlib → third-party → local).

Example:
```python
async def calculate_yield(
    latitude: float,
    longitude: float,
    peak_power_kwp: float,
    *,
    tilt: float = 15.0,
    azimuth: float = 180.0,
) -> SimulationResult:
    """Calculate annual PV yield for a given location and system.

    Args:
        latitude: Site latitude in decimal degrees.
        longitude: Site longitude in decimal degrees.
        peak_power_kwp: System peak power in kWp.
        tilt: Panel tilt angle in degrees. Defaults to 15.0.
        azimuth: Panel azimuth in degrees (180 = south). Defaults to 180.0.

    Returns:
        SimulationResult with annual yield, monthly breakdown, and PR.

    Raises:
        PVGISError: If the PVGIS API request fails.
    """
```

### TypeScript / React

- **Strict mode**: `"strict": true` in tsconfig.json. No `any` types.
- **Max component length**: 200 lines per `.tsx` file. Extract sub-components and hooks.
- **Functional components only**: No class components.
- **Custom hooks**: Extract stateful logic into `use<Name>.ts` hooks.
- **Naming**: `camelCase` for variables/functions, `PascalCase` for components/types, `kebab-case` for CSS classes.
- **No inline styles**: Use Tailwind classes exclusively.

Example:
```tsx
interface SimulationResultCardProps {
  result: SimulationResult;
  onDownloadPdf: (projectId: string) => void;
}

export function SimulationResultCard({
  result,
  onDownloadPdf,
}: SimulationResultCardProps): JSX.Element {
  // ...
}
```

## Testing Requirements

### Backend (pytest)

- Coverage minimum: **80% line coverage** (CI enforced)
- Test file location: `backend/tests/<module>/test_<file>.py`
- Use `pytest-asyncio` for async route and service tests
- Use `httpx.AsyncClient` with `TestClient` for API tests
- Mock external APIs (PVGIS, Claude) with `respx` or `pytest-mock`
- Use factory functions in `tests/factories.py` for test data

### Frontend (Playwright)

- All user-facing flows must have E2E coverage
- Test file location: `frontend/e2e/<feature>.spec.ts`
- Use page object model for reusable page interactions
- Run against a local Docker Compose stack in CI

## Deployment Procedures

### Development

```bash
docker compose up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
# Docs: http://localhost:8000/docs
```

### Staging / Production (Railway.app)

1. Merge PR to `develop` → triggers CI
2. CI passes → auto-deploy to Railway staging environment
3. Manual promotion from staging → production via Railway dashboard
4. Database migrations run automatically via `alembic upgrade head` in Railway start command

### Database Migrations

```bash
# Generate migration
alembic revision --autogenerate -m "add projects table"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

## Session Continuity

### Starting a Session

1. Read `conductor/tracks.md` to find the active track
2. Read the track's `conductor/tracks/<track-id>/plan.md` for current task
3. Verify no dependency tracks are blocked
4. Run `docker compose up` to confirm environment health

### Ending a Session

1. Update task status in `plan.md` (`[ ]` → `[x]` or `[~]` if in progress)
2. Commit work-in-progress to feature branch
3. Update `conductor/tracks.md` if track status changed

### Task Status Markers

- `[ ]` — not started
- `[~]` — in progress
- `[x]` — complete
- `[!]` — blocked (add note with blocker)
