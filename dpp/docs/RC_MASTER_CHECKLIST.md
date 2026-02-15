# Decisionproof v0.4 RC MASTER CHECKLIST (SSOT)

Doc ID: DP-RC-MASTER-v0.4
Status: SPEC LOCK (SSOT)
Owner: Sung
Last Updated: 2026-02-15 (Asia/Seoul)

────────────────────────────────────────
0) 이 문서의 역할(SSOT)
- **"RC를 통과했다"를 판단하는 단 하나의 체크리스트(SSOT)**.
- 상세 기준은 아래 링크 문서에 위임하되, **PASS/FAIL 판정 및 실행 커맨드/증빙 위치는 본 문서만** 본다.
- 변경은 DEC(Decision Record)로만 수행한다.

참조(상세 스펙):
- /docs/RC_ACCEPTANCE.md (RC-0 ~ RC-8 상세)
- /apps/api/tests/test_rc*.py (RC 게이트 자동검증)

⚠️ NOTE (RC-9 포함 정책)
- RC_ACCEPTANCE.md는 RC-0~RC-8까지를 정의한다(기존 SPEC LOCK).
- **RC-9(Ops Pack Gate)**는 파일럿 직전 운영 패킷(ops/)을 잠그는 추가 게이트로, 본 문서에서 SSOT로 포함한다.
- RC_ACCEPTANCE에 RC-9를 병합하는 것은 후속 DEC로 처리한다.

────────────────────────────────────────
1) 5-STEP "지금 당장" 체크리스트

[1] RC_MASTER_CHECKLIST.md 확정(본 문서)  ← 지금
[2] RC 전체 자동게이트(테스트) 1회전 PASS
[3] RC Evidence Pack 수집/아카이브(1폴더)
[4] Staging Dry Run(최소 E2E 10케이스 + 롤백 리허설 1회)
[5] Paid Pilot Kickoff 준비(결제/정산/운영·지원 프로토콜 + 계약 문서 묶음)

────────────────────────────────────────
2) RC 게이트(자동검증) 요약

실행 기본값(로컬):
- 프로젝트 루트: dpp/
- Python: 3.12+
- 설치: `pip install -e '.[dev]'`

전체 RC 게이트 1회전(권장):
```bash
pytest -q \
  apps/api/tests/test_rc1_contract.py \
  apps/api/tests/test_rc2_error_format.py \
  apps/api/tests/test_rc3_rate_limit_headers.py \
  apps/api/tests/test_rc4_billing_invariants.py \
  apps/api/tests/test_rc5_gate.py \
  apps/api/tests/test_rc6_observability.py \
  apps/api/tests/test_rc7_otel_contract.py \
  apps/api/tests/test_rc8_release_packet_gate.py \
  apps/api/tests/test_rc9_ops_pack_gate.py
```


────────────────────────────────────────
3) Gate-by-Gate 체크(무엇을, 어떻게, 어디에 남기는가)

표기 규칙
- VERIFY = 반드시 실행/확인해야 하는 커맨드 또는 체크
- EVIDENCE = PASS 증빙 파일(또는 생성물) 위치

RC-0) Spec Lock
- VERIFY
  - /docs/RC_ACCEPTANCE.md 내용이 "SPEC LOCK"이며, 변경은 DEC로만 진행됨을 확인
- EVIDENCE
  - /docs/RC_ACCEPTANCE.md (스냅샷)

RC-1) Contract: Auth + Docs + OpenAPI SSOT
- VERIFY
  - `pytest apps/api/tests/test_rc1_contract.py -q`
- EVIDENCE
  - /.well-known/openapi.json (스냅샷)
  - /docs/quickstart.md
  - /docs/auth.md (선택)

RC-2) Contract: Error Format (RFC 9457)
- VERIFY
  - `pytest apps/api/tests/test_rc2_error_format.py -q`
  - (교차검증 권장) /docs/RC2_VERIFICATION_GUIDE.md의 Linux/curl 스모크 테스트 수행
- EVIDENCE
  - /docs/problem-types.md
  - (선택) /docs/RC2_VERIFICATION_GUIDE.md 실행 로그

