# STEP 3: CDFER SQLite 성능 최적화 실험 보고서

## 실험 환경

- 원본: `C:\Users\gyuwon\Downloads\jlcpcb-components.sqlite3` (수정하지 않음)
- 테스트 복사본: `C:\Users\gyuwon\Downloads\jlcpcb-components-test.sqlite3`
- SQLite 3.45.3, Python sqlite3 모듈

---

## 1. 변경 전 기준 측정

모든 쿼리가 `SCAN jlc_components` (풀 테이블 스캔).

| 쿼리 | 실행 시간 | EXPLAIN QUERY PLAN |
|------|:---------:|-------------------|
| keyword LIKE (STM32F103) | 1,836ms | SCAN jlc_components |
| category COUNT (Capacitors) | 1,313ms | SCAN jlc_components |
| category+subcategory COUNT | 1,317ms | SCAN jlc_components |
| manufacturer filter (TI) | 1,622ms | SCAN jlc_components |
| package filter (0603) | 1,256ms | SCAN jlc_components |
| stock DESC LIMIT 10 | 1,438ms | SCAN + TEMP B-TREE FOR ORDER BY |
| category + stock DESC LIMIT 10 | 1,459ms | SCAN + TEMP B-TREE FOR ORDER BY |
| OFFSET 1000 | 15ms | SCAN jlc_components |
| OFFSET 50000 | 482ms | SCAN jlc_components |

---

## 2. FTS rebuild

### 실행

```sql
INSERT INTO jlc_components_fts(jlc_components_fts) VALUES('rebuild');
```

- rebuild 소요 시간: **26.8초**
- rebuild 후 `jlc_components_fts_idx`: 14,924 rows
- rebuild 후 `jlc_components_fts_docsize`: 633,341 rows

### FTS 검색 결과

| 검색어 | FTS 결과 수 | FTS 시간 | LIKE 시간 | 속도 향상 |
|--------|:---------:|:---------:|:---------:|:---------:|
| STM32F103 | 0 | 0.2ms | 3,099ms | — (토큰 문제) |
| ESP32 | 93 | 0.6ms | 1,778ms | 1,646x |
| LM1117 | 35 | 0.5ms | 1,797ms | 1,402x |
| "USB-C" | 1 | 3.9ms | — | — |

### FTS 토큰화와 MPN 검색 문제

`STM32F103`이 FTS에서 0 결과를 반환하는 원인 (실증 확인):

`unicode61` 토크나이저는 문자와 숫자를 **분리하지 않음**. "STM32F103C8T6" 전체가 하나의 token(`stm32f103c8t6`)으로 저장됨. `fts5vocab`으로 확인한 결과:

```
term='stm32f103c8t6'  doc_count=3   ← 전체 MPN이 하나의 token
term='stm32f103'      (존재하지 않음) ← "STM32F103"이라는 독립 token 없음
```

따라서 `MATCH 'STM32F103'`은 **정확한 token 매칭**을 시도하지만, 해당 token이 인덱스에 존재하지 않으므로 0건. DB에 있는 token은 `stm32f103c8t6`, `stm32f103vft6`, `stm32f103rgt6` 등 전체 MPN임.

**해결: prefix query (`*` 사용)**

| 쿼리 | 결과 수 | 시간 |
|------|:------:|:----:|
| `MATCH 'STM32F103'` | 0 | 2.2ms |
| `MATCH 'STM32F103*'` (prefix) | 65 | 0.4ms |
| `MATCH 'STM32F103C8T6'` (정확) | 3 | 0.2ms |
| `MATCH 'STM32*'` (prefix) | 1,230 | 1.3ms |
| `MATCH 'ESP32*'` (prefix) | 94 | 1.4ms |
| `MATCH 'LM1117*'` (prefix) | 112 | 1.1ms |

prefix query(`*`)를 사용하면 LIKE와 동일한 65건을 찾으며 속도도 0.4~1.4ms로 매우 빠름.

**프로덕션에서의 대응**:
- 검색 입력에 자동으로 `*`을 붙여 prefix query로 실행하는 것이 가장 단순한 해결책
- 또는 FTS5 prefix index (`prefix='2,3,4'` 옵션)를 추가하면 prefix 검색이 더 빨라질 수 있음 (현재도 충분히 빠르므로 당장 필요하지는 않음)
- trigram tokenizer 등으로 재설계하면 부분 문자열 검색도 가능하지만, 현재 스키마의 prefix query로 충분히 실용적

### FTS + JOIN 사용

