import uuid
from functools import lru_cache
from flask import Blueprint, abort
from sqlalchemy import desc
from sqlalchemy.orm import selectinload
from app.extensions import db
from app.models.evicted_person import EvictedPerson
from app.models.settlement import Family, FamilyAlias, SettlementList
from app.routes.search import json_response, load_settlement_info

family_bp = Blueprint('family', __name__)


# Member order for families the data repair has not given a book position yet (a database loaded
# before lemko/spec/data-audit was applied); repaired families come in the order the book prints them.
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


def parse_family_uuid(value):
    try:
        return uuid.UUID(value)
    except ValueError:
        abort(404)


@lru_cache(maxsize=4096)
def resolve_family_uuid(family_uuid):
    """The family to show for a uuid: itself, or the family it was merged into by the data repair,
    so that links to retired family pages keep working. None when the uuid is unknown."""
    if db.session.get(Family, family_uuid) is not None:
        return family_uuid
    alias = db.session.get(FamilyAlias, family_uuid)
    return alias.family_uuid if alias is not None else None


@lru_cache(maxsize=4096)
def _get_family(family_uuid):
    result = (
        EvictedPerson.query
        .options(load_settlement_info)
        .filter(EvictedPerson.family_uuid == family_uuid)
        .order_by(EvictedPerson.family_position.asc().nullslast(), desc(EvictedPerson.full_name))
        .all()
    )
    data = [person.to_dict() for person in result]
    if any(person['family_position'] is None for person in data):
        data.sort(key=lambda x: get_priority(x["family_role"]))
    return data


@family_bp.route('/<family_uuid>')
def get_family_members(family_uuid):
    """The family's rows in book order: people, and the notes the book prints instead of names."""
    family_uuid = resolve_family_uuid(parse_family_uuid(family_uuid))
    members = _get_family(family_uuid) if family_uuid else None
    if not members:
        abort(404)
    return json_response(members)


@lru_cache(maxsize=4096)
def _get_family_settlement(family_uuid):
    family = db.session.get(
        Family, family_uuid,
        options=[selectinload(Family.book_list).selectinload(SettlementList.settlements),
                 selectinload(Family.settlement)],
    )
    if family is None or family.book_list is None:
        return None
    return {
        'heading': family.settlement_label(),
        # The family as printed: its number ('12', '138-1', null when unnumbered), kind and sub-heading
        'family': family.to_dict(),
        'list': family.book_list.to_dict(),
        # The one village the book names for this family, if it does (null for combined lists)
        'settlement': family.settlement.to_dict() if family.settlement else None,
        'list_settlements': [s.to_dict() for s in family.book_list.settlements],
    }


@family_bp.route('/<family_uuid>/settlement')
def get_family_settlement(family_uuid):
    """Everything the book says about where the family lived: the list it was read from
    (with the archive reference) and the register entries of the settlement(s) it covers."""
    family_uuid = resolve_family_uuid(parse_family_uuid(family_uuid))
    info = _get_family_settlement(family_uuid) if family_uuid else None
    if info is None:
        abort(404)
    return json_response(info)
