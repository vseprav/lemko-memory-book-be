from functools import lru_cache
from flask import Blueprint
from sqlalchemy import desc, func
from app.models.area import Area, Oblast
from app.models.evicted_person import EvictedPerson
from app.routes.search import json_response

oblasts_bp = Blueprint('oblasts', __name__)


@lru_cache(maxsize=1)
def _oblasts():
    """Every destination oblast with its people count, counting all the printed variants the
    book links to it. Fills the area filter dropdown."""
    people_count = func.count(EvictedPerson.id).label('count')
    return [
        {**oblast.to_dict(), 'count': count}
        for oblast, count in Oblast.query
        .join(Area, Area.oblast_id == Oblast.id)
        .join(EvictedPerson, EvictedPerson.area_id == Area.id)
        .with_entities(Oblast, people_count)
        .group_by(Oblast.id)
        .order_by(desc(people_count), Oblast.name)
    ]


@oblasts_bp.route('')
@oblasts_bp.route('/')
def oblasts():
    return json_response(_oblasts())
