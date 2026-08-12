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


def check_fts_populated(conn):
    """FTS docsize 테이블에 데이터가 있으면 인덱스가 채워진 것"""
    try:
        cur = conn.execute("SELECT COUNT(*) FROM jlc_components_fts_docsize")
        return cur.fetchone()[0] > 0
    except Exception:
        return False


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

    cur = conn.execute("SELECT COUNT(*) FROM jlc_components")
    row_count = cur.fetchone()[0]
    if row_count == 0:
        error_exit("jlc_components 테이블이 비어있습니다.")

    log(f"  jlc_components: {row_count:,} rows")

    if not check_table_exists(conn, "jlc_components_fts"):
        error_exit("jlc_components_fts (FTS5) 테이블이 존재하지 않습니다.")

    log("  구조 검증 통과")
    return row_count


def step_rebuild_fts(conn):
    log("FTS5 인덱스 rebuild...")

    if check_fts_populated(conn):
        log("  FTS 이미 채워져 있음 — 재구축 건너뜀")
        return

    t0 = time.perf_counter()
    conn.execute(
        "INSERT INTO jlc_components_fts(jlc_components_fts) VALUES('rebuild')"
    )
    conn.commit()
    elapsed = time.perf_counter() - t0
    log(f"  FTS rebuild 완료 ({elapsed:.1f}초)")

    # 확인
    cur = conn.execute("SELECT COUNT(*) FROM jlc_components_fts_docsize")
    docsize = cur.fetchone()[0]
    log(f"  FTS docsize rows: {docsize:,}")


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

    # 컬럼 추가
    if check_column_exists(conn, "jlc_components", "first_price"):
        # 이미 존재하면 값이 채워져 있는지 확인
        cur = conn.execute(
            "SELECT COUNT(*) FROM jlc_components WHERE first_price IS NOT NULL"
        )
        filled = cur.fetchone()[0]
        if filled > 0:
            log(f"  first_price 이미 존재하고 {filled:,}건 채워짐 — 건너뜀")
        else:
            log("  first_price 컬럼 존재하지만 비어있음 — UPDATE 실행")
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
            log(f"  UPDATE 완료 ({elapsed:.1f}초)")
    else:
        log("  first_price 컬럼 추가...")
        conn.execute("ALTER TABLE jlc_components ADD COLUMN first_price REAL")

        t0 = time.perf_counter()
        conn.execute("""
            UPDATE jlc_components SET first_price =
                CAST(substr(price, instr(price,':')+1,
                     CASE WHEN instr(price,',') > 0
                          THEN instr(price,',')-instr(price,':')-1
                          ELSE length(price)-instr(price,':')
                     END) AS REAL)
            WHERE price != ''
        """)
        conn.commit()
        elapsed = time.perf_counter() - t0
        log(f"  UPDATE 완료 ({elapsed:.1f}초)")

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

    tests = [
        ("FTS: STM32F103*",
         "SELECT COUNT(*) FROM jlc_components_fts WHERE jlc_components_fts MATCH 'STM32F103*'"),
        ("FTS: ESP32*",
         "SELECT COUNT(*) FROM jlc_components_fts WHERE jlc_components_fts MATCH 'ESP32*'"),
        ("category COUNT (Capacitors)",
         "SELECT COUNT(*) FROM jlc_components WHERE category='Capacitors'"),
        ("manufacturer (TI)",
         "SELECT COUNT(*) FROM jlc_components WHERE manufacturer='Texas Instruments'"),
        ("stock DESC LIMIT 5",
         "SELECT lcsc FROM jlc_components ORDER BY stock DESC LIMIT 5"),
        ("category + stock DESC",
         "SELECT lcsc FROM jlc_components WHERE category='Capacitors' ORDER BY stock DESC LIMIT 5"),
        ("category + first_price ASC",
         "SELECT lcsc FROM jlc_components WHERE category='Capacitors' ORDER BY first_price ASC LIMIT 5"),
    ]

    all_pass = True
    for label, sql in tests:
        try:
            t0 = time.perf_counter()
            cur = conn.execute(sql)
            rows = cur.fetchall()
            elapsed = (time.perf_counter() - t0) * 1000
            result = rows[0][0] if rows else "N/A"
            status = "PASS" if elapsed < 100 else "SLOW"
            if status == "SLOW":
                all_pass = False
            print(f"  [{status}] {label:35s} {elapsed:7.1f}ms  result={result}")
        except Exception as e:
            all_pass = False
            print(f"  [FAIL] {label:35s} ERROR: {e}")

    # EXPLAIN QUERY PLAN 확인
    print()
    log("EXPLAIN QUERY PLAN 확인...")
    explain_queries = [
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
    for label, sql in explain_queries:
        cur = conn.execute(f"EXPLAIN QUERY PLAN {sql}")
        plans = [r[3] for r in cur.fetchall()]
        uses_index = any("INDEX" in p for p in plans)
        status = "OK" if uses_index else "NO INDEX"
        print(f"  [{status:8s}] {label:20s} → {plans[0] if plans else 'N/A'}")

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
    step_rebuild_fts(conn)

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
    log(f"검증: {'ALL PASS' if all_pass else 'SOME ISSUES'}")
    log(f"출력: {output_path}")
    print()

    if not all_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
