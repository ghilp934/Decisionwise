# OAS & Front‑End Demo Projects – Consolidated Best Practices v1.1 (2026)
이 문서는 2026‑02‑08을 기준으로 여러 데모/실전 프로젝트에서 도출한 베스트 프랙티스를 통합한 것입니다. 사용된 원본 자료는 OAS API 명세, 백엔드/프론트엔드 베스트 프랙티스 문서, 코드 템플릿, 프로젝트 체크리스트, 재사용 가능한 패턴, Claude Memory Export v2 등입니다.  중복되거나 시대에 뒤처진 항목은 제거하고 최신 기술 스택에 맞게 반영했습니다. Node 18은 2025‑03‑27에 EOL을 맞았기 때문에 LTS인 Node 24 이상을 사용하고【648659534715231†L64-L72】, React 19로 업그레이드해야 합니다【488925780167648†L61-L88】.


## 🧾 변경 이력

- **v1.1 (2026‑02‑10)**: DPP 프로토타입(v0.1) 포스트‑오딧에서 도출한 10개 Best Practices + 데모 안정성(하드‑페일 정의/회귀 테스트) + 운영 아티팩트(Audit Ledger/Decision Log) 루틴을 통합했습니다.
- **v1.0 (2026‑02‑08)**: 초기 통합본 작성.

## 🏗️ 프로젝트 설정 & 환경 관리

**버전 & 스택**

- **Node.js**: LTS 버전(현재 v24 Krypton) 이상을 사용합니다. Node 18 Hydrogen은 2025‑03‑27에 End‑of‑Life이므로 더 이상 사용하지 않습니다【648659534715231†L64-L72】.
- **Python**: 백엔드에서는 Python 3.11+ 대신 최신 LTS 버전(Python 3.12+)을 권장합니다.
- **FastAPI**: 0.115+에서 0.128+로 업데이트하여 최신 기능과 보안 패치를 적용합니다.
- **React**: React 19+로 개발합니다. React 19에서 새로운 JSX 변환과 에러 처리 방식이 도입되었으며【488925780167648†L61-L88】, 이전 버전의 PropTypes/defaultProps API는 제거되었습니다【488925780167648†L175-L184】. 타입 안전성을 위해 TypeScript를 채택합니다.
- **Vite**: Vite 8+ 또는 최신 안정 버전을 사용합니다. (원본 문서에서는 Vite 7을 사용했으나 업그레이드를 권장.)
- **Tailwind CSS**: 최신 3.x 버전 사용. PostCSS 기반 설정 파일은 유지합니다.
- **Database**: PostgreSQL 15+ (또는 최신 LTS). SQLAlchemy 2.x 사용.

**환경 설정**

- **코드 스타일 도구**: ESLint Flat Config, Prettier, EditorConfig를 설정하여 일관된 코드 스타일을 유지합니다. 강화된 규칙(미사용 변수 금지, eval 금지, React Hooks 규칙 등)을 포함합니다.
- **환경 변수**: `.env.example` 파일에 필수 변수와 설명, 예시를 제공하고 `.env`를 `.gitignore`에 추가합니다. `env.ts/js` 모듈에서 값 존재 여부와 형식 검증을 수행하여 서버/클라이언트가 시작될 때 필수 변수가 누락되지 않도록 합니다.
- **패키지 스크립트**: `npm run dev`, `build`, `lint`, `format`, `test` 등 기본 스크립트를 정의하고 동시에 프론트엔드/백엔드를 실행하려면 `concurrently`를 사용할 수 있습니다.
- **Git 초기화**: 첫 커밋 전에 `.gitignore` (로그, OS 파일, 환경 변수, IDE 설정 등)와 `.gitattributes`를 설정하고 장기적으로 Git hooks로 자동 린트 및 포맷을 수행합니다.
- **Docker & 배포**: 프로덕션용 `docker-compose.production.yml`에서는 이미지 버전 고정, 환경 변수 주입, 볼륨 권한 제한, 포트 노출 최소화, 리소스 제한(`mem_limit`, `cpu_shares`), Health Check 설정 등을 적용합니다.  

