# Contributing

## Commits

Use Conventional Commits:

```
<type>(<scope>): <short imperative summary>
```

Types: `feat`, `fix`, `security`, `refactor`, `test`, `docs`, `build`, `ci`,
`chore`. Scopes: `api`, `bridge`, `field`, `gateway`, `camera`, `frontend`,
`infra`, `docs`.

Examples:

```
fix(field): require pump cooldown after a max-ON cut
security(api): require device token on telemetry ingestion
```

## Before opening a change

```bash
cd backend/api && pytest tests -q
cd frontend && npm ci && npm run lint && npm test && npm run build
bash firmware/field/tools/run_logic_tests.sh
bash firmware/gateway/scripts/check_payloads.sh
cd firmware/field && pio run -e field
cd firmware/gateway && pio run -e gateway
cd firmware/camera && pio run -e camera
```

Never commit `.env`, `config/passwd`, `config/acl`,
`firmware/*/include/espnow_secrets.h`.
