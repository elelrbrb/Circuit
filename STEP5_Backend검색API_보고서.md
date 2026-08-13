# STEP 5: Backend 검색 API 보고서

## 기술 선택

**Python + FastAPI + sqlite3 (표준 라이브러리)**

이유:
- sqlite3는 Python 표준 라이브러리에 포함, 2GB+ 파일 안정적 read-only 지원
- FTS5 MATCH, prepared statement(parameter binding) 기본 지원
- FastAPI는 경량이면서 REST API 확장 용이, 자동 입력 검증(Query 파라미터 타입/범위), 자동 OpenAPI 문서
- ORM 없이 raw SQL로 직접 제어
- scripts/prepare_db.py와 기술 통일 (Python)

---

## 프로젝트 구조

```
backend/
├── .env.example          # 환경변수 예시
├── requirements.txt      # 의존성
└── src/
    ├── __init__.py
    ├── main.py           # FastAPI 앱, 라우트
    ├── database.py       # DB 연결, 검증
    └── search.py         # FTS 검색 로직, 입력 sanitization
```

---

## 실행 방법

```bash
cd backend
pip install -r requirements.txt

# .env 파일 생성 (DB_PATH 설정)
cp .env.example .env
# .env에서 DB_PATH를 실제 준비된 DB 경로로 수정

# 서버 시작
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

---

## API 엔드포인트

### GET /api/health

```json
{"status": "ok", "database": "connected"}
```

### GET /api/parts/search

| 파라미터 | 타입 | 기본값 | 범위 | 설명 |
|---------|------|-------|------|------|
| q | string | "" | max 200자 | 검색 키워드 |
| limit | int | 20 | 1~100 | 결과 수 |
| offset | int | 0 | ≥ 0 | 페이지네이션 |

---

## 검색 SQL

```sql
SELECT
    j.lcsc, j.mfr, j.manufacturer, j.category, j.subcategory,
    j.package, j.description, j.stock, j.first_price,
    j.price, j.datasheet, j.library_type, j.preferred
FROM jlc_components j
INNER JOIN jlc_components_fts fts ON fts.rowid = j.rowid
WHERE fts.jlc_components_fts MATCH ?
ORDER BY j.stock DESC
LIMIT ? OFFSET ?
```

FTS MATCH에는 sanitize된 prefix query를 parameter binding으로 전달.

---

## FTS 입력 Escaping 방식

1. 길이 검증 (200자 초과 거부)
2. 정규식으로 alphanumeric + underscore 토큰만 추출 (`[a-zA-Z0-9_]+`)
3. 각 토큰을 FTS5 double-quoted string으로 래핑 → FTS operator 충돌 방지 (AND/OR/NOT 등)
4. 2자 이상 토큰: `"token"*` (prefix query)
5. 1자 토큰: `"token"` (exact match only — 너무 넓은 prefix 방지)
6. 최대 5 토큰으로 제한
7. 토큰이 하나도 추출되지 않으면 None → 빈 결과

예:
- `STM32F103` → `"STM32F103"*`
- `USB-C` → `"USB"* "C"` (하이픈 제거, C는 1자이므로 prefix 없음)
- `LM1117S-3.3` → `"LM1117S"* "3"` (특수문자에서 분리, 단일 숫자 "3"은 exact)
- `AND` → `"AND"*` (FTS operator와 충돌 없음)
- `"` → None (토큰 없음 → 빈 결과)
- `*` → None (토큰 없음 → 빈 결과)

---

## API 테스트 결과

### 정상 검색

| 검색어 | HTTP | 결과 수 | DB 시간 | 첫 결과 |
|--------|:----:|:------:|:-------:|---------|
| STM32F103 | 200 | 20 | 5.9ms | C8734 STM32F103C8T6 |
| STM32F103C8T6 | 200 | 3 | 0.6ms | C8734 STM32F103C8T6 |
| ESP32 | 200 | 20 | 2.5ms | C2913202 ESP32-S3-WROOM-1-N16R8 |
| LM1117 | 200 | 20 | 4.1ms | C126027 LM1117S-3.3 |
| USB-C | 200 | 20 | **25.7ms** | C2765186 TYPE-C 16PIN |
| LM1117S-3.3 | 200 | 10 | 6.9ms | C126027 LM1117S-3.3 |

