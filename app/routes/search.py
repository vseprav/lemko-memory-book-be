from flask import Blueprint, request
from sqlalchemy import desc
from app.models.evicted_person import EvictedPerson

search_bp = Blueprint('search', __name__)

@search_bp.route('/evicted_persons')
def evicted_persons():
    search_query = request.args.get('query', '')

    like_pattern = f"%{search_query}%"
    result = (
        EvictedPerson.query
        .filter(EvictedPerson.full_name.like(like_pattern))
        .order_by(desc(EvictedPerson.family_uuid))
        .all()
    )
    serialized_result = [person.to_dict() for person in result]

    return serialized_result