RC-3) Contract: RateLimit Headers
- VERIFY
  - `pytest apps/api/tests/test_rc3_rate_limit_headers.py -q`
- EVIDENCE
  - /docs/rate-limits.md

RC-4) Billing/Settlement Invariants
- VERIFY
  - `pytest apps/api/tests/test_rc4_billing_invariants.py -q`
  - (워커 측 보강) `pytest apps/worker/tests/test_rc4_finalize_invariants.py -q`
- EVIDENCE
  - 테스트 PASS 로그(자동)

RC-5) Release Hygiene + API Inventory + Secrets Scan
- VERIFY
  - `pytest apps/api/tests/test_rc5_gate.py -q`
  - (리포트 재생성) 
    - `python scripts/rc5_release_hygiene_check.py`
    - `python scripts/rc5_api_inventory.py`
    - `python scripts/rc5_sensitive_data_scan.py`
- EVIDENCE
  - /docs/rc/rc5/RC5_RELEASE_HYGIENE_REPORT.md
  - /docs/rc/rc5/RC5_API_INVENTORY.md
  - /docs/rc/rc5/RC5_SENSITIVE_DATA_SCAN_REPORT.md
  - /docs/rc/rc5/RC5_HIDDEN_ENDPOINT_ALLOWLIST.txt

RC-6) Observability Minimum
- VERIFY
  - `pytest apps/api/tests/test_rc6_observability.py -q`
  - (권장) `pytest apps/api/tests/test_rc6_hardening.py -q`
- EVIDENCE
  - ops/slo.json, ops/alerts.json에서 SLI/알림 쿼리 확인(파일럿 최소셋)

RC-7) Staging E2E + OTel Contract
- VERIFY
  - `pytest apps/api/tests/test_rc7_otel_contract.py -q`
  - (권장) staging 환경에서 E2E 10케이스 스크립트 1회전 + 롤백 리허설 1회
- EVIDENCE
  - /ops/runbook.md (Rollback Procedure 포함)
  - staging 실행 로그(별도 보관)

RC-8) RC Release Packet(외부 배포용)
- VERIFY
  - `pytest apps/api/tests/test_rc8_release_packet_gate.py -q`
- EVIDENCE
  - /public/RELEASE_NOTES_v0.4_RC.md
  - /public/PILOT_READY.md

RC-9) Ops Pack Gate (SLO/Alerts/Runbook)
- VERIFY
  - `pytest apps/api/tests/test_rc9_ops_pack_gate.py -q`
- EVIDENCE
  - /ops/slo.schema.json + /ops/slo.json
  - /ops/alerts.schema.json + /ops/alerts.json
  - /ops/runbook.md

────────────────────────────────────────
4) Evidence Pack 아카이브(권장 표준 폴더)

목표: RC PASS 증빙을 "한 폴더"로 묶어, 나중에 감사/회귀검증이 가능하게 한다.

권장 경로
- `evidence/rc-v0.4-YYYYMMDD/`

최소 포함(복사본 OK)
- docs/RC_MASTER_CHECKLIST.md
- docs/RC_ACCEPTANCE.md
- public/RELEASE_NOTES_v0.4_RC.md
- public/PILOT_READY.md
- docs/problem-types.md
- docs/rate-limits.md
- docs/quickstart.md
- docs/pricing-ssot.md (+ 실제 SSOT 파일이 있다면 함께)
- docs/rc/rc5/* (4개 파일)
- ops/* (5개 파일)
- openapi snapshot: /.well-known/openapi.json
- pytest 결과 로그(전체 RC 게이트 1회전)

────────────────────────────────────────
5) Stop Rule (파일럿 직전)
- P0 결함(정의는 RC_ACCEPTANCE.md 참조) 1개라도 존재하면 즉시 STOP
- 돈 관련 경로(Reserve/Finalize/Reconcile)에서 "복구 불가" 의심 신호가 나오면 기능 개발보다 롤백/동결 우선

참고 표준(요약)
- RFC 9457 (Problem Details)  
- IETF RateLimit headers draft (RateLimit/RateLimit-Policy)  
- OWASP API Security Top 10 (특히 API inventory 관리)  
- 배포 변경은 테스트/롤백 자동화가 핵심(Operational Excellence)
