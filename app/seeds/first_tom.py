from flask.cli import with_appcontext
import click
from app.extensions import db
from app.models.evicted_person import EvictedPerson
import pandas as pd


@click.command(name='seed_db')
@with_appcontext
def seed_evicted_persons():
    # Read the CSV file
    df = pd.read_csv('./app/seeds/evicted_persons_tom1.csv')
    # Iterate over DataFrame rows and save to database
    for index, row in df.iterrows():
        person = EvictedPerson(
            id=row['id'],
            family_uuid=row['family_uuid'],
            full_name=row['full_name'],
            family_role=row['family_role'],
            birth_year=row['birth_year'],
            area_eviction=row['area_eviction'],
            settlement=row['settlement']
        )
        db.session.add(person)

    # Commit the session to save all objects to the database
    db.session.commit()