**프로젝트 초기 체크리스트**

프로젝트 시작 시 다음을 확인합니다.

| 단계 | 주요 항목 |
| --- | --- |
| **Day 1 – 코드 품질 도구** | ESLint/Prettier/EditorConfig 설정, 첫 커밋, Git hook 구성 |
| **환경 변수 관리** | `.env` & `.env.example` 작성, 환경 검증 코드, 필수 변수 테스트 |
| **개발 스크립트** | 기본 NPM 스크립트 정의, 백엔드 스크립트(`start.py`, `check_server.py`) 추가 |
| **문서화** | `README.md` 초안, API 명세(OpenAPI/Swagger) 링크, 주요 컴포넌트 JSDoc 작성 |
| **역할 분담** | 사용자와 AI 에이전트의 역할을 명확히 정의(코드 작성 vs UI 검수 등) |
| **포기 기준** | 환경 제약(예: Windows EISDIR 오류) 발견 시 빠른 방향 전환; 동일한 접근을 세 번 이상 반복하지 않음 |

## 🧱 아키텍처 패턴

**계층형 아키텍처 (Layered Architecture)**

- 프레젠테이션(Presentation), 애플리케이션(Application), 도메인(Domain), 인프라(Infrastructure) 네 개의 레이어로 구성합니다. 상위 레이어는 하위 레이어에만 의존하고 반대로 의존해서는 안 됩니다. 도메인 레이어는 다른 레이어를 모릅니다.  
- 엔드포인트는 인증과 요청/응답 검증만 수행하고 비즈니스 로직은 애플리케이션 레이어의 Use Case/Service 클래스에 위임합니다.  
- 인프라 레이어는 DB/스토리지/외부 API 접근 로직을 담당하며 인터페이스를 통해 추상화합니다.  

**추상화 패턴**

- **Factory 패턴**: 설정에 따라 런타임에 구현체를 결정합니다(예: S3 vs 로컬 스토리지). 테스트 시 팩토리를 패치하여 Mock을 주입합니다.  
- **Adapter 패턴**: PaddleOCR 같은 외부 라이브러리를 내부 표준 인터페이스로 감싸서 교체 가능성을 확보합니다.  
- **Repository 패턴**: 데이터 접근 로직을 비즈니스 로직에서 분리하고 SQLAlchemy 세션을 통해 CRUD 함수를 제공합니다. 복잡한 쿼리를 재사용하고 테스트에서는 인메모리 DB 또는 Mock Repository로 대체할 수 있습니다.  
- **의존성 주입(DI)**: 서비스/도메인 클래스의 생성자에 의존성을 주입하여 테스트 가능성을 높입니다. Python에서는 FastAPI의 `Depends` 또는 Pydantic Settings/Dependency Injector를 사용할 수 있습니다.  

**상태 머신 & 비동기 처리**

- OCR 작업이나 비동기 워크플로는 **상태 머신**으로 설계합니다. 작업 상태(QUEUED → RUNNING → COMPLETED → FAILED)를 Enum으로 정의하고, 전이(transition)를 명시적으로 처리합니다.  
- 백엔드는 Celery 4.x/5.x 대신 최신 **Celery 6+**를 사용합니다. 태스크에는 시간 제한, 재시도 정책, 멱등성 키를 설정하고, 작업 ID를 `ulid`로 생성하여 추적성을 확보합니다.  
- AsyncIO를 사용하는 경우 세션/커넥션 풀을 컨텍스트 매니저와 함께 관리하고, 동기식 코드와 섞어 쓰지 않도록 주의합니다.  

## 🧠 설계 원칙 & 코드 품질

**SOLID 원칙**

