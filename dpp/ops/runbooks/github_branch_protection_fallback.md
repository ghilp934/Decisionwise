# GitHub Branch Protection: Main Branch (Fallback)

**목적**: Ruleset 사용 불가 시 Branch Protection Rules로 main 브랜치 보호

**적용 대상**: `master` 브랜치

**권장**: Ruleset 사용 (github_ruleset_main.md 참조)

---

## 자동 적용

### Bash
```bash
cd path/to/repo
APPLY=1 bash tools/github/apply_branch_protection_main.sh
```

### PowerShell
```powershell
cd path\to\repo
$env:APPLY="1"; .\tools\github\apply_branch_protection_main.ps1
```

---

## 수동 적용 (GitHub UI)

### 1. Settings 이동

1. GitHub 저장소 페이지로 이동
2. **Settings** 탭 클릭
3. 왼쪽 메뉴에서 **Branches** 선택

### 2. Branch Protection Rule 생성

1. **Branch protection rules** 섹션에서 **Add rule** 클릭
2. **Branch name pattern** 입력: `master`

### 3. 보호 설정

#### Protect matching branches

**A) Require a pull request before merging**
- ✅ **Require a pull request before merging** 체크
- ✅ **Require approvals** 체크
  - Required number of approvals: `1`
- ✅ **Dismiss stale pull request approvals when new commits are pushed** (선택 사항)
- ❌ Require review from Code Owners (선택 사항)
- ✅ **Require approval of the most recent reviewable push** (선택 사항)
- ✅ **Require conversation resolution before merging** 체크

**B) Require status checks to pass before merging**
- ✅ **Require status checks to pass before merging** 체크
- ✅ **Require branches to be up to date before merging** 체크 (Strict mode)

**Status checks that are required** (검색 후 선택):
- `RC Gates (Linux)`
- `rehearse-customer`

**⚠️ 중요**: 체크 이름은 GitHub Actions workflow job name과 정확히 일치해야 합니다.

**C) Require conversation resolution before merging**
- ✅ 체크 (위의 A 섹션에 포함됨)

**D) Require signed commits**
- ❌ 체크 안 함 (선택 사항 - 조직 정책에 따라 결정)

**E) Require linear history**
- ❌ 체크 안 함 (선택 사항)

**F) Require deployments to succeed before merging**
- ❌ 체크 안 함

**G) Lock branch**
- ❌ 체크 안 함 (read-only 모드로 전환되므로 사용 안 함)

**H) Do not allow bypassing the above settings**
- ✅ **Do not allow bypassing the above settings** 체크 (가능한 경우)
- ⚠️ **주의**: Repository admin 권한이 있어도 우회 불가

**I) Restrict who can push to matching branches**
- ❌ 체크 안 함 (PR 병합은 허용)

**Rules applied to everyone including administrators**
- ✅ **Include administrators** 체크 (관리자도 규칙 준수)

### 4. Force push 및 Deletion 방지

**이전 섹션에서 설정됨:**
- ✅ **Require a pull request before merging** 체크 시 자동으로 force push 방지
- Branch deletion은 별도 설정 필요 없음 (PR 병합 시 자동 삭제 방지)

### 5. 저장

1. **Create** 버튼 클릭 (또는 **Save changes**)
2. Branch protection rule 활성화 확인

---

## Ruleset vs Branch Protection 차이점

| 기능 | Ruleset | Branch Protection |
|------|---------|-------------------|
| 다중 브랜치 패턴 | ✅ 유연한 include/exclude | ❌ 단일 패턴만 |
| Organization-level 적용 | ✅ 가능 | ❌ 불가 |
| Tag 보호 | ✅ 가능 | ❌ 불가 |
| Bypass actors 세밀 제어 | ✅ 가능 | ⚠️ 제한적 |
| API 업데이트 | ✅ PUT (idempotent) | ⚠️ 복잡 |
| GitHub UI | ✅ 최신 UI | ❌ 레거시 UI |
| 호환성 | ✅ 2023년 이후 | ✅ 모든 저장소 |

**권장**: 가능하면 Ruleset 사용

---

## 검증

### PR 테스트

1. 새 브랜치 생성 후 변경사항 커밋
2. PR 생성
3. 확인 사항:
   - ❌ "Merge pull request" 버튼 비활성화 (체크 통과 전)
   - ⏳ "RC Gates (Linux)" 체크 실행 중
   - ⏳ "rehearse-customer" 체크 실행 중
   - ✅ 모든 체크 통과 후 머지 가능
   - ⚠️ "Branch is out-of-date" 경고 시 업데이트 필요 (Strict mode)

### Force Push 테스트 (실패 확인)

```bash
git push -f origin master
# Expected: remote: error: GH006: Protected branch update failed
```

---

## 트러블슈팅

### "Include administrators" 체크 불가

**원인**: Organization 정책으로 비활성화됨

**해결**:
1. Organization Settings → Member privileges 확인
2. 또는 조직 관리자에게 요청

### Required checks 누락

**원인**: Workflow가 한 번도 실행되지 않음

**해결**:
1. PR 생성 또는 workflow_dispatch로 수동 실행
2. 체크 실행 후 Settings에서 체크 이름 검색 가능

---

## 관련 파일

- **자동화 스크립트**:
  - `tools/github/apply_branch_protection_main.sh`
  - `tools/github/apply_branch_protection_main.ps1`
- **검증 스크립트**: `tools/github/verify_branch_rules.sh`
- **권장 방법**: `ops/runbooks/github_ruleset_main.md`

---

## 참고

- [Branch Protection Rules Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches)
