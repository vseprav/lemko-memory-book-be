`source venv/bin/activate`
`export DATABASE_URI="postgresql://url"`
`flask --app app run --debug`
`gunicorn wsgi:app`
`pip install -r requirements.txt`
`flask db init`
`flask db migrate -m "Added evicted persons model"`
# BE dev url
## Search route
`https://memorybookbe.azurewebsites.net/search/evicted_persons?query=Кухар`
## Family route
`https://memorybookbe.azurewebsites.net/family/c845a093-e33c-4da4-94f2-9d7924893718`
