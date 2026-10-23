"""flask repair-book-data: bring the person and family tables back to the printed book.

The data audit (lemko/spec/data-audit) compared every row of the three books with the database
and merged every fix into one plan. spec/data-audit/tools/build_repair_files.py turns that plan
into the files in migrations/data/repair:

- persons.csv.gz: every printed person or note row (143,407) with its place in the book, its
  values as printed, its family, and the natural key of the database row it is today (empty
  for the 7,602 rows to insert);
- families.csv.gz: every book entity (34,521): uuid, list, number and kind as printed, order in
  the list, printed sub-heading, settlement;
- family_aliases.csv: the family uuids the regrouping retires, with the family they merged into;
- lists_expected.csv: what every list must hold afterwards, next to the printed totals.

The command resolves each target row to a database row (by book position where it is already
stored, else by the natural key, reading the text 'NaN' as a blank cell), loads the targets into
temporary tables and applies the difference with set-based SQL in one transaction: insert
families, insert people, update moved or corrected rows, fill the book positions, relink area_id,
retire families into aliases, drop register values nothing uses, and log the repair in
data_repairs. Before COMMIT it checks the result against lists_expected.csv and reports where the
book's own printed totals differ. Without --apply the transaction is rolled back at the end, so a
dry run exercises the whole path.

Run it deliberately, never from startup.sh:
    flask repair-book-data            # dry run
    flask repair-book-data --apply    # commit
    flask repair-book-data --again    # after an apply: run the diff again; it must change nothing
"""
import csv
import gzip
import io
import json
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path

import click
from flask.cli import with_appcontext
from sqlalchemy import text

from app.extensions import db

NAME = 'book-repair-2026-10'
DATA = Path(__file__).resolve().parents[2] / 'migrations' / 'data'
REPAIR = DATA / 'repair'
PERSON_NAMESPACE = uuid.UUID('6f1c1f6e-6b1e-4c58-9d3e-1e4b0a5c2f10')
BLANKS = {'', 'NaN', 'n/a'}  # pandas NaN stored as text, and the seed file's n/a: blank cells

PERSON_COLUMNS = ('id', 'list_id', 'book_tr', 'book_row_no', 'row_kind', 'persons_represented', 'family_uuid',
                  'family_position', 'full_name', 'family_role', 'birth_year', 'area_eviction', 'settlement', 'is_new')
FAMILY_COLUMNS = ('family_uuid', 'list_id', 'settlement_id', 'printed_no', 'kind', 'book_seq', 'section', 'is_new')


class RepairError(Exception):
    pass


def blank(value):
    return '' if value is None or value in BLANKS else value


def read(name):
    opener = gzip.open if name.endswith('.gz') else open
    with opener(REPAIR / name, 'rt', encoding='utf-8', newline='') as fh:
        return list(csv.DictReader(fh))


def scalar(conn, sql, **params):
    return conn.execute(text(sql), params).scalar()