- **단일 책임 원칙(SRP)**: 클래스/모듈은 하나의 책임만 수행합니다. OCR 서비스에서는 전처리, 텍스트 추출, DB 저장, 알림 전송, 보고서 생성 등을 각각 별도 클래스로 분리합니다.  
- **개방/폐쇄 원칙(OCP)**: 기존 코드를 수정하지 않고 기능을 확장할 수 있도록 인터페이스와 추상 클래스를 설계합니다. 예를 들어 저장소 타입을 추가할 때 팩토리 함수만 수정합니다.  
- **의존성 역전 원칙(DIP)**: 상위 모듈이 하위 모듈의 구현에 의존하지 않도록 인터페이스 추상화를 도입합니다. FastAPI 엔드포인트는 구체적인 저장소 구현을 알지 못합니다.  

**불변성 & 타입 안전성**

- Python에서는 데이터 클래스와 Pydantic BaseModel을 사용하여 불변성(`frozen=True`)을 유지하고 타입 힌트를 적극적으로 사용합니다. Pydantic v2의 `model_validate`와 `model_dump`를 활용해 타입 검증과 직렬화를 명확히 합니다.  
- 프런트엔드에서는 TypeScript를 사용하여 props와 상태의 타입을 정의하고, `any` 타입 사용을 지양합니다.  

**코드 스타일 & 모듈 관리**

- **상수화**: 매직 문자열과 숫자는 `constants.ts`/`settings.py`에 중앙화합니다.  
- **모듈 exports**: React 컴포넌트는 기본이 아닌 **named export**를 사용하고, 각 디렉터리에 `index.ts`를 두어 내부 API를 명확히 노출합니다.  
- **파일 구조**: 기능별 모듈로 디렉터리를 구성하고, 동일한 역할을 가진 파일끼리 묶습니다(`api/`, `services/`, `components/`, `pages/`).  

**성능 최적화**

- React 컴포넌트는 불필요한 리렌더링을 방지하기 위해 `memo`, `useCallback`, `useMemo`를 적절히 사용합니다. 비용이 큰 연산은 memoization을 적용하고, 상태 변화에 따라 의존성 배열을 정확히 지정합니다.  
- 프런트엔드 렌더링을 최적화하기 위해 requestAnimationFrame을 사용하여 DOM 업데이트를 배치하고, 이벤트 위임을 통해 이벤트 리스너 수를 줄입니다.  
- React 상태는 **최상위 레벨**(예: App)에서 관리하여 페이지 간에 공유되는 데이터가 중복 선언되지 않도록 합니다.  

## 🔐 보안 & 멀티테넌시

**Security‑First Design**

- 프로젝트 시작 시 보안 요구사항을 **GO/NO‑GO Gate** 형태로 명시하고 각 Gate를 자동화 테스트로 검증합니다. OAS 프로젝트에서는 인증, 테넌트 격리, 스토리지 경로 검증, 업로드 제한, CSP 헤더, SSRF 방지, 민감 정보 관리 등 7개의 Gate를 정의했습니다.  
- **다층 보안(Defense in Depth)**을 적용해 API 레이어, 서비스/비즈니스 레이어, 스토리지, DB 레이어 등 모든 계층에서 독립적으로 테넌트 ID와 권한을 검증합니다. 단일 계층의 취약점이 전체 시스템을 무너뜨리지 않도록 합니다.  
- **환경별 보안 설정**을 구분합니다. 개발 환경에서는 CORS를 모두 허용할 수 있지만, 프로덕션에서는 특정 도메인만 허용하고 CSP/SSRF 보호를 강제합니다. `.env.development`와 `.env.production`을 분리하고 `validate_env.py`로 배포 전 설정을 검증합니다.  
- **API 키/토큰 관리**: 모든 민감 정보는 AWS Secrets Manager, HashiCorp Vault 또는 Kubernetes Secrets로 관리하고 로테이션 자동화를 구축합니다.  

**보안 체크리스트** (요약)