**USB-C 성능 개선**: 이전 345ms → 수정 후 **25.7ms** (13.4x 개선). 원인: `"C"` exact match (prefix 없음)로 변경하여 overly broad 검색 제거.

### 특수 입력 (FTS operator 등)

| 입력 | HTTP | 동작 | 비고 |
|------|:----:|------|------|
| AND | 200 | 20건 반환 | `"AND"*`로 변환, operator 충돌 없음 |
| OR | 200 | 20건 반환 | `"OR"*`로 변환 |
| NOT | 200 | 20건 반환 | `"NOT"*`로 변환 |
| " | 200 | 0건 (빈 결과) | 토큰 추출 불가 → None |
| * | 200 | 0건 (빈 결과) | 토큰 추출 불가 → None |
| ( | 200 | 0건 (빈 결과) | 토큰 추출 불가 → None |
| A/B | 200 | 20건 반환 | `"A" "B"*`로 변환 (A는 1자, B는 1자) |
| test.test | 200 | 20건 반환 | `"test"* "test"*`로 변환 |

**서버 crash 없음**, 모든 입력에서 FTS syntax error 없음.

### 파라미터 오류

| 입력 | HTTP | 동작 |
|------|:----:|------|
| limit=10000 | 422 | FastAPI 자동 검증 (le=100 초과) |
| offset=-1 | 422 | FastAPI 자동 검증 (ge=0 미달) |

### 에러 응답 구분

| 상황 | HTTP | 응답 |
|------|:----:|------|
| 정상 검색 결과 0건 | 200 | `{"returnedCount": 0, "items": []}` |
| DB/검색 내부 오류 | 500 | `{"error": "Internal search error..."}` |
| 파라미터 검증 실패 | 422 | FastAPI 자동 에러 응답 |

---

## 검색 결과 예시

```json
{
  "query": "STM32F103",
  "limit": 20,
  "offset": 0,
  "returnedCount": 20,
  "queryTimeMs": 5.9,
  "items": [
    {
      "lcsc": 8734,
      "mfr": "STM32F103C8T6",
      "manufacturer": "STMicroelectronics",
      "category": "Embedded Processors & Controllers",
      "subcategory": "Microcontrollers (MCU/MPU/SOC)",
      "package": "LQFP-48(7x7)",
      "description": "...",
      "stock": 270767,
      "firstPrice": 1.4415,
      "price": "1-9:1.4415,10-49:1.3766,...",
      "datasheet": "https://...",
      "isBasic": false,
      "preferred": false
    }
  ]
}
```

---

## DB Query 실행시간

| 검색어 | DB query 시간 | 비고 |
|--------|:-------------:|------|
| STM32F103 | 5.9ms | prefix query |
| STM32F103C8T6 | 0.6ms | exact token match |
| ESP32 | 2.5ms | prefix query |
| LM1117 | 4.1ms | prefix query |
| USB-C | 25.7ms | "USB"* "C" (C는 exact, 이전 345ms에서 개선) |
| LM1117S-3.3 | 6.9ms | "LM1117S"* "3" |

STEP 3에서 검증한 FTS 성능이 backend를 거쳐서도 유지됨. JOIN + ORDER BY stock DESC + LIMIT/OFFSET 포함하여 단일 토큰 기준 1~6ms.

---

## 최종 판단

- 검색 API가 정상 동작함
- FTS5 double-quoted prefix query로 MPN 검색이 실용적 속도 (1~6ms)
- double-quote 래핑으로 AND/OR/NOT 등 FTS operator 충돌 완전 방지
- 단일 문자 토큰에 prefix 없음으로 overly broad 검색 방지 (USB-C: 345ms → 25.7ms)
- parameter binding + 토큰 추출 방식으로 SQL injection/FTS error 방지
- FastAPI 자동 파라미터 검증으로 range 오류 처리
- 예외 처리: 정상 0건(200) vs 서버 오류(500) 명확히 구분
- 2GB SQLite를 read-only로 안정적으로 서빙 가능
