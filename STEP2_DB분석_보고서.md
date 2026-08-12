# STEP 2: CDFER jlcpcb-components.sqlite3 실제 DB 분석 보고서

## 분석 대상

- 파일: `C:\Users\gyuwon\Downloads\jlcpcb-components.sqlite3`
- 출처: [CDFER/jlcpcb-parts-database](https://github.com/CDFER/jlcpcb-parts-database)
- 원본: yaqwsx/jlcparts의 11GB SQLite에서 stock < 5인 부품을 제거하고 FTS 인덱스를 추가한 가공 DB

---

## 1. DB 기본 정보

| 항목 | 값 |
|------|-----|
| 파일 크기 | 2,190,295,040 bytes (2.09 GB) |
| SQLite 버전 | 3.45.3 |
| 정상 접근 여부 | 정상 (read-only 모드로 접근 확인) |

### 테이블 목록

| 테이블명 | row 수 | 설명 |
|---------|--------|------|
| `jlc_components` | 633,341 | 핵심 부품 테이블 |
| `lcsc_components` | 4,099,946 | LCSC 추가 정보 (제조사, 속성, 이미지) |
| `meta` | 5 | DB 메타데이터 |
| `jlc_components_fts` | 633,341 (구조만) | FTS5 가상 테이블 |
| `jlc_components_fts_config` | 1 | FTS 설정 |
| `jlc_components_fts_data` | 2 | FTS 데이터 |
| `jlc_components_fts_docsize` | 0 | FTS 문서 크기 (**비어있음**) |
| `jlc_components_fts_idx` | 0 | FTS 인덱스 (**비어있음**) |

### 뷰 (View)

없음.

### 인덱스

| 인덱스명 | 대상 테이블 |
|---------|-----------|
| `sqlite_autoindex_meta_1` | meta |

**일반 인덱스가 전혀 없음** — category, manufacturer, package, stock 등에 인덱스 없음.

### FTS 가상 테이블

```sql
CREATE VIRTUAL TABLE jlc_components_fts USING fts5(
    lcsc, mfr, package, description, datasheet,
    content='jlc_components'
)
```

**중요: FTS 인덱스가 비어있음** — `jlc_components_fts_docsize` = 0 rows, `jlc_components_fts_idx` = 0 rows. FTS MATCH 쿼리는 항상 0 결과를 반환함. 구조만 존재하고 데이터가 채워지지 않은 상태.

---

## 2. jlc_components 테이블 스키마

```sql
CREATE TABLE jlc_components (
    lcsc INTEGER PRIMARY KEY NOT NULL,
    fetched_at INTEGER NOT NULL,
    present INTEGER NOT NULL,
    sync_seen INTEGER NOT NULL DEFAULT 0,
    category TEXT NOT NULL,
    subcategory TEXT NOT NULL,
    mfr TEXT NOT NULL,
    package TEXT NOT NULL,
    joints INTEGER NOT NULL,
    manufacturer TEXT NOT NULL,
    library_type TEXT NOT NULL,
    preferred INTEGER NOT NULL,
    last_on_stock INTEGER NOT NULL,
    description TEXT NOT NULL,
    datasheet TEXT NOT NULL,
    stock INTEGER NOT NULL,
    price TEXT NOT NULL,
    attributes TEXT NOT NULL,
    rohs INTEGER,
    eccn TEXT NOT NULL,
    assembly INTEGER,
    assembly_process TEXT,
    assembly_mode TEXT,
    website_component_id TEXT,
    attrition TEXT NOT NULL,
    basic INTEGER DEFAULT 0
)
```

### 컬럼 상세

| 컬럼명 | 타입 | NOT NULL | 설명 |
|--------|------|----------|------|
| lcsc | INTEGER | PK | LCSC 부품 번호 (C 접두사 없이 숫자) |
| fetched_at | INTEGER | Y | 수집 시점 Unix timestamp |
| present | INTEGER | Y | 존재 여부 플래그 |
| sync_seen | INTEGER | Y | 동기화 플래그 |
| category | TEXT | Y | 1차 카테고리 |
| subcategory | TEXT | Y | 2차 카테고리 |
| mfr | TEXT | Y | 제조사 부품번호 (MPN) |
| package | TEXT | Y | 패키지/풋프린트 |
| joints | INTEGER | Y | 솔더 조인트 수 |
| manufacturer | TEXT | Y | 제조사명 |
| library_type | TEXT | Y | 'base' 또는 'expand' |
| preferred | INTEGER | Y | preferred 여부 (0 또는 1) |
| last_on_stock | INTEGER | Y | 마지막 재고 확인 timestamp |
| description | TEXT | Y | 부품 설명 |
| datasheet | TEXT | Y | 데이터시트 URL |
| stock | INTEGER | Y | 현재 재고 수량 |
| price | TEXT | Y | 수량별 가격 문자열 |
| attributes | TEXT | Y | 기술 사양 JSON |
| rohs | INTEGER | N | RoHS 여부 |
| eccn | TEXT | Y | ECCN 코드 |
| assembly | INTEGER | N | Assembly 가능 여부 |
| assembly_process | TEXT | N | SMT/DIP |
| assembly_mode | TEXT | N | Assembly 모드 |
| website_component_id | TEXT | N | 웹사이트 컴포넌트 ID |
| attrition | TEXT | Y | 소모 정보 JSON |
| basic | INTEGER | N | Basic 부품 여부 (기본값 0) |

### 전체 row 수: 633,341

---

## 3. 카테고리 분포

- **고유 category 수**: 92
- **고유 subcategory 수**: 706

### category별 부품 수 (주요)

| category | 부품 수 |
|---------|---------|
| (빈 값) | 117,854 |
| Resistors | 93,934 |
| Connectors | 89,397 |
| Capacitors | 49,350 |
| Transistors/Thyristors | 36,566 |
| Circuit Protection | 33,067 |
| Inductors, Coils, Chokes | 32,563 |
| Diodes | 29,929 |
| Power Management (PMIC) | 27,667 |
| Switches | 15,092 |
| Crystals, Oscillators, Resonators | 13,255 |
| Amplifiers/Comparators | 9,306 |
| Logic | 8,028 |
| Embedded Processors & Controllers | 7,882 |
| Optoelectronics | 6,929 |
| Interface | 6,674 |
| Filters | 6,587 |
| Power Modules | 5,256 |

**주의**: 빈 category가 117,854개(18.6%)로 가장 많음. 이 부품들은 category가 빈 문자열.

### subcategory 상위 (주요)

| category | subcategory | 부품 수 |
|---------|------------|---------|
| (빈 값) | (빈 값) | 117,854 |
| Resistors | Chip Resistor - Surface Mount | 79,367 |
| Transistors/Thyristors | MOSFETs | 26,239 |
| Inductors, Coils, Chokes | Power Inductors | 23,138 |
| Connectors | Wire To Board Connector | 22,830 |
| Circuit Protection | ESD And Surge Protection (TVS/ESD) | 22,769 |
| Capacitors | Multilayer Ceramic Capacitors MLCC - SMD/SMT | 22,752 |

---

## 4. 제조사 / 패키지 / 재고 / 가격

### 제조사 (manufacturer)

- 고유 제조사 수: **1,417**
- 빈 값 수: **165,522** (26.1%)
- 상위: YAGEO (22,593), Texas Instruments (21,193), Vishay (11,764)

### 패키지 (package)

- 고유 package 수: **15,720**
- 빈 값 수: **0** (전부 값 있음, 단 "-" 값 22,282개)
- 상위: 0603 (33,762), 0805 (28,275), 0402 (25,872), 1206 (22,933)
- 중국어 포함 값: "插件" (16,180), "插件,P=2.54mm" (7,826)

### 재고 (stock)

- 타입: INTEGER
- 최소: **5** / 최대: **23,886,316** / 평균: **6,490**
- stock < 5: **0건** (CDFER의 필터링 확인됨)
- stock = 0: **0건**

| 범위 | 부품 수 |
|------|---------|
| 5-9 | 38,246 |
| 10-99 | 168,295 |
| 100-999 | 183,529 |
| 1K-9.9K | 203,863 |
| 10K-99K | 34,790 |
| 100K-999K | 4,151 |
| 1M+ | 467 |

### 가격 (price)

**저장 형식**: 쉼표로 구분된 "수량시작-수량끝:단가(USD)" 쌍의 문자열

```
1-199:0.0189,200-599:0.0163,600-3999:0.0152,4000-7999:0.0144,8000-19999:0.014,20000-:0.0138
```

- 형식: `{from}-{to}:{price},{from}-{to}:{price},...`
- 마지막 구간의 to는 빈 값 (= 무제한)
- JSON 아님 — 커스텀 문자열 형식
- 빈 값: **1건** (사실상 100% 존재)
- 가격은 USD 기준

**첫 단가 추출 SQL** (동작 확인됨):
```sql
CAST(substr(price, instr(price,':')+1, 
     CASE WHEN instr(price,',') > 0 
          THEN instr(price,',')-instr(price,':')-1
          ELSE length(price)-instr(price,':')
     END) AS REAL) as first_price
```

---

## 5. attributes 구조

### 형식

- JSON 문자열 (`{"key": "value", ...}`)
- 파싱 정상 동작
- 빈 값 또는 `{}`: **41,080건** (6.5%)
- 유효 데이터: **592,261건** (93.5%)

### 카테고리별 attributes 예시

| 카테고리 | 대표 keys |
|---------|----------|
| Resistors | Resistance, Tolerance, Power(Watts), Type, Temperature Coefficient, Voltage-Supply(Max) |
| Capacitors | Capacitance, Voltage Rating, Temperature Coefficient, Tolerance |
| Inductors | Inductance, Current Rating, DC Resistance(DCR), Current - Saturation(Isat), Tolerance |
| Diodes | Voltage - DC Reverse(Vr), Current - Rectified, Voltage - Forward(Vf@If) |
| MOSFETs | Drain to Source Voltage, Current - Continuous Drain(Id), RDS(on), Gate Charge(Qg) |
| MCU | ADC (Bit), CPU Maximum Speed, Number of I/O |
| LDO | Output Voltage, Output Current, Voltage Dropout, Voltage - Supply |
| Connectors | Connector Type, Gender, Number of Contacts, Mounting Type |
| Sensors | Resistance @ 25℃, B Constant, Operating Temperature |
| Crystals | Frequency, Load Capacitance, Frequency Stability |

### 핵심 특성

- **카테고리마다 key가 완전히 다름** — 통합 스키마 불가
- **같은 카테고리 내에서도 key 개수/종류가 부품마다 다를 수 있음**
- **값에 단위 포함** — "10kΩ", "100mW", "50V" 등 (파싱 필요)
- **jlc_components.attributes와 lcsc_components.attributes는 같은 부품이라도 key명이 다름**

### lcsc_components.attributes

lcsc_components에도 별도의 attributes가 있음. LCSC 웹사이트에서 수집한 데이터로, jlc_components의 attributes와 key명이 다를 수 있음.

예: jlc_components에서 `"DC Resistance(DCR)"` → lcsc_components에서 `"DC Resistance"`

---

## 6. 데이터 존재율

| 항목 | 존재 수 | 비율 |
|------|---------|------|
| description (비어있지 않음) | 519,100 | 82.0% |
| datasheet (비어있지 않음) | 505,133 | 79.8% |
| manufacturer (비어있지 않음) | 467,819 | 73.9% |
| attributes (비어있지 않음) | 592,261 | 93.5% |
| price (비어있지 않음) | 633,340 | 100.0% |
| stock > 0 | 633,341 | 100.0% |

---

## 7. Basic / Preferred / library_type

### library_type 분포

| library_type | 부품 수 |
|-------------|---------|
| expand | 632,991 |
| base | 350 |

### basic 컬럼 분포

| basic | 부품 수 |
|-------|---------|
| 0 | 633,341 |

**basic 컬럼은 모두 0**. 이 DB에서는 basic 정보가 사실상 무의미.

### preferred 분포

| preferred | 부품 수 |
|----------|---------|
| 0 | 632,351 |
| 1 | 990 |

### 조합

| library_type | basic | preferred | 부품 수 |
|-------------|-------|-----------|---------|
| expand | 0 | 0 | 632,001 |
| expand | 0 | 1 | 990 |
| base | 0 | 0 | 350 |

**분석**: 

- `basic` 컬럼은 CDFER의 generate-database.py에서 추가된 컬럼이지만, 별도의 CSV 파일(basic/preferred parts 목록)에 있는 component_code에 대해서만 UPDATE하는 방식. 현재 DB에서는 전부 0 — 이는 해당 UPDATE 로직이 이 SQLite에 적용되지 않았거나, 매칭되는 코드가 없었을 수 있음.
- `library_type='base'`가 350개 존재: JLCPCB에서 Basic으로 지정된 부품 중 재고 5개 이상인 것.
- tscircuit/jlcsearch는 `library_type`을 기준으로 Basic을 판단: `Boolean(c.basic)` 대신 `library_type` 필드에서 변환.

**우리 DB에서 Basic 판정의 source of truth**:

`library_type` 컬럼이 source of truth. 근거:
1. `basic` 컬럼은 전부 0이므로 정보가 없음
2. `library_type='base'`는 원본 JLCPCB API에서 직접 가져온 값 (yaqwsx/jlcparts의 jlcpcb.py에서 `_normalizeLibraryType`으로 변환: "basic"→"base", "extended"→"expand")
3. tscircuit/jlcsearch도 `library_type`을 기준으로 `is_basic` 계산: `is_basic: Boolean(c.basic)` — 여기서 `c.basic`은 yaqwsx/jlcparts가 `library_type == "base"`로 설정한 boolean 필드

따라서 우리 프로젝트에서는:
- **Basic 부품**: `library_type = 'base'` (350개)
- **Extended 부품**: `library_type = 'expand'` (632,991개)
- **Preferred 부품**: `preferred = 1` (990개)
- `basic` 컬럼은 무시

---

## 8. FTS 검색

### 현재 상태: FTS 인덱스가 비어있음

```
jlc_components_fts_docsize: 0 rows
jlc_components_fts_idx: 0 rows
```

FTS5 테이블 구조(schema)만 존재하고 실제 데이터가 채워지지 않은 상태.
**FTS MATCH 쿼리는 모두 0 결과를 반환**.

### LIKE 검색 성능 (대안)

| 키워드 | 결과 수 | 실행 시간 |
|-------|---------|----------|
| STM32F103 | 65 | 1,744ms |
| 10k | 6,217 | 1,788ms |
| ESP32 | 94 | 1,658ms |
| LM1117 | 112 | 1,498ms |
| USB-C | 1 | 1,485ms |

**LIKE 검색은 1.5~1.8초** (인덱스 없는 전체 테이블 스캔).
프로덕션 사용 시 FTS 인덱스 재구축 또는 별도 인덱스 생성이 필수.

---

## 9. SQL 기능 확인

### 동작 확인된 쿼리 패턴

**중요: 모든 필터 쿼리는 SCAN jlc_components (풀 테이블 스캔)**

EXPLAIN QUERY PLAN 실행 결과, 현재 DB에는 일반 인덱스가 전혀 없으며 모든 WHERE 절은 전체 테이블을 스캔합니다.

```
EXPLAIN QUERY PLAN SELECT * FROM jlc_components WHERE category='Capacitors' LIMIT 5
→ SCAN jlc_components

EXPLAIN QUERY PLAN SELECT * FROM jlc_components WHERE manufacturer='Texas Instruments' LIMIT 5
→ SCAN jlc_components

EXPLAIN QUERY PLAN SELECT * FROM jlc_components ORDER BY stock DESC LIMIT 5
→ SCAN jlc_components + USE TEMP B-TREE FOR ORDER BY
```

이전 분석에서 category 필터가 0.1~0.3ms로 "매우 빠르다"고 판단한 것은 **LIMIT 5가 걸린 짧은 쿼리에서 우연히 빠른 결과를 반환한 것**이며, 실제로는:

| 쿼리 유형 | LIMIT 5 시간 | COUNT(*) 시간 (풀 스캔) |
|----------|:--------:|:--------:|
| category 필터 | 0.3ms | **1,261ms** |
| manufacturer 필터 | 3.1ms | **1,103ms** |
| package 필터 | 0.3ms | **1,251ms** |
| category + subcategory | 0.1ms | **1,649ms** |

LIMIT 5 + 필터 조합이 빨라 보이는 이유: SQLite가 PK 순서로 스캔하다 조건 일치하는 첫 5건을 빠르게 찾기 때문. 하지만 페이지네이션(큰 OFFSET), 결과 수 카운트, 정렬이 필요하면 풀 스캔이 발생.

### 큰 OFFSET 성능

| OFFSET | 실행 시간 |
|--------|----------|
| 0 | 0.3ms |
| 1,000 | 32.9ms |
| 50,000 | 694.3ms |
| 90,000 | 1,221ms |

### 복합 조건 + 정렬

| 쿼리 | 실행 시간 | EXPLAIN |
|------|----------|---------|
| `WHERE category='Capacitors' ORDER BY stock DESC LIMIT 5` | 1,271ms | SCAN + TEMP B-TREE |
| `ORDER BY stock DESC LIMIT 5` (전체) | 1,208ms | SCAN + TEMP B-TREE |

**결론**: 현재 DB에서는 인덱스가 전혀 없으므로:
- 첫 페이지(LIMIT 5, OFFSET 0) → 빠름 (우연)
- 페이지네이션, 정렬, COUNT → **항상 1~2초 풀 스캔**
- 프로덕션 사용을 위해서는 category, manufacturer, package, stock에 인덱스 추가 필수

### 가격 정렬 가능 여부

price는 문자열이므로 직접 ORDER BY 불가. 첫 단가를 SQL 런타임에 추출해서 정렬할 수는 있으나 매번 풀 스캔 필요 (1.8초). 프로덕션에서는 first_price 컬럼을 미리 계산해서 저장하거나 별도 인덱스를 만들어야 함.

---

## 10. jlcparts와의 관계

### meta 테이블 내용

| key | value |
|-----|-------|
| format | source-db-v2 |
| migrated_from | cache.sqlite3 |
| jlc_components | 7,156,944 (원본 전체 수) |
| lcsc_components | 4,099,778 |
| migration_seconds | 552.41 |

### 원본 → CDFER DB 변환

- **원본 (yaqwsx/jlcparts)**: 7,156,944 부품
- **CDFER DB**: 633,341 부품 (원본의 8.8%)
- **제거된 것**: stock < 5인 부품 (약 91% 제거)
- **그대로 유지**: 스키마(jlc_components, lcsc_components 테이블 구조), 데이터 형식
- **추가한 것**: FTS5 가상 테이블 (하지만 인덱스 데이터 비어있음), `basic` 컬럼 (모두 0)
- **수정**: VACUUM으로 파일 크기 최적화

### lcsc_components 테이블

- 전체: 4,099,946 rows (원본 그대로 유지됨 — 필터링 안 됨)
- jlc_components와 JOIN 가능: 401,334 (jlc_components의 63.4%)
- lcsc에만 있는 부품: 3,698,612 (원본에서 재고 부족으로 jlc에서 삭제된 부품들의 LCSC 데이터)

### jlcsearch 참고 가능성

tscircuit/jlcsearch는 이 DB와 동일한 원본(yaqwsx/jlcparts)을 사용하며, derived tables를 통해 카테고리별 파라미터를 정규화함.

**중요: jlcsearch의 attributes 데이터 흐름**

jlcsearch의 derived table parser가 읽는 `extra.attributes`는 단순히 `jlc_components.attributes`가 아닙니다. 실제 데이터 흐름:

1. yaqwsx/jlcparts의 `sourceDb.py` → `_rowToComponent()`가 DB에서 부품을 읽을 때:
   - `jlc_components.attributes` → `jlc_extra.attributes`로 매핑
   - `lcsc_components.attributes` → `extra.attributes`로 매핑

2. yaqwsx/jlcparts의 `datatables.py` → `_mergeAttributes()`가 두 소스를 병합:
   ```python
   def _mergeAttributes(component):
       attr = dict(_extraAttributes(component.get("extra", {})))   # lcsc_components.attributes (기본)
       for key, value in _jlcAttributes(component.get("jlc_extra", {})).items():  # jlc_components.attributes
           if value in ["", "-"]:
               continue
           attr[key] = value  # jlc_extra가 extra를 덮어씀 (override)
       return attr
   ```

3. 병합된 attributes가 최종 `components` 테이블의 `extra` JSON에 포함됨

4. jlcsearch의 derived table parser (`resistor.ts`, `capacitor.ts` 등)는 이 **병합된 extra.attributes**를 읽음:
   ```typescript
   const extra = JSON.parse(c.extra ?? "{}")
   const rawResistance = extra?.attributes?.["Resistance"]
   ```

**우리 DB에서의 차이점**:

우리 `jlcpcb-components.sqlite3`에는:
- `jlc_components.attributes` — JLCPCB API에서 온 속성 (key명: "Resistance", "Power(Watts)" 등)
- `lcsc_components.attributes` — LCSC 웹에서 온 속성 (key명: 비슷하지만 약간 다름, 예: "DC Resistance" vs "DC Resistance(DCR)")

**jlcsearch parser를 직접 재사용할 경우**:
- `jlc_components.attributes`만 사용: 대부분의 카테고리에서 주요 파라미터가 포함되어 있으므로 **Resistor, Capacitor 등 기본 카테고리는 동작함**. 단, MCU 등 일부 카테고리에서는 LCSC 측 속성이 더 풍부할 수 있음.
- `lcsc_components.attributes`와 병합 사용: 원본 jlcparts와 동일한 결과. JOIN으로 구현 가능 (jlc_components의 63%가 lcsc_components에 매핑됨).

**Resistor 예시** (우리 DB의 `jlc_components.attributes` 직접 사용 가능):
```json
{"Resistance":"10kΩ","Tolerance":"±1%","Power(Watts)":"100mW","Type":"Thick Film Resistor",...}
```
→ jlcsearch의 `parseAndConvertSiUnit("10kΩ")` → 10000 (바로 적용 가능)

**Capacitor 예시** (우리 DB의 `jlc_components.attributes` 직접 사용 가능):
```json
{"Capacitance":"100nF","Voltage Rating":"50V","Temperature Coefficient":"X7R","Tolerance":"±10%"}
```
→ jlcsearch의 `parseAndConvertSiUnit("100nF")` → 0.0000001 (바로 적용 가능)

**결론**: jlcsearch의 SI unit 파서와 카테고리별 key 매핑은 `jlc_components.attributes`에 직접 적용 가능하나, 일부 카테고리에서는 병합된 데이터를 쓸 때보다 속성이 빠져있을 수 있음. 나중에 파라미터 필터를 구현할 때 카테고리별로 `jlc_components.attributes`만으로 충분한지 검증이 필요함.

---

## 11. 최종 판단

### 이 DB를 첫 웹사이트 데이터 소스로 그대로 사용해도 되는가?

**조건부 가능**. 데이터 자체는 충분하지만, 현재 상태로는 검색과 정렬에 심각한 성능 문제가 있음. 인덱스 추가 및 FTS 재구축이 선행되어야 함.

### 검색 구현에 문제가 없는가?

**문제 있음**. FTS 인덱스가 비어있어서 키워드 검색이 작동하지 않음. LIKE 검색은 1.5초 이상 소요. **FTS 인덱스 재구축이 필수**.

### 카테고리 탐색 구현에 문제가 없는가?

**데이터 측면에서는 문제 없음**. 92개 category, 706개 subcategory 체계가 잘 갖춰져 있음. 단, 빈 category가 117,854건(18.6%)인 점 주의. **성능 측면에서는 인덱스 필요** — category 필터도 풀 스캔이므로, 결과 수 표시나 정렬이 필요하면 1초 이상. 인덱스를 추가하면 해결됨.

### 정렬/페이징 구현에 문제가 없는가?

**문제 있음**. LIMIT/OFFSET 자체는 동작하나, 큰 OFFSET(5만+)에서 700ms~1.2초. ORDER BY stock/price는 항상 풀 스캔 (1~2초). 모든 쿼리가 SCAN jlc_components (인덱스 없음). 프로덕션 수준의 응답을 위해 인덱스 추가 필수.

### 파라미터 필터를 만들기 위해 추가 처리가 어느 정도 필요한가?

**상당한 처리 필요**. attributes가 JSON 문자열이고 카테고리마다 key가 완전히 다르며 값에 단위가 포함됨. tscircuit/jlcsearch의 derived table + SI unit 파서 패턴을 참고하여 카테고리별로:
1. JSON에서 key 추출
2. 단위 포함 값을 숫자로 파싱 ("10kΩ" → 10000)
3. 정규화된 컬럼으로 별도 테이블 또는 인덱스 생성

이 과정이 필요함. 45개 카테고리에 대해 jlcsearch가 이미 구현한 코드를 참고할 수 있으나, jlcsearch는 `jlc_components.attributes`와 `lcsc_components.attributes`를 병합한 데이터를 사용한다는 점 주의. 우리 DB에서는 `jlc_components.attributes`만으로도 Resistor/Capacitor 등 주요 카테고리의 핵심 파라미터가 포함되어 있으므로 MVP 단계에서는 충분하나, 일부 카테고리에서는 `lcsc_components.attributes`와의 JOIN 병합이 필요할 수 있음.

### 다음 STEP에서 가장 먼저 해야 할 일 하나

**이 DB의 복사본에 인덱스와 FTS를 재구축하는 것**.

구체적으로:
- FTS5 인덱스 재구축 (`INSERT INTO jlc_components_fts(jlc_components_fts) VALUES('rebuild')`)
- category, manufacturer, package, stock에 일반 인덱스 추가
- first_price 계산 컬럼 추가 (또는 별도 뷰)

이것만으로 키워드 검색, 카테고리 필터 + 정렬, 가격 정렬이 모두 실용적 속도로 가능해짐.