- 인증 및 API 키 유효성 검사를 모든 엔드포인트에서 수행 (401 Unauthorized).
- 테넌트 격리: API, Storage, DB 모든 계층에서 `tenant_id` 기반으로 필터링합니다.
- 경로 트래버설 방지: 업로드/다운로드 경로에 `../` 또는 `..\`가 포함되지 않도록 검증합니다.
- 파일 업로드 제한: MIME 타입과 확장자를 모두 검증하고, 이미지 10 MB, PDF 50 MB 등 크기 제한을 설정합니다.
- **Content Security Policy**: `default-src 'self'`, `frame-src`/`frame-ancestors`/`form-action`/`base-uri`/`object-src` 등 지시문을 설정합니다.
- **SSRF 방지**: 외부 URL 필드를 받을 때 사설 IP와 로컬호스트(127.0.0.1, 10.0.0.0/8 등)를 차단하고 Pydantic의 `HttpUrl` 타입을 사용합니다.
- 민감 파일 커밋 금지: `.gitignore`에 `.env`, `logs/`, `.pytest_cache/` 등을 포함합니다.

## 📦 데이터 모델링 & 검증

- **Pydantic Models**: 요청/응답 스키마를 Pydantic v2 BaseModel으로 정의하고, 필드 타입/길이/형식을 명시합니다. `model_config`에서 `validate_assignment=True`로 설정하여 런타임 데이터 수정도 검증합니다.  
- **SQLAlchemy Models**: ORM 모델은 `DeclarativeBase`를 사용하여 명확한 타입 주석을 제공하고, `__tablename__`과 인덱스/제약 조건을 명시합니다. 도메인 엔티티와 DB 테이블 간에 매핑 클래스가 분리되어야 하는 경우 Repository 패턴을 사용합니다.  
- **Validation Utilities**: 프런트엔드에서 `responseValidator.js`처럼 응답 객체의 필수 필드 존재 여부를 검증하는 도우미를 만들고, 오류 메시지에 컨텍스트를 포함합니다.

## 🪙 비동기 & 상태 관리

- 백엔드 작업은 Celery 타스크 또는 `asyncio` Task로 실행하고, 작업 ID와 상태를 DB에 기록하여 폴링 또는 WebSocket 통신을 통해 프런트엔드에 전달합니다.  
- 멱등성: 동일한 요청에 대해 중복 작업이 생성되지 않도록 멱등성 키를 사용하며, Celery 태스크의 `retry` 옵션과 `acks_late=True`를 적절히 설정합니다.  
- 비동기 코드에서 SQLAlchemy 세션 등 컨텍스트를 적절히 닫아 메모리 누수를 방지합니다.  

## 🚨 에러 처리 & 로깅

- **Exception Hierarchy**: 사용자 입력 오류, 비즈니스 로직 오류, 외부 시스템 오류 등 서로 다른 예외 클래스를 정의하여 정확한 HTTP 상태 코드와 오류 메시지를 반환합니다.  
- **Graceful Degradation**: 외부 API 오류 시 기본값 제공 또는 큐잉 방식으로 사용자의 작업을 차단하지 않고 복구 가능한 상태로 처리합니다.  
- **Structured Logging**: 로그는 JSON 형식으로 출력하고, 서비스 이름/타임스탬프/요청 ID/테넌트 ID/레벨/메시지/추가 데이터를 포함합니다.  

## 🧪 테스트 전략

- **테스트 피라미드**: 단위 테스트가 대부분(90% 이상)을 차지하며 빠른 피드백을 제공합니다. 통합 테스트는 적절한 수의 경로를 검증하고, E2E 테스트는 핵심 사용자 흐름만 다룹니다.  
- **Test‑Driven Development (TDD)**: 기능 개발 전에 테스트 스케치를 작성하고, 실패하는 테스트를 기반으로 최소한의 코드를 작성한 뒤 리팩터링합니다. TDD는 초기 비용이 있지만 장기적으로 시간을 절약합니다.  
- **보안 테스트**: 인증 실패, 테넌트 격리 위반, 경로 트래버설, 업로드 제한, SSRF 차단 등 각 보안 Gate를 테스트합니다.  
- **환경 검증 자동화**: `validate_env.py`는 배포 전 환경 변수 값과 형식을 검증하며, CI 파이프라인에서 실행합니다.  

## 📈 프로젝트 품질 관리

- **Self‑Review 체크리스트**: 코드 작성 후 5분 동안 다음 항목을 점검합니다: 타입 정의, React 최적화(`memo`, `useMemo`, `useCallback`), 매직 넘버 제거, 파일 크기/컴포넌트 분리, 일관성(import 순서, 네이밍), 접근성(`aria-*`, role), 주석/슬롯 마킹.  
- **품질 점수**: 코드 품질/React 최적화/타입 안전성/일관성/잠재적 버그를 10점 만점으로 평가하고 평균 8점 이상을 목표로 합니다.  
- **메모리 관리**: 세션 시작·중요 결정·마일스톤 완료·세션 종료 시 기억해둬야 할 내용을 `MEMORY.md`에 즉시 기록하고 주기적으로 정리합니다. 불필요한 내용은 매일 제거하고 섹션을 주간 단위로 재구성합니다.  
- **토큰 및 시간 최적화**: 단순 작업에는 7단계 검수 과정을 생략하고, 문제 발생 시 3회 시도 후 포기/대안 제안을 합니다. Bash grep 명령어로 보안 취약점(`eval`, `innerHTML`)과 최적화 지표(React.memo 수, useEffect clean‑up 여부)를 빠르게 검증하고 결과만 보고합니다.  

## 🤝 협업 & 커뮤니케이션 프로토콜

- **작업 지시 템플릿**: 요청에는 작업 제목, 목표, 구현 범위(필수/선택), 핵심 포인트, 제외 사항, 검증 방법을 명시합니다. “MT‑22 구현해줘”처럼 애매한 지시는 금지합니다.
- **작업 시작 전 체크리스트**: 기존 코드 패턴 2개 이상 살펴보기, Mock 데이터와 타입 정의 확인, 의존성 파악, 불명확한 부분 질문. 코드 작성 전에 질문하여 토큰을 절약합니다.  
- **Self‑Review 후 보고**: 완료 보고에는 파일 목록, 구현 내용 요약, 확인 방법, 다음 작업 제안을 포함합니다.  
- **에러 보고**: 위치, 증상, 콘솔 메시지, 재현 방법, 예상 원인을 상세히 작성하여 AI 에이전트가 빠르게 대응할 수 있도록 합니다.  
- **포기 기준**: 환경 제약이나 외부 도구 오류를 발견하면 1~2회 시도 후 즉시 대안 제안을 합니다. 동일한 접근 방식을 3회 이상 반복하지 않습니다.  

## 🖥️ UI/UX & 접근성

- **접근성 체크리스트**: 아이콘 버튼에는 `aria-label`을 부여하고, 모달은 `role="dialog" aria-modal="true"`를 설정하여 ESC 키로 닫히도록 합니다. 터치 타겟은 최소 44×44 px, 광고 영역에는 `role="complementary"`와 `aria-label="Advertisement"`를 추가합니다.  
- **z-index 계층 관리**: UI 충돌을 방지하기 위해 5단계 z-index 시스템을 정의합니다 – 내부 요소(z‑10), 배지/라벨(z‑20), backdrop(z‑40), 헤더/사이드바(z‑50), 모달/라이트박스(z‑60).  
- **광고 구현**: 스톡 이미지/콘텐츠 플랫폼에서는 Banner(728×90 or 320×50), Inline(300×250), Modal(600×400), Native Ad 등 네 가지 광고 유형을 지원합니다. 모든 광고 링크는 `target="_blank"`와 `rel="noopener noreferrer"`를 사용하고, 광고 영역에는 `Sponsored` 배지를 표시합니다. Native Ad는 콘텐츠와 동일한 UI/UX를 유지하며 Fibonacci 기반 위치(3, 11, 19번째)를 권장합니다.  

## 🏷️ 도메인 특화 & 외부 고려사항

- **도메인 특화 필터**: 마켓플레이스/미디어 등 도메인에서는 “가격 낮은 순”같은 일반적인 정렬 대신 이미지 해상도, 색상, 종횡비 등의 특화 필터를 제공합니다.  
- **광고 보안**: 광고 프레임을 삽입할 때 CSP의 `frame-src`와 `frame-ancestors` 지시문을 설정하고, iframe 광고는 외부 도메인만 허용합니다.  
- **데모 vs 프로덕션 갭**: 데모에서 생략한 기능(로그인/결제 등)은 프로덕션 이전에 반드시 구현하고, 보안·테스트·문서·모니터링 체크리스트를 모두 충족해야 합니다.  


## 🧩 DPP 프로토타입(v0.1) 포스트‑오딧 추가분 (2026‑02‑10)

아래 항목은 **DPP 프론트엔드 프로토타입 v0.1**을 “데모‑레디(크래시/고착/무한로딩 제거)” 수준으로 끌어올리는 과정에서 고정된 규칙들입니다.  
특히 **결정론적 복구(새로고침/딥링크/다중탭)**, **폴링 레이스 방지**, **Storage 예외 방어**, **Secure Mode를 데이터 계약으로 잠금**, **악조건을 표준 회귀 테스트로 편입**이 핵심입니다.

### BP-01: JSON 기반 deep clone 금지 (특히 File/Date/Map)

- **Rule**: `JSON.stringify/parse`로 deep clone 하지 않습니다. (File/Date/Map 등 타입 손실/변형)
- **Preferred**: `structuredClone()`(가능한 환경) 또는 **타입별 명시적 복사**.
- **데모 범위 예외**: non‑JSON 타입이 포함될 수 있다면, **먼저 JSON‑safe 형태(메타)로 “정규화(normalize)”**한 뒤에만 JSON clone을 허용합니다.

체크리스트
- [ ] 상태/입력에 File/Date/Map/Set이 들어올 수 있는지 먼저 확인
- [ ] 필요 시 `normalize()`로 JSON‑safe로 변환(예: File → {name,size,type})
- [ ] 가능한 환경이면 `structuredClone()` 사용(지원 범위 확인 필요)

### BP-02: React state 불변성 — “변경은 새 객체로”

- **Rule**: React state를 직접 mutate 하지 않습니다. **수정은 항상 새 객체/새 배열로** 만듭니다.
- **Anti‑pattern**: `state.items.push()` / `state.obj.key = ...`
- **Pattern**: `setState(prev => ({ ...prev, items: [...prev.items, newItem] }))`

체크리스트
- [ ] “이 줄이 prev를 바꾸는가?”를 Self‑Review에서 항상 체크
- [ ] 배열/객체는 spread / map / filter 기반으로 갱신
- [ ] state 내부에 **참조 공유(shared reference)**가 남지 않게 설계

### BP-03: Mock 상태머신 — “타이머 의존” 대신 “결정론적 복구”

- **Rule**: Mock API 상태 전이가 `setTimeout`에만 의존하면, 새로고침/딥링크에서 RUNNING 고착이 발생합니다.  
  **created_at(생성 시각) 기반으로 상태를 재계산**해 “언제든 복구 가능”하게 만듭니다.
- **권장**: `getRun()` 호출 시마다 `elapsed = now - created_at`로 상태를 결정론적으로 계산.

체크리스트
- [ ] “F5(새로고침) during RUNNING”을 P0 테스트로 고정
- [ ] 상태 전이는 `computeStatusFromElapsed()` 같이 순수 함수로 분리
- [ ] “딥링크(직접 URL 입력) → 정상 복구”를 필수 조건으로 둠

### BP-04: 폴링 루프 4원칙

1. **inFlight guard**: 요청 중이면 다음 폴링을 스킵해 중복 요청을 방지
2. **terminal stop**: SUCCEEDED/FAILED 같은 terminal 상태면 폴링 중단
3. **visibility/bfcache 고려**: 탭/히스토리 복원에서 중복 interval이 생기지 않게 방어
4. **recover UX**: 네트워크 악조건(느림/오프라인)에서 “재시도 경로”를 제공

체크리스트
- [ ] `isFetching`(또는 AbortController)로 inFlight guard
- [ ] terminal 상태 전이 시 `clearInterval`/cleanup
- [ ] bfcache 복원 시 `pageshow`(persisted)에서 폴링 재시작/정리
- [ ] Slow 3G / Offline 토글에서 복구 버튼 또는 자동 재시도

### BP-05: 데모 앱의 “재진입 경로”는 필수

- **Rule**: 사용자는 언제든 새로고침/뒤로가기/직접 URL 입력으로 재진입합니다.  
  “현재 Run을 다시 찾을 수 있는 경로(딥링크/히스토리/대시보드)”가 없으면 데모가 깨집니다.
- **권장**: 최소 1개 재진입 경로를 **제품 요구사항으로 잠금**.

체크리스트
- [ ] “대시보드 → 최근 Run” 또는 “현재 Run 링크 복사” 등 1개 이상 제공
- [ ] Back/Forward 반복(D3)에서 폴링/상태가 안정적인지 확인

### BP-06: localStorage는 항상 실패할 수 있다

- **Rule**: Safari Private Mode, Quota 초과, 브라우저 정책으로 `localStorage`는 예외를 던질 수 있습니다.  
  따라서 모든 접근은 **try/catch**로 방어하고, 실패 시 **degrade(캐시 없음)**로 처리합니다.

체크리스트
- [ ] `getItem/setItem/removeItem` 전부 try/catch
- [ ] 실패 시 crash 금지(경고 로그 + null 반환)
- [ ] 데이터가 “필수”면 localStorage가 아니라 서버 저장(또는 IndexedDB)로 설계

### BP-07: “문서 = 계약” (Claim–Evidence 매핑)

- **Rule**: 데모/프로토타입에서도 문서를 “설명”이 아니라 **계약(Contract)**로 취급합니다.
- **Pattern**: 요구사항/주장(Claim) ↔ 근거/구현(Evidence) ↔ 테스트(Verification)를 1:1로 매핑.

체크리스트
- [ ] P0(하드‑페일) 정의를 문서에 먼저 고정
- [ ] “이 버그는 어떤 테스트로 다시 잡는가?”를 항상 기록
- [ ] 커밋/패치마다 “무엇이 왜 잠겼는지”를 Decision Log로 남김

### BP-08: Alert 금지, 에러 표면 통일

- **Rule**: `alert()`는 UX를 깨고 자동 테스트를 어렵게 합니다.  
  모든 피드백은 **inline message / toast** 등으로 통일합니다.
- **권장**: 중요도에 따라 (1) auto‑dismiss 3s, (2) 수동 닫기, (3) 블로킹 모달을 구분.

### BP-09: Secure Mode는 UI가 아니라 데이터 계약으로 잠금

- **Rule**: Secure Mode는 “화면에서 URL을 숨김”이 아니라  
  **(저장/로그/Run/Manifest 어디에도 URL이 남지 않는) 데이터 계약**으로 잠급니다.
- **권장**: 입력 스키마에서부터 URL 필드를 금지하거나, 저장 전 **redaction/guard**를 적용.

체크리스트
- [ ] Run/Manifest/Log에 URL 잔존 여부를 회귀 테스트로 고정
- [ ] Secure Mode에서는 외부 fetch/preview 등 기능을 명시적으로 disable

### BP-10: DevTools로 “악조건”을 표준 테스트로 만들기

- **Rule**: “현실 같은 실패”를 **수동 우연**에 맡기지 말고, DevTools 설정으로 표준 테스트화합니다.
- **필수 시나리오**: Slow 3G, Offline, CPU throttling, cache disable, Back/Forward 반복, multi‑tab.

체크리스트
- [ ] Slow 3G에서 무한 로딩 없이 복구 경로 제공
- [ ] Offline→Online 전환에서 자동/수동 복구
- [ ] Back/Forward 반복에서 폴링 중복/레이스 0

### 데모 안정성: HARD FAIL 정의 + 회귀 테스트(D1–D10)

**HARD FAIL (데모 블로커) 정의**
- HF1: 흰 화면 / Unhandled error crash
- HF2: 무한 로딩 / 무한 스피너(>10s)
- HF3: 상태(QUEUED/RUNNING) 영구 고착
- HF4: Secure Mode인데 URL이 Run/Manifest/Log에 잔존

**회귀 테스트 예시(DPP)**
- D1: RUNNING 중 새로고침(F5)
- D3: Back/Forward 3회(폴링 중복/레이스)
- D7: Slow 3G
- D8: Offline→Online 토글
- D9: Safari Private Mode
- D10: localStorage quota exceeded

> 운영 팁: “하드‑페일 정의 → 재현 테스트 → 패치 위치 → 최종 PASS”를 **Ledger 1장**으로 고정하면, 다음 프로젝트에서도 속도가 급격히 빨라집니다.

### 운영 아티팩트(권장): Audit Feedback Ledger + Decision Log

- **Audit Feedback Ledger**: 이슈/Severity/상태/패치 위치/재현 테스트/근거를 표로 누적합니다.  
- **Decision Log(DEC)**: “Context → Decision → Consequence → Revisit Trigger” 포맷으로 **결정론을 잠금**합니다.

권장 운영 규칙
- [ ] P0(하드‑페일)부터 제거하고, P1(UX) → P2(문서) 순으로 진행
- [ ] “부분 해결(△)”은 반드시 OPEN item으로 올려 v0.2 마일스톤에 배치
- [ ] 회귀 테스트 세트는 줄이지 말고, 프로젝트가 바뀌면 **추가만** 허용


## ✅ 체크리스트 요약

아래 체크리스트는 프로젝트 라이프사이클의 각 단계에서 확인해야 할 핵심 항목입니다. 필요에 따라 개인/팀의 상황에 맞게 수정하여 사용하세요.

### 프로젝트 시작 시 (Day 1)

- [ ] LTS 버전(Node 24+/React 19+ 등)으로 환경 구성 완료【648659534715231†L64-L72】【488925780167648†L61-L88】
- [ ] ESLint/Prettier/EditorConfig 설정 및 첫 커밋
- [ ] `.env` 관리(예시 포함)와 환경 변수 검증 스크립트 작성
- [ ] README 초안 및 API 명세 준비
- [ ] 역할 분담과 포기 기준 정의

### 개발 중 (Daily)

- [ ] 작업 지시 템플릿과 Self‑Review 체크리스트 사용
- [ ] Mock 데이터/타입 정의 확인 후 코드 작성
- [ ] DevTools 악조건 회귀 테스트(예: Slow 3G/Offline/Back‑Forward)를 주 1회 이상 수행
- [ ] 폴링/타이머/스토리지 등 “데모 킬러” 경로는 inFlight/cleanup/try‑catch로 방어
- [ ] 보안 Gate 및 테스트 피라미드 유지
- [ ] Memory 파일에 중요한 결정 기록 및 정리

### 배포 전 (Pre‑Deployment)

- [ ] ESLint/Prettier 에러 0개, console.log 제거
- [ ] API 키 등 민감 정보가 노출되지 않는지 확인
- [ ] Lighthouse 점수(80 점 이상) 및 번들 크기(500 KB 이하) 확인
- [ ] Runbook/Deployment Checklists 문서화 및 검증
- [ ] Blue‑Green 또는 롤링 배포 계획 수립

### 배포 후 (Post‑Deployment)

- [ ] 모니터링 도구(Sentry, Web Vitals, Prometheus 등) 설정 및 알림 확인
- [ ] 로그/메트릭을 분석하여 병목 및 오류를 식별
- [ ] 사용자 피드백 수집 후 기능 개선 또는 버그 수정 계획 수립
- [ ] 기술 부채 목록을 업데이트하고 우선순위를 지정

---

**마지막 업데이트:** 2026‑02‑10 (v1.1)

본 문서는 살아있는 문서입니다. 다음 프로젝트에서 새로운 교훈이 발견되면 항목을 추가하거나 수정하세요. 품질과 효율의 균형을 유지하며 지속적으로 발전시키는 것이 중요합니다.