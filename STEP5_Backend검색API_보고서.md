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
2. FTS5 특수문자 제거: `"` `'` `*` `(` `)` `-` `+` `^` `~` `{` `}` `:` `[` `]` `|` `&` `!`
3. 안전한 문자만 유지: `[a-zA-Z0-9 ._/]`
4. 공백으로 분리 → 토큰별 `*` 접미사 추가 (prefix query)
5. 최대 5 토큰으로 제한
6. 모든 토큰이 비어있으면 None 반환 → 빈 결과

예: `STM32F103` → `STM32F103*`
예: `USB-C` → `USB* C*` (하이픈 제거, 두 토큰으로 분리)
예: `"test"` → `test*` (따옴표 제거)
예: `*` → None (빈 결과)

---

## API 테스트 결과

### 정상 검색

| 검색어 | HTTP | 결과 수 | DB 시간 | 첫 결과 |
|--------|:----:|:------:|:-------:|---------|
| STM32F103 | 200 | 20 | 4.4ms | C8734 STM32F103C8T6 stock=270,767 |
| ESP32 | 200 | 20 | 3.8ms | C2913202 ESP32-S3-WROOM-1-N16R8 |
| LM1117 | 200 | 20 | 2.4ms | C126027 LM1117S-3.3 stock=73,060 |
| USB-C | 200 | 20 | 345ms | C2765186 TYPE-C 16PIN stock=1,171,811 |

USB-C가 느린 이유: `USB-C` → `USB* C*`로 변환되어 "USB"로 시작하는 모든 부품과 "C"로 시작하는 모든 부품의 교집합을 검색. "C"는 거의 모든 MPN에 포함되므로 범위가 넓어짐. 향후 하이픈을 포함한 복합어 처리를 개선할 수 있음.

### 비정상 입력

| 입력 | HTTP | 동작 |
|------|:----:|------|
| q= (빈값) | 200 | 빈 결과 반환 |
| q=" (따옴표만) | 200 | 빈 결과 (특수문자 제거 후 빈 토큰) |
| q=* (별표만) | 200 | 빈 결과 |
| q=STM32F103" | 200 | 20건 정상 반환 (따옴표 제거됨) |
| limit=10000 | 422 | FastAPI 자동 검증 (le=100 초과) |
| offset=-1 | 422 | FastAPI 자동 검증 (ge=0 미달) |

**서버 crash 없음**, 모든 비정상 입력에 대해 안전한 응답.

---

## 검색 결과 예시

```json
{
  "query": "STM32F103",
  "limit": 20,
  "offset": 0,
  "total": 20,
  "queryTimeMs": 4.4,
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

| 검색어 | DB query 시간 |
|--------|:-------------:|
| STM32F103 | 4.4ms |
| ESP32 | 3.8ms |
| LM1117 | 2.4ms |
| USB-C | 345ms (토큰 분리 문제) |

STEP 3에서 검증한 FTS 성능 (0.4~1.4ms)이 backend를 거쳐서도 유지됨 (단일 토큰 검색 기준 2~5ms). 차이는 JOIN + ORDER BY stock DESC + LIMIT/OFFSET 처리 시간.

---

## 최종 판단

- 검색 API가 정상 동작함
- FTS5 prefix query로 MPN 검색이 실용적 속도 (2~5ms)
- 입력 sanitization으로 SQL injection과 FTS query error 방지됨
- FastAPI의 자동 파라미터 검증으로 range 오류 처리됨
- 2GB SQLite를 read-only로 안정적으로 서빙 가능
- USB-C 같은 하이픈 포함 복합어는 향후 개선 여지 있음
