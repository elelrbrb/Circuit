"""
CDFER jlcpcb-components SQLite DB 준비 스크립트

CDFER/jlcpcb-parts-database에서 다운로드한 원본 SQLite DB에
검색/필터/정렬을 위한 최적화를 적용하여 프로덕션 준비된 복사본을 생성합니다.

사용법:
    python scripts/prepare_db.py <원본DB경로> <출력DB경로>

예시:
    python scripts/prepare_db.py ^
        "C:\\Users\\gyuwon\\Downloads\\jlcpcb-components.sqlite3" ^
        "C:\\Users\\gyuwon\\Downloads\\jlcpcb-components-ready.sqlite3"

적용 내용 (STEP 3에서 검증됨):
    1. FTS5 인덱스 rebuild
    2. category/subcategory, manufacturer, package, stock 인덱스
    3. first_price 컬럼 추가 및 인덱스
    4. ANALYZE 실행
"""

import sqlite3
import shutil
import sys
import os
import time


def log(msg):
    print(f"[prepare_db] {msg}")


def error_exit(msg):
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(1)


def check_table_exists(conn, table_name):
    cur = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cur.fetchone()[0] > 0


def check_column_exists(conn, table_name, column_name):
    cur = conn.execute(f"PRAGMA table_info('{table_name}')")
    columns = [row[1] for row in cur.fetchall()]
    return column_name in columns


def check_index_exists(conn, index_name):
    cur = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,),
    )
    return cur.fetchone()[0] > 0


def get_row_count(conn, table_name):
    cur = conn.execute(f"SELECT COUNT(*) FROM [{table_name}]")
    return cur.fetchone()[0]


def step_copy_db(source_path, output_path):
    log(f"원본 복사: {source_path} -> {output_path}")
    if os.path.exists(output_path):
        os.remove(output_path)
    shutil.copy2(source_path, output_path)
    size_mb = os.path.getsize(output_path) / 1024 / 1024
    log(f"  복사 완료 ({size_mb:.1f} MB)")


def step_validate_source(conn):
    log("원본 구조 검증...")

    if not check_table_exists(conn, "jlc_components"):
        error_exit("jlc_components 테이블이 존재하지 않습니다.")

    row_count = get_row_count(conn, "jlc_components")
    if row_count == 0:
        error_exit("jlc_components 테이블이 비어있습니다.")

    log(f"  jlc_components: {row_count:,} rows")

    if not check_table_exists(conn, "jlc_components_fts"):
        error_exit("jlc_components_fts (FTS5) 테이블이 존재하지 않습니다.")

    log("  구조 검증 통과")
    return row_count


def step_rebuild_fts(conn, expected_row_count):
    log("FTS5 인덱스 확인 및 rebuild...")

    # FTS 상태 확인: docsize row 수와 jlc_components row 수 비교
    try:
        fts_docsize_count = get_row_count(conn, "jlc_components_fts_docsize")
    except Exception:
        fts_docsize_count = 0

    if fts_docsize_count == expected_row_count:
        log(f"  FTS 정상 (docsize={fts_docsize_count:,} == jlc_components={expected_row_count:,}) — rebuild 건너뜀")
        return
    elif fts_docsize_count > 0:
        log(f"  FTS 불완전 (docsize={fts_docsize_count:,} != jlc_components={expected_row_count:,}) — rebuild 실행")
    else:
        log(f"  FTS 비어있음 (docsize=0) — rebuild 실행")

    t0 = time.perf_counter()
    conn.execute(
        "INSERT INTO jlc_components_fts(jlc_components_fts) VALUES('rebuild')"
    )
    conn.commit()
    elapsed = time.perf_counter() - t0
    log(f"  FTS rebuild 완료 ({elapsed:.1f}초)")

    # rebuild 후 검증
    fts_docsize_after = get_row_count(conn, "jlc_components_fts_docsize")
    if fts_docsize_after != expected_row_count:
        error_exit(
            f"FTS rebuild 후 docsize({fts_docsize_after:,}) != "
            f"jlc_components({expected_row_count:,})"
        )
    log(f"  FTS 검증 통과 (docsize={fts_docsize_after:,})")


def step_create_indexes(conn):
    log("일반 인덱스 생성...")

    indexes = [
        ("idx_cat_subcat", "CREATE INDEX IF NOT EXISTS idx_cat_subcat ON jlc_components(category, subcategory)"),
        ("idx_cat_stock", "CREATE INDEX IF NOT EXISTS idx_cat_stock ON jlc_components(category, stock DESC)"),
        ("idx_manufacturer", "CREATE INDEX IF NOT EXISTS idx_manufacturer ON jlc_components(manufacturer)"),
        ("idx_package", "CREATE INDEX IF NOT EXISTS idx_package ON jlc_components(package)"),
        ("idx_stock", "CREATE INDEX IF NOT EXISTS idx_stock ON jlc_components(stock DESC)"),
    ]

    for name, sql in indexes:
        if check_index_exists(conn, name):
            log(f"  {name} — 이미 존재, 건너뜀")
            continue
        t0 = time.perf_counter()
        conn.execute(sql)
        conn.commit()
        elapsed = time.perf_counter() - t0
        log(f"  {name} — 생성 ({elapsed:.1f}초)")


