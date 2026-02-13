# Claude Code 팁(해커톤 우승자 ZIP + Advent of Claude 2025) 적용 메모 v0.1

- 작성일: 2026-02-10 00:00 KST
- 목적: **공통 헌장 / CONSOLIDATED BEST PRACTICES / FE 기술명세 템플릿**을 *나중에* 버전업할 때, 이번에 확인한 자료에서 “재사용 가능한 원칙”만 추출해 안전하게 이식하기 위한 **적용용 메모(스크리닝 완료본)**

---

## 0) 입력 자료 인벤토리 & 라이선스/사용성 게이트

### A. 해커톤 우승자 팁 ZIP (claude-code-tips-main.zip)
- 라이선스 상태: **All Rights Reserved** (권리 보유자 허락 없이 복제/배포/파생 저작물 작성 리스크 큼)
- 본 메모에서의 처리 원칙(보수적):
  1) **문구/코드/구조를 그대로 옮기지 않는다.**
  2) “아이디어/원리”만 추상화해 **클린룸 방식으로 재작성**한다.
  3) 향후 실제 문서 버전업 시에도 *동일 원칙 고정* (필요 시 권리자에게 별도 사용 허락/라이선스 확보)

### B. 웹 아티클: Advent of Claude 2025 (adocomplete.com)
- 저작권: 일반 웹 콘텐츠로서 통상 **All Rights Reserved** 가정(명시 라이선스 없음)
- 본 메모에서의 처리 원칙:
  - **짧은 인용은 피하고**, 개념만 요약/재구성(표현·구성은 독자적으로 작성)

### C. 1차(공식) 참고: Anthropic Claude Code 문서/엔지니어링 글
- 목적: 기능/옵션/포맷을 “정확하게” 반영하기 위한 **사실 확인용 1차 소스**
- 본 메모에 반영한 항목: hooks, sandboxing, permissions/allowlist, /init(및 --init), CLAUDE.md 운용 등

---

## 1) 법/규정/윤리(2026-02-10 KST 기준) 보수 스크리닝 결과

### 1-1. AI 생성물/광고 투명성(표시·고지) — “기본 ON” 설계 권장
- 한국: 「인공지능기본법」이 2026-01-22 시행되며, 정부 발표/정책 뉴스에서 **AI 생성물 워터마크/표시 등 투명성 장치**를 핵심 안전장치로 강조하는 흐름(세부 요건은 하위 규정/가이드 재확인 필요)
- 해외: EU는 AI Act 적용 일정에 따라 **AI 생성/조작 콘텐츠 투명성 의무**가 단계적으로 강화(특히 2026년 8월 전후가 주요 분기점)

> 결론(문서 반영 원칙):  
> “대외 공개 가능한 산출물(문서/이미지/영상/광고)”에는 **AI 활용 고지/표시 슬롯**을 템플릿 기본값으로 두고, 프로젝트별로 끌 수 없게(또는 ‘승인 필요’) 잠그는 방향이 안전함.

### 1-2. 개인정보(대한민국 PIPA & 전송요구권 확대) — “데이터 최소화 + 보관기간 짧게”
- PIPC(개인정보보호위원회) 발표에 따르면 **본인전송요구권(데이터 이동권) 적용 범위 확대**가 전송요구권(마이데이터) 확대를 위한 시행령 개정이 진행 중이며, 적용 범위·일정은 **공식 공지/고시 기준으로 재확인**이 필요
- 개발/운영 문서에는 “입력 데이터 최소화, 로그는 메타/해시 중심, 자동 삭제, 고객 데이터의 외부 LLM 전송 통제(또는 동의/위탁/국외이전 플로우 분리)”를 **기본 정책으로 명시**하는 게 안전함.

### 1-3. 저작권/라이선스(콘텐츠 윤리) — “외부 프롬프트/팁은 원문 이식 금지”
- 특히 All Rights Reserved 자료는 **문구/구조/코드**를 그대로 옮기는 순간 분쟁 리스크가 커짐.
- 따라서 문서 버전업 프로세스에 **License Gate(라이선스 체크) + Clean-room Drafting(독자 작성) + Diff Similarity Spot-check(유사표현 점검)**를 포함시키는 것을 권장.

---

## 2) “안전하게 재사용 가능한” 핵심 원칙 묶음(스크리닝 통과)

아래는 ZIP/아티클에서 관찰된 흐름을 **개념 수준으로 재구성**한 것들이다. (표현·구성은 독자 작성)

