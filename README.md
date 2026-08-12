# Circuit - 전자부품 통합 검색/비교 플랫폼

여러 전자부품 유통 사이트의 데이터를 통합하여 사용자가 전자부품을 쉽게 찾고, 비교하고, 선택할 수 있는 웹 플랫폼 프로젝트입니다.

---

## 프로젝트 개요

### 목표

전자부품을 구매할 때 여러 사이트를 일일이 돌아다니며 비교하는 비효율을 해결합니다. 하나의 인터페이스에서 다양한 공급업체의 부품 정보를 검색하고, 가격/재고/사양을 한눈에 비교하며, 필요한 부품을 체계적으로 관리할 수 있는 도구를 만듭니다.

### 대상 공급업체

| 공급업체 | 지역 | 특징 | API 지원 |
|---------|------|------|---------|
| **LCSC** | 중국/글로벌 | JLCPCB 부품 공급처, 가격 경쟁력 | 비공식 API |
| **JLCPCB Parts** | 중국/글로벌 | PCB Assembly 전용 라이브러리, Basic/Extended 구분 | 공식 API |
| **Mouser** | 미국/글로벌 | 800만+ 제품, 글로벌 배송 | 공식 API (무료) |
| **DigiKey** | 미국/글로벌 | 가장 풍부한 파라미터 검색, 강력한 API | 공식 API (무료) |
| **element14 / Farnell** | 유럽/아시아 | Avnet 그룹, 유럽/아시아 강세 | 공식 API (무료) |
| **디바이스마트** | 한국 | 국내 최대 전자부품몰, 아두이노/라즈베리파이 | API 없음 |

### 주요 기능 (계획)

- **통합 검색**: 하나의 검색창에서 모든 공급업체의 부품을 동시에 검색
- **카테고리 탐색**: 통합된 카테고리 구조로 부품 브라우징
- **파라미터 필터**: 카테고리별 기술 사양으로 부품 필터링 (저항값, 용량, 전압 등)
- **다중 정렬**: 가격순, 재고순, 관련도순 등
- **부품 상세정보**: 사양, 데이터시트, 이미지, 가격 이력
- **공급업체 비교**: 동일 부품(MPN)을 여러 공급업체에서 가격/재고 비교
- **부품 선택 관리**: 선택한 부품을 리스트로 관리, 내보내기

---

## 현재 상태

> **Phase 0: 조사 및 분석 단계 (완료)**

현재 이 프로젝트는 구현 전 조사/분석 단계에 있습니다. 코드 작성에 앞서 각 공급업체 사이트의 데이터 구조, API 가용성, 그리고 기존 오픈소스 프로젝트들을 충분히 조사하여 최적의 접근 방식을 결정하고 있습니다.

조사 결과는 [`연구조사_전자부품_검색사이트.md`](./연구조사_전자부품_검색사이트.md)에 정리되어 있습니다.

---

## 조사 결과 요약

### 데이터 접근 방법

#### LCSC
- **비공식 REST API**: `https://wwwapi.lcsc.com/v1/search/global-search?keyword={검색어}`
- 인증 없이 사용 가능
- 부품 코드(C번호), MPN, 제조사, 카테고리, 패키지, 수량별 가격, 재고, 데이터시트 URL 제공
- 파라미터 검색은 미지원 (키워드 + 카테고리만)
- 공식 API가 아니므로 언제든 변경 가능

#### JLCPCB
- **공식 Components API**: https://api.jlcpcb.com/
- HMAC-SHA256 인증 (APP_ID, API_KEY, API_SECRET 필요)
- 개발자 포털에서 무료 발급
- 실시간 가격, 재고, 사양, Basic/Extended 구분 제공
- **오픈소스 데이터**: yaqwsx/jlcparts 프로젝트가 전체 부품 DB를 SQLite로 매일 업데이트 (~11GB)

#### Mouser
- **공식 Search API**: https://www.mouser.com/api-hub/
- API Key 기반 인증 (My Mouser 계정에서 무료 발급)
- SOAP + REST 지원
- KeywordSearch, SearchByManufacturerPartNumber, SearchByMouserPartNumber
- 800만+ 제품 검색, 가격/재고/사양 제공

