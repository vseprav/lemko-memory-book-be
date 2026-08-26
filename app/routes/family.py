import uuid
from functools import lru_cache
from flask import Blueprint, abort
from sqlalchemy import desc
from app.models.evicted_person import EvictedPerson
from app.routes.search import json_response

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