def step_add_first_price(conn):
    log("first_price 컬럼 및 인덱스 생성...")

    # 컬럼 추가 (없으면)
    if not check_column_exists(conn, "jlc_components", "first_price"):
        log("  first_price 컬럼 추가...")
        conn.execute("ALTER TABLE jlc_components ADD COLUMN first_price REAL")
        conn.commit()
    else:
        log("  first_price 컬럼 이미 존재")

    # 미처리 row 확인
    cur = conn.execute(
        "SELECT COUNT(*) FROM jlc_components WHERE price != '' AND first_price IS NULL"
    )
    remaining = cur.fetchone()[0]

    if remaining == 0:
        log("  first_price 모든 row 처리 완료 — UPDATE 건너뜀")
    else:
        log(f"  first_price 미처리 row: {remaining:,}개 — UPDATE 실행")
        t0 = time.perf_counter()
        conn.execute("""
            UPDATE jlc_components SET first_price =
                CAST(substr(price, instr(price,':')+1,
                     CASE WHEN instr(price,',') > 0
                          THEN instr(price,',')-instr(price,':')-1
                          ELSE length(price)-instr(price,':')
                     END) AS REAL)
            WHERE price != '' AND first_price IS NULL
        """)
        conn.commit()
        elapsed = time.perf_counter() - t0
        log(f"  UPDATE 완료 ({elapsed:.1f}초, {remaining:,}건 처리)")

    # UPDATE 후 검증: price가 있는데 first_price가 여전히 NULL인 row
    cur = conn.execute(
        "SELECT COUNT(*) FROM jlc_components WHERE price != '' AND first_price IS NULL"
    )
    still_null = cur.fetchone()[0]
    if still_null > 0:
        log(f"  [경고] price != '' 인데 first_price IS NULL인 row: {still_null}개")
        # 원인 조사: price 값이 비정상인 경우
        cur = conn.execute("""
            SELECT lcsc, price FROM jlc_components
            WHERE price != '' AND first_price IS NULL
            LIMIT 5
        """)
        for r in cur.fetchall():
            log(f"    C{r[0]}: price='{r[1][:80]}'")
    else:
        log("  first_price 검증 통과 (미처리 row 0건)")

    # 인덱스
    price_indexes = [
        ("idx_first_price", "CREATE INDEX IF NOT EXISTS idx_first_price ON jlc_components(first_price)"),
        ("idx_cat_price", "CREATE INDEX IF NOT EXISTS idx_cat_price ON jlc_components(category, first_price)"),
    ]
    for name, sql in price_indexes:
        if check_index_exists(conn, name):
            log(f"  {name} — 이미 존재, 건너뜀")
            continue
        t0 = time.perf_counter()
        conn.execute(sql)
        conn.commit()
        elapsed = time.perf_counter() - t0
        log(f"  {name} — 생성 ({elapsed:.1f}초)")


def step_analyze(conn):
    log("ANALYZE 실행...")
    t0 = time.perf_counter()
    conn.execute("ANALYZE")
    conn.commit()
    elapsed = time.perf_counter() - t0
    log(f"  ANALYZE 완료 ({elapsed:.1f}초)")