def copy_rows(conn, table, columns, rows):
    """COPY rows into a temp table; an empty value becomes NULL."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator='\n')
    for r in rows:
        writer.writerow([r.get(c) for c in columns])
    buf.seek(0)
    cursor = conn.connection.cursor()
    try:
        cursor.copy_expert(f"COPY {table} ({', '.join(columns)}) FROM STDIN WITH (FORMAT csv)", buf)
    finally:
        cursor.close()


def resolve_persons(conn, persons, lists):
    """Give every target row the id of the database row it is, or a new deterministic id."""
    rows = conn.execute(text(
        "SELECT id, family_uuid, full_name, family_role, birth_year, area_eviction, list_id, book_tr "
        "FROM evicted_persons")).all()
    by_pos, by_key = {}, defaultdict(list)
    for r in rows:
        if r.list_id is not None and r.book_tr is not None:
            by_pos[(r.list_id, r.book_tr)] = str(r.id)
        by_key[(str(r.family_uuid), blank(r.full_name), blank(r.family_role), blank(r.birth_year),
                blank(r.area_eviction))].append(str(r.id))
    for ids in by_key.values():
        ids.sort()
    claimed, how, unresolved = set(), Counter(), []
    for p in persons:
        p['list_id'], p['settlement'] = lists[(int(p['volume']), int(p['table_no']))]
        p['book_tr'] = int(p['book_tr'])
        stored = by_pos.get((p['list_id'], p['book_tr']))
        if stored and stored not in claimed:
            p['id'], p['is_new'] = stored, 'false'
            claimed.add(stored)
            how['matched by book position'] += 1
            continue
        if not p['key_family_uuid']:
            p['id'], p['is_new'] = str(uuid.uuid5(PERSON_NAMESPACE, 'lemko-memory-book:person:' + p['book_key'])), 'true'
            how['to insert'] += 1
            continue
        key = (p['key_family_uuid'], blank(p['key_full_name']), blank(p['key_family_role']),
               blank(p['key_birth_year']), blank(p['key_area_eviction']))
        ids = [i for i in by_key.get(key, ()) if i not in claimed]
        if not ids:
            unresolved.append(p)
            continue
        p['id'], p['is_new'] = ids[0], 'false'
        claimed.add(ids[0])
        how['matched by natural key'] += 1
    if unresolved:
        examples = '; '.join(f"{p['book_key']} {p['key_full_name']} | {p['key_family_role']} | {p['key_birth_year']}"
                             for p in unresolved[:5])
        raise RepairError(f'{len(unresolved)} target rows match no database row, e.g. {examples}')
    unclaimed = [r for r in rows if str(r.id) not in claimed]
    if unclaimed:
        examples = '; '.join(f'{r.full_name} | {r.family_role} | {r.birth_year} ({r.id})' for r in unclaimed[:5])
        raise RepairError(f'{len(unclaimed)} database rows belong to no book row, e.g. {examples}')
    existing = {str(r.id) for r in rows}
    collisions = [p['id'] for p in persons if p['is_new'] == 'true' and p['id'] in existing]
    if collisions:
        raise RepairError(f'{len(collisions)} new ids collide with existing rows')
    return how


def prepare_families(conn, families, lists):
    stored = {str(r.family_uuid): r for r in
              conn.execute(text("SELECT family_uuid, list_id, settlement_id FROM families")).all()}
    for f in families:
        f['list_id'], _ = lists[(int(f['volume']), int(f['table_no']))]
        f['is_new'] = 'false' if f['family_uuid'] in stored else 'true'
        if f['settlement_id'] == 'keep':
            if f['is_new'] == 'true':
                raise RepairError(f"family {f['family_uuid']} is not in the database but should keep its settlement")
            f['settlement_id'] = stored[f['family_uuid']].settlement_id
        else:
            f['settlement_id'] = int(f['settlement_id']) if f['settlement_id'] else None
    targets = {f['family_uuid'] for f in families}
    retired = set(stored) - targets
    return retired, sum(1 for f in families if f['is_new'] == 'true')


def check_result(conn, expected, lists_by_id, expected_families):
    """Raise unless the tables hold exactly what the plan says; return the report."""
    problems = []
    totals = conn.execute(text(
        "SELECT count(*) AS rows, count(*) FILTER (WHERE list_id IS NULL OR book_tr IS NULL) AS unplaced, "
        "count(*) FILTER (WHERE family_position IS NULL) AS unpositioned, "
        "count(DISTINCT family_uuid) AS families_used FROM evicted_persons")).one()
    families = scalar(conn, "SELECT count(*) FROM families")
    empty_families = scalar(conn, "SELECT count(*) FROM families f WHERE NOT EXISTS "
                                  "(SELECT 1 FROM evicted_persons p WHERE p.family_uuid = f.family_uuid)")
    bare_families = scalar(conn, "SELECT count(*) FROM families WHERE book_seq IS NULL OR kind IS NULL OR list_id IS NULL")
    list_mismatch = scalar(conn, "SELECT count(*) FROM evicted_persons p JOIN families f ON f.family_uuid = p.family_uuid "
                                 "WHERE f.list_id <> p.list_id")
    blanks_left = scalar(conn, "SELECT count(*) FROM evicted_persons WHERE full_name IN ('NaN', 'n/a', '') "
                               "OR family_role IN ('NaN', 'n/a', '') OR birth_year IN ('NaN', 'n/a', '') "
                               "OR area_eviction IN ('NaN', 'n/a', '')")
    area_unlinked = scalar(conn, "SELECT count(*) FROM evicted_persons WHERE area_eviction IS NOT NULL AND area_id IS NULL")
    area_wrong = scalar(conn, "SELECT count(*) FROM evicted_persons p JOIN areas a ON a.id = p.area_id "
                              "WHERE a.printed <> p.area_eviction")
    expected_rows = sum(int(e['rows']) for e in expected)
    if totals.rows != expected_rows:
        problems.append(f'{totals.rows} rows stored, {expected_rows} expected')
    if totals.unplaced or totals.unpositioned:
        problems.append(f'{totals.unplaced} rows without a book position, {totals.unpositioned} without a family position')
    if families != expected_families:
        problems.append(f'{families} families stored, {expected_families} expected')
    if empty_families:
        problems.append(f'{empty_families} families without members')
    if bare_families:
        problems.append(f'{bare_families} families without list, kind or order')
    if list_mismatch:
        problems.append(f'{list_mismatch} people whose family is in another list')
    if blanks_left:
        problems.append(f'{blanks_left} rows still hold NaN, n/a or an empty string instead of NULL')
    if area_unlinked or area_wrong:
        problems.append(f'{area_unlinked} people with an area but no area_id, {area_wrong} with the wrong area_id')

    # The book's family total is the last printed family number, so it counts the numbered families,
    # sometimes together with the un-numbered households (Вислічок numbers nothing and counts 184
    # households; Прилуки counts its one household). Un-numbered individuals ('ч/с' rows) are
    # never counted. A list is accepted when the printed total matches either reading.
    per_list = {r.list_id: r for r in conn.execute(text(
        "SELECT p.list_id, count(*) AS rows, sum(coalesce(p.persons_represented, 1)) AS persons, "
        "count(DISTINCT p.family_uuid) AS entities, "
        "count(DISTINCT p.family_uuid) FILTER (WHERE f.kind = 'numbered') AS numbered, "
        "count(DISTINCT p.family_uuid) FILTER (WHERE f.kind = 'unnumbered_household') AS households "
        "FROM evicted_persons p JOIN families f ON f.family_uuid = p.family_uuid GROUP BY p.list_id")).all()}
    printed = {r.id: r for r in conn.execute(text(
        "SELECT id, heading, list_total_persons, list_total_families FROM settlement_lists")).all()}
    wrong_lists, undocumented, documented = [], [], []
    for e in expected:
        list_id, heading = lists_by_id[(int(e['volume']), int(e['table_no']))]
        got = per_list.get(list_id)
        want = (int(e['rows']), int(e['persons']), int(e['entities']))
        have = (got.rows, int(got.persons), got.entities) if got else (0, 0, 0)
        if have != want:
            wrong_lists.append(f'{heading}: rows/persons/entities {have} expected {want}')
            continue
        book = printed[list_id]
        total_families = int(book.list_total_families) if (book.list_total_families or '').isdigit() else None
        differs = (book.list_total_persons is not None and have[1] != book.list_total_persons) or \
                  (total_families is not None and total_families not in (got.numbered, got.numbered + got.households))
        note = (f'{heading}: persons {have[1]} vs printed {book.list_total_persons}, '
                f'families {got.numbered} numbered + {got.households} households vs printed {book.list_total_families}')
        if differs and not e['documented_difference']:
            undocumented.append(note)
        elif differs:
            documented.append(note)
    if wrong_lists:
        problems.append(f'{len(wrong_lists)} lists differ from the plan: ' + ' | '.join(wrong_lists[:5]))
    if undocumented:
        problems.append(f'{len(undocumented)} lists differ from the printed totals without a documented reason: '
                        + ' | '.join(undocumented[:5]))
    if problems:
        raise RepairError('result checks failed: ' + '; '.join(problems))
    return {
        'rows': totals.rows, 'families': families, 'families_used': totals.families_used,
        'lists_matching_printed_totals': len(expected) - len(documented),
        'lists_with_documented_book_differences': len(documented),
    }


def run(conn, again, echo):
    started = time.time()
    version = scalar(conn, "SELECT version_num FROM alembic_version")
    if version < '0007':
        raise RepairError(f'schema is at migration {version}; 0007 or later is needed')
    applied = conn.execute(text("SELECT applied_at FROM data_repairs WHERE name = :n"), {'n': NAME}).first()
    if applied and not again:
        raise RepairError(f'{NAME} was applied on {applied.applied_at}; use --again to run the diff once more')

    lists = {(r.volume, r.table_no): (r.id, r.heading)
             for r in conn.execute(text("SELECT id, volume, table_no, heading FROM settlement_lists")).all()}
    persons, families = read('persons.csv.gz'), read('families.csv.gz')
    aliases, expected = read('family_aliases.csv'), read('lists_expected.csv')
    echo(f'targets: {len(persons)} rows in {len(families)} families; {len(aliases)} aliases; {len(expected)} lists')

    how = resolve_persons(conn, persons, lists)
    echo('rows: ' + ', '.join(f'{v} {k}' for k, v in sorted(how.items())))
    retired, new_families = prepare_families(conn, families, lists)
    alias_old = {a['old_uuid'] for a in aliases}
    if retired != alias_old and not (again and not retired):
        raise RepairError(f'{len(retired)} families would be left without members but {len(alias_old)} aliases are listed; '
                          f'unexpected: {sorted(retired ^ alias_old)[:5]}')
    echo(f'families: {new_families} to insert, {len(retired)} to retire into aliases')

    conn.execute(text(
        "CREATE TEMP TABLE repair_persons (id uuid PRIMARY KEY, list_id integer, book_tr integer, book_row_no integer, "
        "row_kind text, persons_represented smallint, family_uuid uuid, family_position smallint, full_name text, "
        "family_role text, birth_year text, area_eviction text, settlement text, is_new boolean) ON COMMIT DROP"))
    conn.execute(text(
        "CREATE TEMP TABLE repair_families (family_uuid uuid PRIMARY KEY, list_id integer, settlement_id integer, "
        "printed_no text, kind text, book_seq integer, section text, is_new boolean) ON COMMIT DROP"))
    copy_rows(conn, 'repair_persons', PERSON_COLUMNS, persons)
    copy_rows(conn, 'repair_families', FAMILY_COLUMNS, families)

    before = conn.execute(text(
        "SELECT count(*) FILTER (WHERE p.family_uuid <> r.family_uuid) AS moved, "
        "count(*) FILTER (WHERE p.full_name IS DISTINCT FROM r.full_name) AS name_changed, "
        "count(*) FILTER (WHERE p.family_role IS DISTINCT FROM r.family_role) AS role_changed, "
        "count(*) FILTER (WHERE p.birth_year IS DISTINCT FROM r.birth_year) AS year_changed, "
        "count(*) FILTER (WHERE p.area_eviction IS DISTINCT FROM r.area_eviction) AS area_changed, "
        "count(*) FILTER (WHERE p.family_role IN ('NaN', 'n/a') OR p.birth_year IN ('NaN', 'n/a') "
        "OR p.area_eviction IN ('NaN', 'n/a')) AS nan_rows, "
        "count(*) FILTER (WHERE p.row_kind <> r.row_kind) AS flagged, "
        "count(*) FILTER (WHERE p.list_id IS DISTINCT FROM r.list_id OR p.book_tr IS DISTINCT FROM r.book_tr "
        "OR p.family_position IS DISTINCT FROM r.family_position) AS positioned "
        "FROM evicted_persons p JOIN repair_persons r ON r.id = p.id WHERE NOT r.is_new")).one()
    summary = {
        'families_inserted': conn.execute(text(
            "INSERT INTO families (family_uuid, list_id, settlement_id, printed_no, kind, book_seq, section) "
            "SELECT family_uuid, list_id, settlement_id, printed_no, kind, book_seq, section FROM repair_families "
            "WHERE is_new")).rowcount,
        'families_updated': conn.execute(text(
            "UPDATE families f SET list_id = r.list_id, settlement_id = r.settlement_id, printed_no = r.printed_no, "
            "kind = r.kind, book_seq = r.book_seq, section = r.section FROM repair_families r "
            "WHERE r.family_uuid = f.family_uuid AND NOT r.is_new AND "
            "(f.list_id, f.settlement_id, f.printed_no, f.kind, f.book_seq, f.section) IS DISTINCT FROM "
            "(r.list_id, r.settlement_id, r.printed_no, r.kind, r.book_seq, r.section)")).rowcount,
        'people_inserted': conn.execute(text(
            "INSERT INTO evicted_persons (id, family_uuid, full_name, family_role, birth_year, area_eviction, settlement, "
            "list_id, book_tr, book_row_no, family_position, row_kind, persons_represented, created_at, updated_at) "
            "SELECT id, family_uuid, full_name, family_role, birth_year, area_eviction, settlement, list_id, book_tr, "
            "book_row_no, family_position, row_kind, persons_represented, now(), now() FROM repair_persons "
            "WHERE is_new")).rowcount,
        'people_updated': conn.execute(text(
            "UPDATE evicted_persons p SET family_uuid = r.family_uuid, full_name = r.full_name, "
            "family_role = r.family_role, birth_year = r.birth_year, area_eviction = r.area_eviction, "
            "list_id = r.list_id, book_tr = r.book_tr, book_row_no = r.book_row_no, family_position = r.family_position, "
            "row_kind = r.row_kind, persons_represented = r.persons_represented, updated_at = now() "
            "FROM repair_persons r WHERE r.id = p.id AND NOT r.is_new AND "
            "(p.family_uuid, p.full_name, p.family_role, p.birth_year, p.area_eviction, p.list_id, p.book_tr, "
            "p.book_row_no, p.family_position, p.row_kind, p.persons_represented) IS DISTINCT FROM "
            "(r.family_uuid, r.full_name, r.family_role, r.birth_year, r.area_eviction, r.list_id, r.book_tr, "
            "r.book_row_no, r.family_position, r.row_kind, r.persons_represented)")).rowcount,
        'people_moved': before.moved, 'cells_name': before.name_changed, 'cells_role': before.role_changed,
        'cells_year': before.year_changed, 'cells_area': before.area_changed, 'rows_with_nan_text': before.nan_rows,
        'rows_flagged_as_note': before.flagged, 'rows_given_a_book_position': before.positioned,
    }

    missing_areas = [r[0] for r in conn.execute(text(
        "SELECT DISTINCT area_eviction FROM evicted_persons p WHERE area_eviction IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM areas a WHERE a.printed = p.area_eviction)")).all()]
    if missing_areas:
        raise RepairError(f'the areas register lacks {len(missing_areas)} printed values: {missing_areas[:10]}')
    summary['area_links_set'] = conn.execute(text(
        "UPDATE evicted_persons p SET area_id = a.id FROM areas a "
        "WHERE a.printed = p.area_eviction AND p.area_id IS DISTINCT FROM a.id")).rowcount
    summary['area_links_cleared'] = conn.execute(text(
        "UPDATE evicted_persons SET area_id = NULL WHERE area_eviction IS NULL AND area_id IS NOT NULL")).rowcount

    members_left = scalar(conn, "SELECT count(*) FROM evicted_persons WHERE family_uuid = ANY(CAST(:retired AS uuid[]))",
                          retired=sorted(retired))
    if members_left:
        raise RepairError(f'{members_left} people still belong to families that should be retired')
    summary['families_retired'] = conn.execute(
        text("DELETE FROM families WHERE family_uuid = ANY(CAST(:retired AS uuid[]))"), {'retired': sorted(retired)}).rowcount
    summary['aliases_inserted'] = 0
    for a in aliases:
        summary['aliases_inserted'] += conn.execute(text(
            "INSERT INTO family_aliases (old_uuid, family_uuid, reason) VALUES (:old, :new, :reason) "
            "ON CONFLICT (old_uuid) DO NOTHING"), {'old': a['old_uuid'], 'new': a['family_uuid'], 'reason': a['reason']}).rowcount

    with open(DATA / 'areas.csv', encoding='utf-8', newline='') as fh:
        register = [r['printed'] for r in csv.DictReader(fh)]
    dropped = [r[0] for r in conn.execute(text(
        "DELETE FROM areas a WHERE NOT (a.printed = ANY(:keep)) "
        "AND NOT EXISTS (SELECT 1 FROM evicted_persons p WHERE p.area_id = a.id) RETURNING a.printed"),
        {'keep': register}).all()]
    summary['area_values_dropped'] = dropped

    summary['checks'] = check_result(conn, expected, lists, len(families))
    summary['seconds'] = round(time.time() - started, 1)
    if not applied:
        conn.execute(text("INSERT INTO data_repairs (name, summary) VALUES (:n, CAST(:s AS jsonb))"),
                     {'n': NAME, 's': json.dumps(summary, ensure_ascii=False)})
    return summary


@click.command('repair-book-data')
@click.option('--apply', 'apply_', is_flag=True, help='Commit. Without it the transaction is rolled back at the end.')
@click.option('--again', is_flag=True, help='Run the diff although the repair is logged as applied; it must change nothing.')
@with_appcontext
def repair_book_data(apply_, again):
    """Bring evicted_persons and families back to the printed book (lemko/spec/data-audit)."""
    with db.engine.connect() as conn:
        tx = conn.begin()
        try:
            summary = run(conn, again, click.echo)
        except RepairError as e:
            tx.rollback()
            click.echo(f'ABORTED, nothing changed: {e}', err=True)
            raise SystemExit(1)
        except Exception:
            tx.rollback()
            raise
        click.echo(json.dumps(summary, ensure_ascii=False, indent=1))
        if apply_:
            tx.commit()
            click.echo('COMMITTED')
        else:
            tx.rollback()
            click.echo('DRY RUN: everything above was rolled back')
