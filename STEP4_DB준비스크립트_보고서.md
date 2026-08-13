# STEP 4: DB 준비 스크립트 보고서

## 목적

CDFER/jlcpcb-parts-database에서 새 DB를 받을 때마다 STEP 3에서 검증한 최적화를 자동으로 적용하는 재현 가능한 스크립트.

---

## 스크립트

`scripts/prepare_db.py`

### 사용법

```
python scripts/prepare_db.py <원본DB경로> <출력DB경로>
```

### 예시

```
python scripts/prepare_db.py ^
    "C:\Users\gyuwon\Downloads\jlcpcb-components.sqlite3" ^
    "C:\Users\gyuwon\Downloads\jlcpcb-components-ready.sqlite3"
```

### 적용 내용

| 단계 | 작업 | 소요 시간 |
|------|------|:---------:|
| 1 | 원본 파일 복사 (원본 수정 금지) | ~5초 |
| 2 | 원본 구조 검증 (테이블/FTS 존재 확인) | < 1초 |
| 3 | FTS5 인덱스 rebuild | ~41초 |
| 4 | 일반 인덱스 5개 생성 | ~13초 |
| 5 | first_price 컬럼 추가 + UPDATE | ~38초 |
| 6 | first_price 인덱스 2개 생성 | ~7초 |
| 7 | ANALYZE | ~8초 |
| 8 | 자동 검증 (7개 쿼리 + EXPLAIN) | < 1초 |
| **총** | | **~112초** |

### 안전성

- 원본 DB는 절대 수정하지 않음 (파일 복사 후 복사본만 변경)
- 원본과 출력 경로가 같으면 에러 출력 후 중단
- `IF NOT EXISTS`로 인덱스 중복 생성 방지
- `first_price` 컬럼 이미 존재 시 감지 → 미처리 row(`price != '' AND first_price IS NULL`)만 UPDATE
- UPDATE 후 검증: 미처리 row가 0인지 확인, 비정상 price 값 보고
- FTS 상태 검증: `jlc_components_fts_docsize` row 수와 `jlc_components` row 수를 비교하여 정상/불완전/비어있음 판별
- FTS rebuild 후 재검증: docsize == jlc_components row 수 일치 확인
- 각 단계 실패 시 명확한 에러 메시지

### 자동 검증 (correctness + 성능 + index 사용)

검증 항목:
- FTS 검색: 결과 > 0 확인 (0건이면 WRONG)
- COUNT 쿼리: 결과 > 0 확인
- 정렬 쿼리: 5건 반환 + 값 NOT NULL 확인
- 실행 시간 100ms 초과 시 SLOW
- EXPLAIN QUERY PLAN: 기대하는 쿼리에서 INDEX 미사용 시 FAIL
- 모든 검증 통과해야 ALL PASS (exit code 0)

---

## 실행 결과

```
[prepare_db] 총 소요 시간: 94.6초
[prepare_db] 원본 크기: 2088.8 MB
[prepare_db] 출력 크기: 2316.4 MB (+227.6 MB, +10.9%)
[prepare_db] 부품 수: 633,341
[prepare_db] 검증: ALL PASS
```

### 검증 결과

| 테스트 | 상태 | 결과 | 실행 시간 | 검증 조건 |
|--------|:----:|------|:---------:|----------|
| FTS: STM32F103* | PASS | 65건 | 4.0ms | 결과 > 0 |
| FTS: ESP32* | PASS | 94건 | 1.2ms | 결과 > 0 |
| category COUNT (Capacitors) | PASS | 49,350건 | 11.8ms | 결과 > 0 |
| manufacturer (TI) | PASS | 21,193건 | 4.2ms | 결과 > 0 |
| stock DESC LIMIT 5 | PASS | OK | 0.2ms | 5건, stock NOT NULL |
| category + stock DESC | PASS | OK | 0.3ms | 5건, stock NOT NULL |
| category + first_price ASC | PASS | OK | 0.2ms | 5건, first_price NOT NULL |

### EXPLAIN QUERY PLAN

| 쿼리 | 상태 | 사용 인덱스 |
|------|:----:|------------|
| category COUNT | PASS | COVERING INDEX idx_cat_price |
| manufacturer | PASS | COVERING INDEX idx_manufacturer |
| stock DESC | PASS | COVERING INDEX idx_stock |
| cat+stock DESC | PASS | COVERING INDEX idx_cat_stock |
| cat+price ASC | PASS | COVERING INDEX idx_cat_price |

### first_price 검증

- 미처리 row (price != '' AND first_price IS NULL): **0건**
- 비정상 price 값: 없음

---

## 생성된 인덱스 목록

| 인덱스 | 정의 | 용도 |
|--------|------|------|
| idx_cat_subcat | `(category, subcategory)` | 카테고리 탐색 |
| idx_cat_stock | `(category, stock DESC)` | 카테고리 내 재고순 |
| idx_manufacturer | `(manufacturer)` | 제조사 필터 |
| idx_package | `(package)` | 패키지 필터 |
| idx_stock | `(stock DESC)` | 전체 재고순 |
| idx_first_price | `(first_price)` | 전체 가격순 |
| idx_cat_price | `(category, first_price)` | 카테고리 내 가격순 |

---

## 파일 구조

```
Circuit/
├── scripts/
│   └── prepare_db.py          ← DB 준비 스크립트
├── .gitignore                 ← *.sqlite3 제외 확인
├── STEP4_DB준비스크립트_보고서.md
└── ...
```

SQLite DB 파일은 `.gitignore`에서 `*.sqlite3`로 제외됨.
