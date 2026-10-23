from functools import lru_cache
from flask import Blueprint
from sqlalchemy import func
from app.extensions import db
from app.models.evicted_person import EvictedPerson
from app.models.settlement import Family, Settlement, settlement_list_settlements
from app.routes.search import json_response, PERSON_IN_LIST_SETTLEMENT

settlements_bp = Blueprint('settlements', __name__)


@lru_cache(maxsize=1)
def _settlements():
    """Every register entry with its people count (same match rule as the search filter)."""
    counts = dict(
        db.session.query(settlement_list_settlements.c.settlement_id, func.count(EvictedPerson.id))
        .select_from(EvictedPerson)
        .filter(EvictedPerson.row_kind == 'person')  # the same people the search finds
        .join(Family)
        .join(settlement_list_settlements, PERSON_IN_LIST_SETTLEMENT)
        .group_by(settlement_list_settlements.c.settlement_id)
        .all()
    )
    return [
        {
            'id': s.id,
            'name': s.name,
            'alt_names': list(s.alt_names),
            'note': s.note,
            'powiat_1939': s.powiat_1939,
            'count': counts.get(s.id, 0),
        }
        for s in Settlement.query.order_by(Settlement.name, Settlement.register_no)
    ]


@settlements_bp.route('')
@settlements_bp.route('/')
def settlements():
    return json_response(_settlements())
