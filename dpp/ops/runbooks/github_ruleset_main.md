# GitHub Ruleset: Main Branch Protection (RC Gate)

**목적**: main/master 브랜치를 RC Gates + Pilot Packet Rehearsal 체크 없이 머지 불가로 잠금

**적용 대상**: `master` 브랜치 (default branch)

---

## 자동 적용 (권장)

### Bash
```bash
cd path/to/repo
APPLY=1 bash tools/github/apply_ruleset_main.sh
```

### PowerShell
```powershell
cd path\to\repo
$env:APPLY="1"; .\tools\github\apply_ruleset_main.ps1
```

### Plan Only (적용 없이 확인)
```bash
PLAN_ONLY=1 bash tools/github/apply_ruleset_main.sh
```

---

## 수동 적용 (GitHub UI)

### 1. Repository Settings 이동

1. GitHub 저장소 페이지로 이동
2. **Settings** 탭 클릭
3. 왼쪽 메뉴에서 **Rules** → **Rulesets** 선택

### 2. 새 Ruleset 생성

1. **New ruleset** 버튼 클릭
2. **New branch ruleset** 선택

### 3. Ruleset 기본 설정

**Ruleset Name:**
```
decisionproof-main-rc-gate
```

**Enforcement status:**
- ✅ **Active** (즉시 적용)
- ❌ Evaluate (테스트 모드 - 사용 안 함)

**Target branches:**
1. **Add target** 클릭
2. **Include by pattern** 선택
3. Pattern 입력: `master` (또는 default branch 이름)
4. **Add inclusion pattern** 클릭

### 4. Branch Rules 설정

#### A) Require a pull request before merging

- ✅ **Require a pull request before merging** 체크
- **Required approvals**: `1`
- ✅ **Require conversation resolution** 체크
- ❌ Dismiss stale pull request approvals (선택 사항)
- ❌ Require review from Code Owners (선택 사항)

#### B) Require status checks to pass

- ✅ **Require status checks to pass** 체크
- ✅ **Require branches to be up to date before merging** 체크 (Strict mode)

**Required checks 추가:**
1. **Add checks** 클릭
2. 검색창에 다음 체크 이름 입력 후 선택:
   - `RC Gates (Linux)`
   - `rehearse-customer`
3. **Add selected** 클릭

**⚠️ 중요**: Required checks 이름은 GitHub Actions workflow의 job name과 정확히 일치해야 합니다.
- rc_gates.yml: `RC Gates (Linux)`
- pilot_packet.yml: `rehearse-customer`

#### C) Block force pushes

- ✅ **Block force pushes** 체크

#### D) Block deletions

- ✅ **Require deployments to succeed** 체크하지 않음
- ✅ **Block deletions** 체크 (브랜치 삭제 방지)

### 5. Bypass list (선택 사항)

**권장 설정**: Bypass actors 없음 (모든 사용자/앱에 룰 적용)

**필요 시 Bypass 추가**:
- Repository admin
- Specific users/teams
- Apps (예: Dependabot, Renovate)

⚠️ **주의**: Bypass를 추가하면 해당 사용자/앱은 RC Gates 없이 머지 가능

### 6. 저장

1. **Create** 버튼 클릭
2. Ruleset 활성화 확인

---

## 검증

### 자동 검증
```bash
bash tools/github/verify_branch_rules.sh
```

### 수동 검증

1. **Settings** → **Rules** → **Rulesets** 이동
2. `decisionproof-main-rc-gate` ruleset 확인
3. **Enforcement**: Active
4. **Target branches**: master
5. **Rules**:
   - Pull request (1 approval, conversation resolution)
   - Required status checks (strict: true)
     - RC Gates (Linux) ✓
     - rehearse-customer ✓
   - Block force pushes ✓
   - Block deletions ✓

### PR 테스트

1. 새 브랜치 생성 후 변경사항 커밋
2. PR 생성
3. 확인 사항:
   - ❌ "Merge pull request" 버튼 비활성화 (체크 통과 전)
   - ⏳ "RC Gates (Linux)" 체크 실행 중
   - ⏳ "rehearse-customer" 체크 실행 중
   - ✅ 모든 체크 통과 후 머지 가능
   - ⚠️ "Branch is out-of-date" 경고 시 업데이트 필요 (Strict mode)

---

## 트러블슈팅

### Required check가 표시되지 않음

**원인**: GitHub Actions workflow가 한 번도 실행되지 않음

**해결**:
1. PR 생성 또는 workflow_dispatch로 수동 실행
2. 체크 실행 후 Settings에서 체크 이름 검색 가능

### 체크 이름이 다름

**확인**:
```bash
gh api repos/:owner/:repo/commits/:commit_sha/check-runs \
  --jq '.check_runs[].name'
```

**수정**:
- Workflow YAML 파일에서 `jobs.<id>.name` 확인
- Ruleset의 required check 이름과 일치하도록 수정

### Bypass가 필요한 경우

**긴급 핫픽스 시**:
1. Settings → Rules → Rulesets
2. `decisionproof-main-rc-gate` 클릭
3. **Enforcement**: Evaluate (일시적으로 비활성화)
4. 핫픽스 머지 후 다시 Active로 변경

---

## 관련 파일

- **SSOT**: `ops/github/ruleset_main.json`
- **자동화 스크립트**:
  - `tools/github/apply_ruleset_main.sh`
  - `tools/github/apply_ruleset_main.ps1`
- **검증 스크립트**: `tools/github/verify_branch_rules.sh`
- **폴백 가이드**: `ops/runbooks/github_branch_protection_fallback.md`

---

## 참고

- [GitHub Rulesets Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets)
- [Required status checks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks)