#### DigiKey
- **공식 Product Information V4 API**: https://developer.digikey.com/
- OAuth 2.0 인증 (Client ID + Client Secret)
- Rate Limit: 120 req/min, 1000 req/day
- 가장 풍부한 엔드포인트:
  - KeywordSearch, ProductSearch, ProductDetails
  - Categories (전체 카테고리 트리)
  - Manufacturers (전체 제조사 목록)
  - PricingByQuantity, Substitutions, RecommendedProducts

#### element14 / Farnell / Newark
- **공식 Product Search API (REST)**: https://partner.element14.com/
- API Key 기반 인증
- element14(아시아), Farnell(유럽), Newark(북미) 하나의 API로 접근
- 키워드 검색, MPN 검색, 스토어별 가격/재고

#### 디바이스마트
- **API 없음**
- 웹 스크래핑만 가능 (법적/기술적 검토 필요)
- 데이터 구조화 열악

### 핵심 발견: 이미 존재하는 것 vs 직접 만들 것

#### 이미 존재하는 것 (활용 가능)
| 항목 | 프로젝트/서비스 | 설명 |
|------|---------------|------|
| JLCPCB 전체 부품 DB | yaqwsx/jlcparts | 매일 업데이트되는 SQLite DB |
| JLCPCB 검색 API | tscircuit/jlcsearch | URL에 `.json` 추가로 API 사용 |
| 다중 공급업체 API 래퍼 | peeter123/digikey-api, sparkmicro/mouser-api | Python 라이브러리 |
| 카테고리/파라미터 매핑 | inventree_part_import, Ki-nTree | YAML 기반 매핑 설정 |
| BOM 가격 비교 | KiCost | 오픈소스, 다중 유통업체 |
| 통합 API (유료) | PartFuse, Nexar/Octopart | 하나의 API로 모든 유통업체 |

#### 직접 만들어야 하는 것
| 항목 | 이유 |
|------|------|
| 통합 검색 웹 UI | 기존 오픈소스는 CLI/데스크톱/인벤토리 관리에 초점 |
| 다중 공급업체 비교 뷰 | 동일 부품을 여러 공급업체에서 비교하는 웹 인터페이스 부재 |
| 부품 탐색/선택 UX | BOM 관리가 아닌 "탐색 및 선택"에 초점을 맞춘 도구 부재 |
| 디바이스마트 연동 | 국내 공급업체를 지원하는 기존 프로젝트 없음 |

---

## 개발 로드맵

### Phase 0: 조사 및 분석 (완료)
- [x] 각 공급업체 사이트 데이터 구조 조사
- [x] API 가용성 및 제약사항 확인
- [x] 관련 GitHub 오픈소스 프로젝트 조사
- [x] 활용 가능한 리소스 정리
- [ ] 통합 데이터 모델 설계
- [ ] 기술 스택 결정
- [ ] 시스템 아키텍처 설계

### Phase 1: MVP - JLCPCB/LCSC 단일 소스
- [ ] 백엔드 기본 구조 구축
- [ ] JLCPCB/LCSC 데이터 수집 및 저장
- [ ] 카테고리 탐색 구현
- [ ] 키워드 검색 구현
- [ ] 파라미터 필터 구현 (저항, 커패시터 등 주요 카테고리)
- [ ] 부품 상세 페이지
- [ ] 부품 선택 리스트 관리
- [ ] 프론트엔드 기본 UI

### Phase 2: DigiKey 연동
- [ ] OAuth 2.0 인증 구현
- [ ] DigiKey 검색/상세 조회 연동
- [ ] 통합 검색 결과 병합
- [ ] 공급업체 간 가격/재고 비교 뷰

### Phase 3: Mouser + element14 연동
- [ ] Mouser API 연동
- [ ] element14 API 연동
- [ ] MPN 기반 크로스 레퍼런스

### Phase 4: 디바이스마트 연동
- [ ] 데이터 수집 방법 결정 (스크래핑 또는 제휴)
- [ ] 연동 구현
- [ ] 국내 가격/배송 정보 통합

### Phase 5: 고도화
- [ ] 사용자 인증 시스템
- [ ] BOM 관리 기능
- [ ] 가격 변동 알림
- [ ] 대체품 추천
- [ ] 가격 히스토리/추이 차트

---

## 참고 프로젝트

