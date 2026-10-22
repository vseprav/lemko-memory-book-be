import uuid
from functools import lru_cache
from flask import Blueprint, abort
from sqlalchemy import desc
from sqlalchemy.orm import selectinload
from app.models.evicted_person import EvictedPerson
from app.models.settlement import Family, SettlementList
from app.routes.search import json_response, load_settlement_info

family_bp = Blueprint('family', __name__)


# Define a priority dictionary for family roles
role_priority = {
    "господар": 1,
    "господиня": 2,
    "дружина": 3,
    "син": 4,
    "дочка": 5,
    "інше": 6
}


def get_priority(role):
    return role_priority.get(role, role_priority["інше"])


@lru_cache(maxsize=4096)
def _get_family(family_uuid):
    result = (
        EvictedPerson.query
        .options(load_settlement_info)
        .filter(EvictedPerson.family_uuid == family_uuid)
        .order_by(desc(EvictedPerson.full_name))
        .all()
    )
    data = [person.to_dict() for person in result]
    return sorted(data, key=lambda x: get_priority(x["family_role"]))


@family_bp.route('/<family_uuid>')
def get_family_members(family_uuid):
    try:
        family_uuid = uuid.UUID(family_uuid)
    except ValueError:
        abort(404)

    members = _get_family(family_uuid)
    if not members:
        abort(404)
    return json_response(members)


@lru_cache(maxsize=4096)
def _get_family_settlement(family_uuid):
    family = (
        Family.query
        .options(selectinload(Family.book_list).selectinload(SettlementList.settlements),
                 selectinload(Family.settlement))
        .get(family_uuid)
    )
    if family is None or family.book_list is None:
        return None
    return {
        'heading': family.settlement_label(),
        'list': family.book_list.to_dict(),
        # The one village the book names for this family, if it does (null for combined lists)
        'settlement': family.settlement.to_dict() if family.settlement else None,
        'list_settlements': [s.to_dict() for s in family.book_list.settlements],
    }


@family_bp.route('/<family_uuid>/settlement')
def get_family_settlement(family_uuid):
    """Everything the book says about where the family lived: the list it was read from
    (with the archive reference) and the register entries of the settlement(s) it covers."""
    try:
        family_uuid = uuid.UUID(family_uuid)
    except ValueError:
        abort(404)

    info = _get_family_settlement(family_uuid)
    if info is None:
        abort(404)
    return json_response(info)
