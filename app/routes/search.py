from functools import lru_cache
from flask import Blueprint, Response, request
import json
from sqlalchemy import desc, func
from sqlalchemy.orm import selectinload
from app.models.evicted_person import EvictedPerson
from app.models.settlement import Family, SettlementList

search_bp = Blueprint('search', __name__)

MAX_LIMIT = 50
MAX_FACETS = 50
MAX_QUERY_LEN = 100  # chars
MAX_WORDS = 5        # each word becomes an ILIKE clause

# Names in the DB use both the typographic (’) and ASCII (') apostrophe
APOSTROPHES = "'’ʼ‘`"


CACHE_MAX_AGE = 86400  # data is static; let browsers/CDN cache responses for a day


def json_response(data, status=200):
    resp = Response(json.dumps(data, ensure_ascii=False), status=status,
                    mimetype='application/json; charset=utf-8')
    resp.headers['Cache-Control'] = f'public, max-age={CACHE_MAX_AGE}'
    return resp


# Loads family -> list -> settlements for a page of people in a few queries instead of one per person
load_settlement_info = selectinload(EvictedPerson.family).options(
    selectinload(Family.book_list).selectinload(SettlementList.settlements),
    selectinload(Family.settlement),
)


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


@lru_cache(maxsize=2048)
def _search(search_query, limit, offset):
    # Every word must match somewhere in the name, in any order
    words = search_query.split()
    filters = [EvictedPerson.full_name.ilike(f"%{escape_for_like(word)}%") for word in words]
    base_query = EvictedPerson.query.filter(*filters)

    total = base_query.with_entities(func.count()).scalar()

    # Facets computed in SQL instead of loading every matching row into Python
    last_name_expr = func.split_part(EvictedPerson.full_name, ' ', 1).label('last_name')
    last_names = [
        row.last_name for row in base_query
        .with_entities(last_name_expr)
        .distinct()
        .order_by(last_name_expr)
        .limit(MAX_FACETS)
    ]
    area_evictions = [
        row.area_eviction for row in base_query
        .filter(EvictedPerson.area_eviction.isnot(None))
        .with_entities(EvictedPerson.area_eviction)
        .distinct()
        .order_by(EvictedPerson.area_eviction)
        .limit(MAX_FACETS)
    ]

    # Names starting with the query rank first; then alphabetical.
    # Stable ordering is required for offset paging to return consistent pages.
    prefix_pattern = f"{escape_for_like(search_query)}%"
    items = (
        base_query
        .options(load_settlement_info)
        .order_by(
            desc(EvictedPerson.full_name.ilike(prefix_pattern)),
            EvictedPerson.full_name,
            EvictedPerson.id,
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        'total': total,
        'last_names': last_names,
        'area_evictions': area_evictions,
        'items': [person.to_dict() for person in items],
    }


@search_bp.route('/evicted_persons')
def evicted_persons():
    search_query = ' '.join(request.args.get('query', '')[:MAX_QUERY_LEN].split()[:MAX_WORDS])
    limit = min(request.args.get('limit', 20, type=int), MAX_LIMIT)
    offset = max(request.args.get('offset', 0, type=int), 0)

    if not search_query or len(search_query) < 3:
        return json_response({'total': 0, 'last_names': [], 'area_evictions': [], 'items': []})

    return json_response(_search(search_query, limit, offset))
