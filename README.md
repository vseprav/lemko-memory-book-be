`source venv/bin/activate`
`flask --app app run --debug`
`gunicorn wsgi:app`
`pip install -r requirements.txt`
`flask db init`
`flask db migrate -m "Added evicted persons model"`
# BE dev url
https://memorybookbe.azurewebsites.net/search/evicted_persons?query=Кухар