### 2-1. CLAUDE.md를 “프로젝트 운영체제”로 쓰는 원칙
- 목적: 매 세션마다 반복되는 규칙/명령/주의사항을 **지속 컨텍스트**로 고정
- 운용:
  - `/init` 또는 `--init`로 초기 골격을 만든 뒤, 실제 시행착오를 통해 **짧게·강하게** 다듬는다.
  - “항상 적용되는 것만” 남기고, 상황 의존 규칙은 skills로 분리한다.
- 위험/가드:
  - 너무 길어지면 무시될 확률이 커지므로 “삭제했을 때 실제 오류가 늘어나는 문장만 남긴다” 규칙을 둔다.

### 2-2. 권한/도구 통제는 “allowlist + sandbox 우선”
- 반복 승인 피로를 줄이려면:
  1) 자주 쓰는 안전 명령을 allowlist로 먼저 줄이고
  2) 그 다음 sandbox로 **OS 레벨 격리**를 건다.
- `--dangerously-skip-permissions`류의 전면 우회는:
  - “인터넷 차단/격리된 샌드박스 + 짧은 작업(예: lint 자동수정)” 같은 **극히 제한된 워크플로우**에서만 허용하는 것이 안전하다.

### 2-3. hooks로 “헌장/규칙”을 결정론적으로 강제
- LLM의 “선택”에 맡기지 않고, 특정 이벤트에서 **항상 실행**되게 만들 수 있다.
- 추천되는 훅 활용(예시 레벨):
  - PreToolUse: 파괴적 명령, 비승인 도메인 접속, 민감 파일 접근 차단
  - PostToolUse(Edit/Write): 포맷터/린터/타입체커 자동 실행
  - Stop/Notification: 사용자 확인 필요 시 알림(터미널 대기 최소화)
- hooks는 `.claude/settings.json`(프로젝트 공유)와 `~/.claude/settings.json`(개인) 범위를 분리한다.

### 2-4. “검증 가능한 루프”를 문서/워크플로우에 포함
- “탐색 → 계획 → 구현 → 검증” 루프를 고정하고,
- 검증은 사람이 아니라 **명령/테스트/린트/체크리스트**로 수행되게 설계한다.
- 기술명세에는 “검증 명령(예: test/lint/typecheck), 성공 기준, 실패 시 롤백/리트라이 규칙”을 **Acceptance Criteria**에 연결해 둔다.

### 2-5. 컨텍스트 관리(세션 지속/압축/재개)는 “보안/프라이버시 우선”
- 재개/지속 기능은 생산성에 유리하지만, 다음을 문서로 잠근다:
  - 세션에 비밀값을 남기지 않기(토큰/키/PII)
  - export/로그 공유 전 **자동 마스킹/비식별화**
  - 고객 데이터가 섞인 세션은 기본적으로 지속 저장 금지(또는 보관기간 극단적으로 짧게)

---

## 3) 문서별 “적용 위치” 제안(나중에 버전업할 때 복붙 가능한 수준)

> 표기 규칙:  
> - [ADOPT] 지금도 바로 넣어도 되는 보수적 항목  
> - [ADOPT+GUARD] 넣되 가드/제한을 함께 넣어야 안전한 항목  
> - [DEFER] 시기상조/증거 부족/운영 준비 부족  
> - [REJECT] 현재 기준에서 위험이 더 큰 항목

### 3-1. 공통 헌장(Common Charter) 버전업 시
- [ADOPT] License Gate: 외부 자료(프롬프트/코드/가이드) 유입 시 라이선스 확인 → All Rights Reserved는 “아이디어만” 허용
- [ADOPT] Tool/Permission Gate: allowlist 우선 + sandbox 우선(전면 우회 금지)
- [ADOPT] Hooks-First: 헌장 조항 중 “반드시 지켜야 하는 것”은 hooks로 강제(사람/LLM 기억에 의존 금지)
- [ADOPT+GUARD] Session/Export Gate: 대화 export/로그 공유 전 자동 마스킹(PII/토큰) + 공유 승인 절차
- [DEFER] 고도 자동화(에이전트 팀/원격 세션/브라우저 자동화)는 보안/개인정보 설계가 완성된 뒤로 미룸

### 3-2. CONSOLIDATED BEST PRACTICES 버전업 시
- [ADOPT] “Claude Code 운영” 섹션 신설(또는 확장)
  - CLAUDE.md 운영 규칙(짧게/강하게, 상황별 skills 분리)
  - hooks 패턴(PreToolUse 차단 / PostToolUse 포맷/린트)
  - allowlist/sandbox 기본값
- [ADOPT] “검증 루프” 항목 강화
  - 모든 작업은 “검증 명령”을 붙여서 끝내기(사람이 눈으로만 확인 금지)
