# Lemko Memory Book — Backend

## Run locally (with auto-reload)

One-time setup: create a `.env` file in this directory (git-ignored):

```
DATABASE_URI=postgresql://postgres:postgres@localhost:5432/lemko_memory_book
FLASK_APP=app
FLASK_DEBUG=1
FLASK_RUN_PORT=5001
```

Then start the server:

```bash
./run-local.sh              # auto-reload on code changes (default via FLASK_DEBUG=1)
./run-local.sh --reload     # force auto-reload on
./run-local.sh --no-reload  # run without auto-reload
./run-local.sh --port 5002  # any extra flags are passed through to `flask run`
```

The server runs on http://localhost:5001 and by default **restarts automatically
whenever a backend file changes**. Stop with Ctrl+C.

Health check: `curl http://localhost:5001/hello`

Point the frontend at it via `lemko-memory-book-fe/.env.local`:

```
REACT_APP_API_URL=http://localhost:5001
```

## Settlement data

`settlements`, `settlement_lists`, `settlement_list_settlements` and `families` hold the book's
register of settlements and name lists, and link every family to the list it was read from.
Migrations `0002` and `0003` create and fill them from `migrations/data/*.csv`, so `flask db upgrade`
(run by `startup.sh` on Azure) is all that is needed. The book is the source of truth: values are
stored as printed, nothing is corrected.

The CSVs are generated from the book HTML by the scripts in `../spec/settlements/tools`
(see `../spec/settlements/README.md`); regenerate them with:

```bash
cd ..   # the lemko folder
python3 spec/settlements/tools/make_seed_files.py lemko-memory-book-be/migrations/data
```

The `settlement` string in search and family responses is now the heading printed above the
book's list the family was read from (e.g. `Дошниця – Тиханя`).

## Search filters

`GET /search/evicted_persons` takes, besides `query`, `limit` and `offset`:

- `settlement=<settlements.id>`: people whose family the book places in that settlement, or whose
  family's list covers it without naming one village (so Дошниця also returns `Дошниця – Тиханя`).
- `area=<area_eviction>`: exact match on the area of eviction as printed (not normalized).

Filters work without `query`; the 3-character minimum applies to the text only. The response has
facets `last_names`, `area_evictions` and `settlements` (`[{id, name, note, count}]`, top 50 by count),
and each item carries `settlement_id` when the book points at exactly one register entry.

Dropdown data: `GET /settlements` (every register entry with alt names, note, 1939 powiat and people
count) and `GET /search/area_evictions` (every printed value with its count).

## Other commands

```bash
pip install -r requirements.txt      # install dependencies (inside venv)
flask db migrate -m "message"        # generate a migration
flask db upgrade                     # apply migrations
gunicorn wsgi:app                    # production-style run (no reload)
```

## Deployed (Azure) URLs

- Search: `https://memorybookbe.azurewebsites.net/search/evicted_persons?query=Кухар`
- Family: `https://memorybookbe.azurewebsites.net/family/c845a093-e33c-4da4-94f2-9d7924893718`