def step_verify(conn):
    log("최종 검증...")
    print()

    all_pass = True

    # --- correctness + 성능 검증 ---
    tests = [
        {
            "label": "FTS: STM32F103*",
            "sql": "SELECT COUNT(*) FROM jlc_components_fts WHERE jlc_components_fts MATCH 'STM32F103*'",
            "check": lambda rows: rows[0][0] > 0,
            "desc": "결과 > 0",
        },
        {
            "label": "FTS: ESP32*",
            "sql": "SELECT COUNT(*) FROM jlc_components_fts WHERE jlc_components_fts MATCH 'ESP32*'",
            "check": lambda rows: rows[0][0] > 0,
            "desc": "결과 > 0",
        },
        {
            "label": "category COUNT (Capacitors)",
            "sql": "SELECT COUNT(*) FROM jlc_components WHERE category='Capacitors'",
            "check": lambda rows: rows[0][0] > 0,
            "desc": "결과 > 0",
        },
        {
            "label": "manufacturer (TI)",
            "sql": "SELECT COUNT(*) FROM jlc_components WHERE manufacturer='Texas Instruments'",
            "check": lambda rows: rows[0][0] > 0,
            "desc": "결과 > 0",
        },
        {
            "label": "stock DESC LIMIT 5",
            "sql": "SELECT lcsc, stock FROM jlc_components ORDER BY stock DESC LIMIT 5",
            "check": lambda rows: len(rows) == 5 and all(r[1] is not None for r in rows),
            "desc": "5건 반환, stock NOT NULL",
        },
        {
            "label": "category + stock DESC",
            "sql": "SELECT lcsc, stock FROM jlc_components WHERE category='Capacitors' ORDER BY stock DESC LIMIT 5",
            "check": lambda rows: len(rows) == 5 and all(r[1] is not None for r in rows),
            "desc": "5건 반환, stock NOT NULL",
        },
        {
            "label": "category + first_price ASC",
            "sql": "SELECT lcsc, first_price FROM jlc_components WHERE category='Capacitors' ORDER BY first_price ASC LIMIT 5",
            "check": lambda rows: len(rows) == 5 and all(r[1] is not None for r in rows),
            "desc": "5건 반환, first_price NOT NULL",
        },
    ]

    for t in tests:
        try:
            t0 = time.perf_counter()
            cur = conn.execute(t["sql"])
            rows = cur.fetchall()
            elapsed = (time.perf_counter() - t0) * 1000

            correct = t["check"](rows)
            fast = elapsed < 100
            passed = correct and fast

            if not passed:
                all_pass = False

            result_val = rows[0][0] if rows and len(rows[0]) >= 1 else "N/A"
            status = "PASS" if passed else ("WRONG" if not correct else "SLOW")
            print(f"  [{status:5s}] {t['label']:35s} {elapsed:7.1f}ms  result={result_val}  ({t['desc']})")
        except Exception as e:
            all_pass = False
            print(f"  [FAIL ] {t['label']:35s} ERROR: {e}")

    # --- EXPLAIN QUERY PLAN 검증 (index 사용 필수) ---
    print()
    log("EXPLAIN QUERY PLAN 검증 (INDEX 사용 필수)...")

    explain_tests = [
        ("category COUNT",
         "SELECT COUNT(*) FROM jlc_components WHERE category='Capacitors'"),
        ("manufacturer",
         "SELECT COUNT(*) FROM jlc_components WHERE manufacturer='Texas Instruments'"),
        ("stock DESC",
         "SELECT lcsc FROM jlc_components ORDER BY stock DESC LIMIT 5"),
        ("cat+stock DESC",
         "SELECT lcsc FROM jlc_components WHERE category='Capacitors' ORDER BY stock DESC LIMIT 5"),
        ("cat+price ASC",
         "SELECT lcsc FROM jlc_components WHERE category='Capacitors' ORDER BY first_price ASC LIMIT 5"),
    ]

    for label, sql in explain_tests:
        cur = conn.execute(f"EXPLAIN QUERY PLAN {sql}")
        plans = [r[3] for r in cur.fetchall()]
        uses_index = any("INDEX" in p for p in plans)

        if not uses_index:
            all_pass = False

        status = "PASS" if uses_index else "FAIL"
        plan_str = plans[0] if plans else "N/A"
        print(f"  [{status:5s}] {label:20s} → {plan_str}")

    print()
    return all_pass


def main():
    if len(sys.argv) != 3:
        print("사용법: python scripts/prepare_db.py <원본DB> <출력DB>")
        print()
        print("예시:")
        print('  python scripts/prepare_db.py "downloads/jlcpcb-components.sqlite3" "downloads/jlcpcb-components-ready.sqlite3"')
        sys.exit(1)

    source_path = sys.argv[1]
    output_path = sys.argv[2]

    if not os.path.exists(source_path):
        error_exit(f"원본 DB 파일이 존재하지 않습니다: {source_path}")

    if os.path.abspath(source_path) == os.path.abspath(output_path):
        error_exit("원본과 출력 경로가 같습니다. 원본 보호를 위해 다른 경로를 지정하세요.")

    print()
    log("=" * 50)
    log("CDFER SQLite DB 준비 스크립트")
    log("=" * 50)
    print()

    total_t0 = time.perf_counter()

    # 1. 복사
    step_copy_db(source_path, output_path)

    # 2. 연결 및 검증
    conn = sqlite3.connect(output_path)
    conn.execute("PRAGMA journal_mode=WAL")
    row_count = step_validate_source(conn)

    # 3. FTS rebuild
    step_rebuild_fts(conn, row_count)

    # 4. 일반 인덱스
    step_create_indexes(conn)

    # 5. first_price
    step_add_first_price(conn)

    # 6. ANALYZE
    step_analyze(conn)

    # 7. 검증
    all_pass = step_verify(conn)

    conn.close()

    # 최종 정보
    total_elapsed = time.perf_counter() - total_t0
    final_size = os.path.getsize(output_path)
    original_size = os.path.getsize(source_path)

    print()
    log("=" * 50)
    log("완료")
    log("=" * 50)
    log(f"총 소요 시간: {total_elapsed:.1f}초")
    log(f"원본 크기: {original_size / 1024 / 1024:.1f} MB")
    log(f"출력 크기: {final_size / 1024 / 1024:.1f} MB (+{(final_size - original_size) / 1024 / 1024:.1f} MB, +{(final_size - original_size) * 100 / original_size:.1f}%)")
    log(f"부품 수: {row_count:,}")
    log(f"검증: {'ALL PASS' if all_pass else 'FAILED'}")
    log(f"출력: {output_path}")
    print()

    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