```sql
SELECT j.lcsc, j.mfr, j.category, j.stock
FROM jlc_components j
INNER JOIN jlc_components_fts fts ON fts.rowid = j.rowid
WHERE fts.jlc_components_fts MATCH 'ESP32'
ORDER BY j.stock DESC LIMIT 5
```
→ **3.5ms** (매우 빠름)

### FTS 결론

- **기존 FTS 구조를 rebuild하면 정상 작동함**
- 대부분의 키워드에서 **1000x 이상 성능 향상**
- 정확 token 매칭(`MATCH 'STM32F103'`)은 해당 문자열이 독립 token으로 존재할 때만 동작
- MPN 검색에서는 **prefix query(`MATCH 'STM32F103*'`)**를 사용하면 LIKE와 동일한 결과를 0.4ms에 반환
- 프로덕션에서는 사용자 입력에 `*`을 자동 추가하여 prefix query로 실행하는 것이 가장 단순하고 효과적

---

## 3. 일반 index 추가

### 추가한 index

| index 이름 | 정의 | 생성 시간 |
|-----------|------|:---------:|
| idx_category | `ON jlc_components(category)` | 3.0초 |
| idx_cat_subcat | `ON jlc_components(category, subcategory)` | 3.5초 |
| idx_manufacturer | `ON jlc_components(manufacturer)` | 2.8초 |
| idx_package | `ON jlc_components(package)` | 2.3초 |
| idx_stock | `ON jlc_components(stock DESC)` | 2.1초 |
| idx_cat_stock | `ON jlc_components(category, stock DESC)` | 3.2초 |

### index 추가 후 성능

| 쿼리 | Before | After | 사용 index | 향상 |
|------|:------:|:-----:|-----------|:----:|
| category COUNT | 1,313ms | **22ms** | COVERING INDEX idx_cat_stock | 60x |
| category+subcategory COUNT | 1,317ms | **38ms** | COVERING INDEX idx_cat_subcat | 35x |
| manufacturer filter | 1,622ms | **6ms** | COVERING INDEX idx_manufacturer | 270x |
| package filter | 1,256ms | **6ms** | COVERING INDEX idx_package | 209x |
| stock DESC LIMIT 10 | 1,438ms | **0.2ms** | COVERING INDEX idx_stock | 7,190x |
| category + stock DESC | 1,459ms | **0.6ms** | COVERING INDEX idx_cat_stock | 2,432x |
| OFFSET 50000 | 482ms | **9ms** | COVERING INDEX idx_category | 54x |

**모든 index가 COVERING INDEX로 사용됨** — 테이블 자체를 읽지 않고 인덱스만으로 쿼리 처리.

---

## 4. 가격 정렬

### 방법 비교

| 방법 | 설명 | category+정렬 시간 |
|------|------|:------------------:|
| A: SQL 런타임 추출 | `CAST(substr(price, ...) AS REAL)` 매번 계산 | 1,285ms |
| B: first_price 컬럼 + index | 미리 계산해서 저장, index 생성 | **0.5ms** |

### 방법 B 상세

```sql
ALTER TABLE jlc_components ADD COLUMN first_price REAL;

UPDATE jlc_components SET first_price = 
    CAST(substr(price, instr(price,':')+1, 
         CASE WHEN instr(price,',') > 0 
              THEN instr(price,',')-instr(price,':')-1
              ELSE length(price)-instr(price,':')
         END) AS REAL)
WHERE price != '';

CREATE INDEX idx_first_price ON jlc_components(first_price);
CREATE INDEX idx_cat_price ON jlc_components(category, first_price);
```

- UPDATE 소요: 18.6초
- index 생성: 5.9초
- 이후 가격 정렬: **0.3~0.5ms** (COVERING INDEX 사용)

---

## 5. 변경 전후 전체 비교

| 쿼리 | Before | After | 향상 | 사용 index |
|------|:------:|:-----:|:----:|-----------|
| keyword (FTS) | N/A (작동 안 함) | **0.2~1ms** | ∞ | FTS5 virtual table |
| keyword (LIKE) | 1,836ms | 1,836ms | 없음 | (FTS로 대체) |
| category COUNT | 1,313ms | **22ms** | 60x | idx_cat_stock |
| category+subcategory | 1,317ms | **38ms** | 35x | idx_cat_subcat |
| manufacturer | 1,622ms | **6ms** | 270x | idx_manufacturer |
| package | 1,256ms | **6ms** | 209x | idx_package |
| stock 정렬 | 1,438ms | **0.2ms** | 7,190x | idx_stock |
| category + stock 정렬 | 1,459ms | **0.6ms** | 2,432x | idx_cat_stock |
| category + price 정렬 | 1,285ms | **0.5ms** | 2,570x | idx_cat_price |
| OFFSET 50000 | 482ms | **9ms** | 54x | idx_category |