이 프로젝트를 만들기 위해 참고하는 주요 오픈소스 프로젝트들입니다.

### 데이터 소스 / 검색 엔진

| 프로젝트 | 설명 | 핵심 참고 포인트 |
|---------|------|----------------|
| [tscircuit/jlcsearch](https://github.com/tscircuit/jlcsearch) | JLCPCB 부품 검색 엔진 + API | 데이터 파이프라인, 최적화된 SQLite, API 설계 |
| [yaqwsx/jlcparts](https://github.com/yaqwsx/jlcparts) | JLCPCB 전체 부품 카탈로그 | 데이터 소스, 속성 정규화, IndexedDB 기반 로컬 검색 |
| [CDFER/jlcpcb-parts-database](https://github.com/CDFER/jlcpcb-parts-database) | JLCPCB 부품 DB 경량화 | GitHub Actions 자동 업데이트, FTS 인덱스 |

### 인벤토리 관리 / 다중 공급업체 통합

| 프로젝트 | 설명 | 핵심 참고 포인트 |
|---------|------|----------------|
| [Part-DB/Part-DB-server](https://github.com/Part-DB/Part-DB-symfony) | 전자부품 인벤토리 관리 시스템 | 다중 공급업체 연동, 파라미터 검색, 카테고리 구조 |
| [inventree/InvenTree](https://github.com/inventree/inventree) | 오픈소스 재고 관리 | REST API 설계, Supplier Part 모델, 플러그인 구조 |
| [30350n/inventree_part_import](https://github.com/30350n/inventree_part_import) | 다중 공급업체 부품 임포트 CLI | 카테고리/파라미터 매핑 YAML 구조 |
| [sparkmicro/Ki-nTree](https://github.com/sparkmicro/Ki-nTree) | KiCad + InvenTree 부품 생성 | 다중 API 통합 아키텍처, 공급업체별 설정 |

### 가격 비교 / 통합 API

| 프로젝트 | 설명 | 핵심 참고 포인트 |
|---------|------|----------------|
| [hildogjr/KiCost](https://github.com/hildogjr/KiCost) | BOM 가격 비교 스프레드시트 | 각 유통업체 접근 코드, 가격 비교 로직 |
| [PartFuse](https://github.com/PartFuse/partfuse-examples) | 통합 가격/재고 API (유료) | 통합 API 인터페이스 설계 |
| [mageoch/JLCPCB-MCP-Server](https://github.com/mageoch/LCSC-MCP-Server) | JLCPCB API MCP 서버 | 공식 API 사용법, SQLite+FTS5, 파라미터 파싱 |

### API 래퍼 라이브러리

| 프로젝트 | 공급업체 |
|---------|---------|
| [peeter123/digikey-api](https://github.com/peeter123/digikey-api) | DigiKey |
| [sparkmicro/mouser-api](https://github.com/sparkmicro/mouser-api) | Mouser |
| [pyfarnell](https://pyfarnell.readthedocs.io/) | element14/Farnell |

---

## API 문서 링크

| 공급업체 | URL | 비고 |
|---------|-----|------|
| LCSC (비공식) | [Gist](https://gist.github.com/Bouni/fabcc1965036d4816c3d48e2dbf6b169) | 인증 불필요, 비공식 |
| JLCPCB | https://api.jlcpcb.com/ | 개발자 포털에서 키 발급 |
| Mouser | https://www.mouser.com/api-hub/ | API Key 무료 발급 |
| DigiKey | https://developer.digikey.com/ | OAuth 2.0, 일 1000건 |
| element14 | https://partner.element14.com/ | API Key 무료 발급 |
| Nexar/Octopart | https://nexar.com/api | GraphQL, 7000만+ 부품 |
| jlcsearch | https://docs.tscircuit.com/web-apis/jlcsearch-api | 무료, URL에 .json 추가 |

---

## 프로젝트 구조

```
Circuit/
├── README.md                          # 이 파일
├── 연구조사_전자부품_검색사이트.md          # 상세 조사 보고서
└── (추후 구현 코드)
```

---

## 기여

이 프로젝트는 현재 초기 단계입니다. 관심 있는 분은 Issue를 통해 의견을 나눠주세요.

## 라이선스

추후 결정 예정
