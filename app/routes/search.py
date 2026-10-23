from functools import lru_cache
from flask import Blueprint, Response, request
import json
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import selectinload
from app.models.area import Area, Oblast
from app.models.evicted_person import EvictedPerson
from app.models.settlement import Family, Settlement, SettlementList, settlement_list_settlements

search_bp = Blueprint('search', __name__)

MAX_LIMIT = 50
MAX_FACETS = 50
MAX_QUERY_LEN = 100  # chars
MAX_WORDS = 5        # each word becomes an ILIKE clause
MIN_QUERY_LEN = 3    # applies to the text only; the filters work without text

# Names in the DB use both the typographic (’) and ASCII (') apostrophe
APOSTROPHES = "'’ʼ‘`"


CACHE_MAX_AGE = 86400  # data is static; let browsers/CDN cache responses for a day

EMPTY_RESULT = {'total': 0, 'last_names': [], 'area_evictions': [], 'oblasts': [], 'settlements': [], 'items': []}


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


# A person belongs to a settlement when the book names it for their family, or when the family's
# list covers it and the book does not single out one village (a combined list such as
# "Дошниця – Тиханя" counts for both). Used by the filter, the facet and GET /settlements.
PERSON_IN_LIST_SETTLEMENT = and_(
    settlement_list_settlements.c.list_id == Family.list_id,
    or_(Family.settlement_id.is_(None),
        Family.settlement_id == settlement_list_settlements.c.settlement_id),
)


def settlement_filter(settlement_id):
    covering_lists = (
        select(settlement_list_settlements.c.list_id)
        .where(settlement_list_settlements.c.settlement_id == settlement_id)
    )
    return or_(
        Family.settlement_id == settlement_id,
        and_(Family.settlement_id.is_(None), Family.list_id.in_(covering_lists)),
    )


@lru_cache(maxsize=2048)
def _search(search_query, settlement_id, area, oblast_id, limit, offset):
    # Every word must match somewhere in the name, in any order
    words = search_query.split()
    name_filters = [EvictedPerson.full_name.ilike(f"%{escape_for_like(word)}%") for word in words]

    def people(with_area=True, with_settlement=True):
        """People matching the text and, optionally, each filter. A facet leaves out its own
        filter so the dropdown keeps offering the alternatives (and their counts). Note rows
        ('Родина №7 - заклеєно стор. - 4 особи.') are not people and are never found."""
        query = EvictedPerson.query.filter(EvictedPerson.row_kind == 'person', *name_filters).join(Family)
        if area and with_area:
            query = query.filter(EvictedPerson.area_eviction == area)  # the value as printed in the book
        if oblast_id and with_area:
            # Every printed variant the book links to this oblast ("Сталінська", "Сталінська, нині Донецька", …)
            query = query.filter(EvictedPerson.area_id.in_(select(Area.id).where(Area.oblast_id == oblast_id)))
        if settlement_id and with_settlement:
            query = query.filter(settlement_filter(settlement_id))
        return query

    base_query = people()
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
    people_count = func.count(EvictedPerson.id).label('count')
    area_evictions = [
        {'value': row.area_eviction, 'count': row.count}
        for row in people(with_area=False)
        .filter(EvictedPerson.area_eviction.isnot(None))
        .with_entities(EvictedPerson.area_eviction, people_count)
        .group_by(EvictedPerson.area_eviction)
        .order_by(desc(people_count), EvictedPerson.area_eviction)
    ]
    oblasts = [
        {'id': row.id, 'name': row.name, 'modern_name': row.modern_name, 'count': row.count}
        for row in people(with_area=False)
        .join(Area, Area.id == EvictedPerson.area_id)
        .join(Oblast, Oblast.id == Area.oblast_id)
        .with_entities(Oblast.id, Oblast.name, Oblast.modern_name, people_count)
        .group_by(Oblast.id)
        .order_by(desc(people_count), Oblast.name)
    ]
    settlements = [
        {'id': row.id, 'name': row.name, 'note': row.note, 'count': row.count}
        for row in people(with_settlement=False)
        .join(settlement_list_settlements, PERSON_IN_LIST_SETTLEMENT)
        .join(Settlement, Settlement.id == settlement_list_settlements.c.settlement_id)
        .with_entities(Settlement.id, Settlement.name, Settlement.note, people_count)
        .group_by(Settlement.id)
        .order_by(desc(people_count), Settlement.name)
    ]

    # Names starting with the query rank first; then alphabetical.
    # Stable ordering is required for offset paging to return consistent pages.
    ordering = [EvictedPerson.full_name, EvictedPerson.id]
    if search_query:
        prefix_pattern = f"{escape_for_like(search_query)}%"
        ordering.insert(0, desc(EvictedPerson.full_name.ilike(prefix_pattern)))
    items = (
        base_query
        .options(load_settlement_info)
        .order_by(*ordering)
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        'total': total,
        'last_names': last_names,
        'area_evictions': area_evictions,  # printed values; kept for the frontend version before the oblast filter
        'oblasts': oblasts,
        'settlements': settlements,
        'items': [person.to_dict() for person in items],
    }


@search_bp.route('/evicted_persons')
def evicted_persons():
    search_query = ' '.join(request.args.get('query', '')[:MAX_QUERY_LEN].split()[:MAX_WORDS])
    settlement_id = request.args.get('settlement', 0, type=int)
    oblast_id = request.args.get('oblast', 0, type=int)
    area = ' '.join(request.args.get('area', '')[:MAX_QUERY_LEN].split())  # printed value; older frontend
    limit = min(request.args.get('limit', 20, type=int), MAX_LIMIT)
    offset = max(request.args.get('offset', 0, type=int), 0)

    if len(search_query) < MIN_QUERY_LEN:
        search_query = ''
    if not search_query and not settlement_id and not area and not oblast_id:
        return json_response(EMPTY_RESULT)

    return json_response(_search(search_query, settlement_id, area, oblast_id, limit, offset))


@lru_cache(maxsize=1)
def _area_evictions():
    people_count = func.count(EvictedPerson.id).label('count')
    return [
        {'value': row.area_eviction, 'count': row.count}
        for row in EvictedPerson.query
        .filter(EvictedPerson.area_eviction.isnot(None), EvictedPerson.row_kind == 'person')
        .with_entities(EvictedPerson.area_eviction, people_count)
        .group_by(EvictedPerson.area_eviction)
        .order_by(desc(people_count), EvictedPerson.area_eviction)
    ]


@search_bp.route('/area_evictions')
def area_evictions():
    """Every area of eviction as printed in the book, with its people count. Fills the filter dropdown."""
    return json_response(_area_evictions())
