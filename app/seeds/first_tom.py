from pathlib import Path

from flask.cli import with_appcontext
import click
from app.extensions import db
from app.models.area import Area
from app.models.evicted_person import EvictedPerson
from app.models.settlement import Family
import pandas as pd

# family_uuid -> book list / settlement, same file migration 0003 loads
FAMILY_LISTS_CSV = Path(__file__).resolve().parents[2] / 'migrations' / 'data' / 'family_lists.csv'


@click.command(name='seed_db')
@with_appcontext
def seed_evicted_persons():
    # Read the CSV file
    df = pd.read_csv('./app/seeds/evicted_persons_tom1.csv')

    # Every person must belong to a family row (foreign key), so create those first
    mapping = pd.read_csv(FAMILY_LISTS_CSV, dtype=str, keep_default_na=False).set_index('family_uuid')
    for family_uuid in df['family_uuid'].unique():
        if db.session.get(Family, family_uuid) is not None:
            continue
        row = mapping.loc[family_uuid] if family_uuid in mapping.index else None
        db.session.add(Family(
            family_uuid=family_uuid,
            list_id=int(row['list_id']) if row is not None and row['list_id'] else None,
            settlement_id=int(row['settlement_id']) if row is not None and row['settlement_id'] else None,
        ))
    # Each printed area value maps to an areas row (migration 0004); unknown values are added unlinked
    areas = {a.printed: a for a in Area.query}
    for value in df['area_eviction'].dropna().unique():
        if value and value not in areas:
            areas[value] = Area(printed=value)
            db.session.add(areas[value])
    db.session.flush()

    # Iterate over DataFrame rows and save to database
    for index, row in df.iterrows():
        area = areas.get(row['area_eviction'])
        person = EvictedPerson(
            id=row['id'],
            family_uuid=row['family_uuid'],
            full_name=row['full_name'],
            family_role=row['family_role'],
            birth_year=row['birth_year'],
            area_eviction=row['area_eviction'],
            area_id=area.id if area else None,
            settlement=row['settlement']
        )
        db.session.add(person)

    # Commit the session to save all objects to the database
    db.session.commit()
