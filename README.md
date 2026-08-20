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
