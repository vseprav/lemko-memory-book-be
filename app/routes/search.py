from flask import Blueprint, Response, request
import json
from sqlalchemy import desc
from app.models.evicted_person import EvictedPerson

search_bp = Blueprint('search', __name__)

MAX_LIMIT = 300

# Names in the DB use both the typographic (’) and ASCII (') apostrophe
APOSTROPHES = "'’ʼ‘`"


def json_response(data):
    return Response(json.dumps(data, ensure_ascii=False), mimetype='application/json; charset=utf-8')


def escape_for_like(text):
    chars = []
    for ch in text:
        if ch in APOSTROPHES:
            chars.append('_')  # match any apostrophe variant
        elif ch in ('%', '_', '\\'):
            chars.append('\\' + ch)
        else:
            chars.append(ch)
    return ''.join(chars)


@search_bp.route('/evicted_persons')
def evicted_persons():
    search_query = request.args.get('query', '').strip()
    limit = min(request.args.get('limit', 20, type=int), MAX_LIMIT)
    offset = max(request.args.get('offset', 0, type=int), 0)

    if not search_query or len(search_query) < 3:
        return json_response({'total': 0, 'last_names': [], 'area_evictions': [], 'items': []})

    # Every word must match somewhere in the name, in any order
    words = search_query.split()
    filters = [EvictedPerson.full_name.ilike(f"%{escape_for_like(word)}%") for word in words]
    base_query = EvictedPerson.query.filter(*filters)

    total = base_query.count()

    last_names = []
    area_evictions = []
    seen_names = set()
    seen_areas = set()
    for full_name, area in base_query.with_entities(EvictedPerson.full_name, EvictedPerson.area_eviction):
        last_name = full_name.split(' ')[0].strip()
        if last_name not in seen_names:
            seen_names.add(last_name)
            last_names.append(last_name)
        if area and area not in seen_areas:
            seen_areas.add(area)
            area_evictions.append(area)

    # Names starting with the query rank first; then alphabetical.
    # Stable ordering is required for offset paging to return consistent pages.
    prefix_pattern = f"{escape_for_like(search_query)}%"
    items = (
        base_query
        .order_by(
            desc(EvictedPerson.full_name.ilike(prefix_pattern)),
            EvictedPerson.full_name,
            EvictedPerson.id,
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return json_response({
        'total': total,
        'last_names': last_names,
        'area_evictions': area_evictions,
        'items': [person.to_dict() for person in items],
    })
