from flask import Blueprint, Response, request
import json
from sqlalchemy import desc
from app.models.evicted_person import EvictedPerson

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


@family_bp.route('/<family_uuid>')
def get_family_members(family_uuid):
    print(family_uuid)
    result = (
        EvictedPerson.query
        .filter(EvictedPerson.family_uuid == family_uuid)
        .order_by(desc(EvictedPerson.full_name))
        .all()
    )

    data = [person.to_dict() for person in result]
    sorted_data = sorted(data, key=lambda x: get_priority(x["family_role"]))
    response_body = json.dumps(sorted_data, ensure_ascii=False)

    return Response(response_body, mimetype='application/json; charset=utf-8')