- [ADOPT+GUARD] “생성물 표시/AI 고지” 운영 규칙(대외 산출물 템플릿에 기본 슬롯)
- [DEFER] 외부 플러그인/서드파티 MCP 서버는 “화이트리스트 + 보안 검증 루틴” 마련 후 확장

### 3-3. FE 기술명세 템플릿(v1.5 → vNext) 버전업 시
- [ADOPT] “LLM-보조 개발 프로토콜” 섹션(짧게) 추가:
  - `/init`로 CLAUDE.md 생성 후 프로젝트 규칙을 확정
  - 허용 도구/명령 allowlist 명시
  - hooks로 포맷/린트/타입체크 자동화
- [ADOPT] “Reproducibility” 강화:
  - 빌드/실행/테스트 명령, 환경 변수, 버전(런타임/패키지매니저) 고정
- [ADOPT+GUARD] “Data & Privacy” 절:
  - 로그/세션/에러리포트에 PII/토큰 금지
  - 보관기간/삭제 정책(기본 짧게)
- [ADOPT+GUARD] “AI 생성물 표시” 절:
  - UI/문서/광고 등 외부 노출 출력물에는 AI 사용 고지/표시 기본값
- [DEFER] 브라우저 자동화(Chrome 통합) 관련 요구사항은, 테스트 파이프라인과 보안 통제가 자리 잡은 뒤로

---

## 4) 향후 버전업 실행 플랜(클린룸 + 보수적 QA)

### 4-1. 트리거(권장)
- “동일한 실수/누락”이 3회 이상 반복되거나,
- CLAUDE.md/헌장/Best Practices의 항목이 20% 이상 “이미 현업에서 쓰이고 있음”이 확인될 때,
- 또는 hooks/allowlist/sandbox 관련 운영 규칙이 확정되었을 때

### 4-2. 절차(권장)
1) 후보 항목 수집(이번 메모의 [ADOPT]/[ADOPT+GUARD]만)
2) Clean-room Drafting: 외부 자료 원문을 열어둔 상태에서 문서 작성 금지(아이디어 노트만 보고 독자 작성)
3) 유사표현 점검: 문장/목차가 외부 자료와 지나치게 유사하면 재작성
4) 법/정책 점검: AI 표시·개인정보·광고/소비자 관련 조항은 최신 공지 재확인
5) Change Log + DEC/OPEN/ASMP 업데이트(추적성)

---

## 5) 참고 링크(사실 확인용)
- (공식) Claude Code Best Practices / CLAUDE.md, permissions, hooks, sandbox 등
- (공식) Hooks reference & hooks guide
- (공식) Sandboxing 아키텍처 설명(Anthropic Engineering)
- (정부/공공) 한국의 AI 관련 정책/개인정보 전송요구권 확대 공지
- (EU) AI Act 적용 타임라인(투명성 의무 관련)

(※ 링크는 버전업 실행 시점에 다시 최신 확인을 권장)

- Anthropic Claude Code docs (best practices, CLI reference, permissions, sandbox): https://code.claude.com/docs/en/best-practices / https://code.claude.com/docs/en/cli-reference / https://code.claude.com/docs/en/permissions
- Anthropic hooks: https://code.claude.com/docs/en/hooks / https://code.claude.com/docs/en/hooks-guide
- Anthropic engineering (sandboxing): https://www.anthropic.com/engineering/claude-code-sandboxing
- Advent of Claude 2025: https://adocomplete.com/advent-of-claude-2025/
- 대한민국(정부): AI 기본법 시행 및 AI 생성물 워터마크/표시 관련 정책 뉴스: https://www.korea.kr/news/policyNewsView.do?newsId=148958380
- 대한민국(정부): AI 허위·과장광고 대응(“AI 생성물 표시제” 등) 브리핑/보도자료: https://www.korea.kr/briefing/policyBriefingView.do?newsId=156734331 / https://www.korea.kr/briefing/pressReleaseView.do?newsId=156734376
- 대한민국(PIPC): 개인정보 전송요구권(본인전송요구권) 확대(시행령 개정) 관련 보도자료: https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS074&mCode=&nttId=11433
- EU: AI Act 적용 타임라인(2 Aug 2026 등) 및 Article 50 투명성 의무 관련 FAQ/뉴스: https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai / https://digital-strategy.ec.europa.eu/en/faqs/navigating-ai-act / https://digital-strategy.ec.europa.eu/en/news/commission-publishes-first-draft-code-practice-marking-and-labelling-ai-generated-content

