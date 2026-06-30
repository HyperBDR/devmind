# LLM Ops Official Price Reset Runbook

## Purpose

Use this runbook to remove dirty official price data that was produced by
legacy seed/sync behavior, then resync official provider price catalogs.

The reset preserves:

- `LLMProvider`
- `MetaModel`
- provider-level official sources such as `aliyun-official`
- manual price sources
- supplier price sources
- procurement channels and resale configuration

The reset removes or clears:

- legacy model-level official sources such as `aliyun-qwen-max-official`
- official `ModelPriceItem` rows
- official collection snapshots and history
- official collection runs
- official price fields on `LLMModel`

## Safety Rules

Always run `--dry-run` first and save the output in the operation record.

Run a database backup before using `--yes` in production.

The command refuses to run without an explicit scope. Use either
`--provider <code>` or `--all`.

## Preview

Preview one provider:

```bash
python backend/manage.py reset_llm_ops_official_prices \
  --dry-run \
  --provider aliyun
```

Preview all supported official providers:

```bash
python backend/manage.py reset_llm_ops_official_prices \
  --dry-run \
  --all
```

Review these counters before continuing:

- `legacy_sources_deleted`
- `models_reset`
- `price_items_deleted`
- `snapshots_deleted`
- `history_deleted`
- `runs_deleted`

## Execute

Reset and resync one provider:

```bash
python backend/manage.py reset_llm_ops_official_prices \
  --yes \
  --provider aliyun \
  --sync
```

Reset and resync all supported official providers:

```bash
python backend/manage.py reset_llm_ops_official_prices \
  --yes \
  --all \
  --sync
```

If the production environment cannot reach official source pages during the
operation window, use:

```bash
python backend/manage.py reset_llm_ops_official_prices \
  --yes \
  --provider aliyun \
  --sync \
  --skip-source-check
```

## Docker Example

For the production compose service, run the command inside the backend API
container:

```bash
docker compose exec -T backend-api \
  python manage.py reset_llm_ops_official_prices --dry-run --provider aliyun
```

Then execute:

```bash
docker compose exec -T backend-api \
  python manage.py reset_llm_ops_official_prices --yes --provider aliyun --sync
```

## Post-Checks

Open `/llm-ops` and confirm:

- the provider drawer shows one official price source per provider
- model-level official sources no longer appear
- model price rows are repopulated under the provider-level source

For Aliyun, the expected official source is `aliyun-official`.