### DB 용량 변화

| 항목 | 크기 |
|------|------|
| 원본 | 2,088.8 MB |
| 최적화 후 | 2,329.1 MB |
| 증가량 | +240.2 MB (+11.5%) |

---

## 6. 최종 판단

### 기존 FTS를 rebuild해서 그대로 사용할 수 있는가?

**사용 가능**. rebuild 자체는 정상 동작하며 대부분의 키워드 검색에서 1000x 이상 성능 향상. `unicode61` 토크나이저는 MPN 전체(예: "STM32F103C8T6")를 하나의 token으로 저장하므로, 부분 MPN 검색(예: "STM32F103")은 prefix query(`MATCH 'STM32F103*'`)로 실행해야 함. prefix query는 0.4~1.4ms로 충분히 빠르므로, 프로덕션에서 사용자 입력에 `*`을 자동 추가하는 방식으로 대응 가능. 현재 FTS 스키마를 재설계할 필요 없음.

### 어떤 일반 index가 실제로 필요한가?

| index | 필요성 | 이유 |
|-------|:------:|------|
| `idx_cat_subcat(category, subcategory)` | **필수** | 카테고리 탐색의 핵심 쿼리 |
| `idx_cat_stock(category, stock DESC)` | **필수** | 카테고리 내 재고순 정렬 |
| `idx_cat_price(category, first_price)` | **필수** | 카테고리 내 가격순 정렬 |
| `idx_manufacturer(manufacturer)` | **필수** | 제조사 필터 |
| `idx_package(package)` | **필수** | 패키지 필터 |
| `idx_stock(stock DESC)` | **필수** | 전체 재고순 정렬 |
| `idx_first_price(first_price)` | 권장 | 전체 가격순 정렬 |

### 어떤 index는 불필요한가?

| index | 판단 | 이유 |
|-------|:----:|------|
| `idx_category(category)` | 불필요 | `idx_cat_subcat`과 `idx_cat_stock`이 category 단독 필터도 커버 |

### 가격 정렬을 어떤 방식으로 처리하는 것이 좋은가?

**방법 B (first_price 컬럼 + index)**가 압도적으로 우수.
- 런타임 추출: 1,285ms
- 미리 계산 + index: 0.5ms

`first_price` = price 문자열의 첫 번째 단가(최소 수량 가격, USD). DB 초기 세팅 시 1회 UPDATE (18초)로 처리. 이후 가격순 정렬은 0.5ms 이내.

### 최적화 후 이 SQLite를 실제 웹사이트 backend에서 사용할 수 있는 수준인가?

**사용 가능**. 최적화 후 모든 주요 쿼리가 **0.2~38ms** 수준으로, 웹 API 응답 시간으로 충분히 실용적. 구체적으로:
- 카테고리 탐색: 22~38ms
- 필터: 6~10ms
- 정렬: 0.2~0.6ms
- 키워드 검색: 0.2~4ms (FTS)
- 페이지네이션: 9ms (OFFSET 50000)

### DB 용량 증가는 허용 범위인가?

**허용 가능**. 원본 2.09GB → 2.33GB (+240MB, +11.5%). index와 FTS 데이터가 추가되었지만 서버 환경에서 문제 없는 수준.

---

## 적용 요약 (다음 STEP에서 실행할 SQL)

```sql
-- FTS rebuild
INSERT INTO jlc_components_fts(jlc_components_fts) VALUES('rebuild');

-- 일반 index
CREATE INDEX idx_cat_subcat ON jlc_components(category, subcategory);
CREATE INDEX idx_cat_stock ON jlc_components(category, stock DESC);
CREATE INDEX idx_manufacturer ON jlc_components(manufacturer);
CREATE INDEX idx_package ON jlc_components(package);
CREATE INDEX idx_stock ON jlc_components(stock DESC);

-- 가격 정렬용
ALTER TABLE jlc_components ADD COLUMN first_price REAL;
UPDATE jlc_components SET first_price = 
    CAST(substr(price, instr(price,':')+1, 
         CASE WHEN instr(price,',') > 0 
              THEN instr(price,',')-instr(price,':')-1
              ELSE length(price)-instr(price,':')
         END) AS REAL)
WHERE price != '';
CREATE INDEX idx_first_price ON jlc_components(first_price);
CREATE INDEX idx_cat_price ON jlc_components(category, first_price);
```
