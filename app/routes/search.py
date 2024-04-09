from flask import Blueprint, request
# from app.models.evicted_person import EvictedPerson

search_bp = Blueprint('search', __name__)

@search_bp.route('/evicted_persons')
def evicted_persons():
    search_query = request.args.get('query', '')
    return search_query
#     result = EvictedPerson.query.filter(EvictedPerson.full_name == search_query).all()
#
#     return result
