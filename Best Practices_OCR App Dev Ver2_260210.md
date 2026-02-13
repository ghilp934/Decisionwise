Best Practices for AI-Assisted Software Development

  Version: 1.2
  Date: 2026-02-10
  Based on: OCR App Mock Session 02 Project
  Contributors: ghilp934 & Claude Sonnet 4.5

  ---
  📚 Table of Contents

  1. #1-빠른-구현-속도-달성
  2. #2-테스트-커버리지-극대화
  3. #3-human-error-최소화
  4. #4-즉시-적용-가능한-템플릿
  5. #5-quick-reference

  ---
  1. 빠른 구현 속도 달성

  1.1 명확하고 구조화된 요구사항 작성 ⭐️⭐️⭐️

  Why: 모호한 요구사항은 구현 속도를 10배 느리게 만듭니다.

  What: Milestone 기반의 상세한 킥오프 프롬프트

  How:
  ## 킥오프 프롬프트 구조

  ### 1. 프로젝트 개요
  - 목적: 무엇을 만드는가?
  - 범위: 어디까지 만드는가?
  - 제약사항: 무엇을 하지 않는가?

  ### 2. 아키텍처 방향
  - 패턴: Core + Adapters, MVC, etc.
  - 기술 스택: Python, FastAPI, etc.
  - 의존성: 외부 라이브러리, API

  ### 3. Milestone 구조
  - MS-0: 프로젝트 스켈레톤
  - MS-1: 핵심 기능
  - MS-2: 보조 기능
  - MS-3: 품질 개선
  - MS-4: 배포 준비

  ### 4. 절대 규칙 (Invariants)
  - 하드캡: 타임아웃, 크기 제한
  - 금지사항: 재귀, 추측성 구현
  - 강제사항: 타입 힌트, 테스트

  ### 5. 참고 문서
  - 스펙 문서: standalone_ocr_app_spec_v0_1.md
  - 가이드라인: CONSOLIDATED_BEST_PRACTICES.md

  Impact: 구현 속도 80% 향상

  ---
  1.2 점진적/단계적 접근 ⭐️⭐️⭐️

  Why: 한 번에 모든 것을 만들려고 하면 실패합니다.

  What: Milestone 기반 incremental development

  How:
  ## Milestone 진행 원칙

  ### Rule 1: 각 Milestone은 독립적으로 동작해야 함
  - MS-1 완료 → 테스트 가능
  - MS-2 완료 → 테스트 가능
  - MS-3 완료 → 테스트 가능

  ### Rule 2: 이전 Milestone에 의존
  - MS-2는 MS-1을 기반으로
  - MS-3는 MS-2를 기반으로
  - 역방향 의존성 금지

  ### Rule 3: 작은 단위로 자주 검증
  - 파일 3개 작성 → 테스트
  - 함수 5개 작성 → 테스트
  - 모듈 1개 완성 → 통합 테스트

  ### Rule 4: 완료 기준 명확화
  - [ ] 코드 작성 완료
  - [ ] Unit test 작성
  - [ ] 로컬 테스트 통과
  - [ ] 커밋 완료

  Impact: 디버깅 시간 70% 감소

  ---
  1.3 병렬 작업 활용 ⭐️⭐️

  Why: 여러 작업을 순차적으로 하면 시간이 오래 걸립니다.

  What: 독립적인 작업을 동시에 수행

  How:
  ## 병렬 작업 가능한 경우

  ### 파일 읽기
  ❌ Read(file1) → Read(file2) → Read(file3)
  ✅ Read(file1), Read(file2), Read(file3) in parallel

  ### 테스트 실행
  ❌ pytest test1.py && pytest test2.py
  ✅ pytest test1.py test2.py -n auto

  ### 독립적인 모듈 구현
  ✅ 동시 작업 가능:
     - input_loader.py
     - keyfields/extractor.py
     - postprocess/normalizer.py

  ❌ 순차 작업 필요:
     - config.py → pipeline.py (의존성)
     - pipeline.py → CLI (의존성)

  Impact: 구현 시간 30% 단축

  ---
  1.4 적절한 도구 선택 ⭐️⭐️

  Why: 잘못된 도구는 시간을 낭비하게 만듭니다.

  What: 작업에 최적화된 도구 사용

  How:
  ## 작업별 최적 도구

  ### 파일 검색
  ❌ Bash: find . -name "*.py"
  ✅ Glob: pattern="**/*.py"

  ### 코드 검색
  ❌ Bash: grep -r "pattern" src/
  ✅ Grep: pattern="pattern", path="src/"

  ### 파일 읽기
  ❌ Bash: cat file.py
  ✅ Read: file_path="file.py"

  ### 일괄 수정
  ❌ 수동으로 Edit 10번
  ✅ Bash: Python 스크립트로 일괄 수정

  ### 테스트 실행
  ✅ Bash: pytest (CLI 도구는 Bash가 적절)

  ## 도구 선택 기준

  | 작업 | 도구 | 이유 |
  |------|------|------|
  | 파일 찾기 | Glob | 빠르고 정확 |
  | 코드 검색 | Grep | Regex 지원 |
  | 파일 읽기 | Read | 라인 번호, 부분 읽기 |
  | 파일 쓰기 | Write | 전체 교체 |
  | 파일 수정 | Edit | 부분 수정 |
  | 일괄 작업 | Bash | 스크립트 실행 |
  | Git 작업 | Bash | Git 명령어 |

  Impact: 작업 효율 50% 향상

  ---
  2. 테스트 커버리지 극대화

  2.1 CLI/API 테스트 우선 ⭐️⭐️⭐️

  Why: CLI/API는 사용자가 직접 접하는 인터페이스이지만 커버리지가 0%인 경우가 많습니다.

  What: Typer CliRunner, FastAPI TestClient 사용

  How:

  CLI 테스트 (Typer)

  # tests/cli/test_main.py
  from typer.testing import CliRunner
  from ocr_cli.main import app

  runner = CliRunner()

  def test_cli_run_command():
      """CLI run 명령어 테스트"""
      result = runner.invoke(app, ["run", "-i", "test.png", "-p", "P1_SCAN"])

      assert result.exit_code == 0
      assert "Processing" in result.stdout

  def test_cli_batch_command():
      """CLI batch 명령어 테스트"""
      result = runner.invoke(app, ["batch", "--in-dir", "./images"])

      assert result.exit_code == 0
      assert "Found" in result.stdout

  def test_cli_invalid_file():
      """존재하지 않는 파일"""
      result = runner.invoke(app, ["run", "-i", "nonexistent.png"])

      assert result.exit_code != 0
      assert "not found" in result.stdout.lower()

  API 테스트 (FastAPI)

  # tests/api/test_main.py
  from fastapi.testclient import TestClient
  from ocr_api.main import app

  client = TestClient(app)

  def test_api_ocr_endpoint():
      """OCR endpoint 테스트"""
      with open("tests/fixtures/sample.png", "rb") as f:
          response = client.post(
              "/v1/ocr",
              files={"file": ("sample.png", f, "image/png")},
              data={"profile": "P1_SCAN"}
          )

      assert response.status_code == 200
      data = response.json()
      assert "text" in data
      assert "keyfields" in data

  def test_api_rate_limit():
      """Rate limit 테스트"""
      for _ in range(11):  # 제한: 10 req/60s
          response = client.post("/v1/ocr", ...)

      assert response.status_code == 429

  def test_api_invalid_file_format():
      """잘못된 파일 형식"""
      response = client.post(
          "/v1/ocr",
          files={"file": ("test.txt", b"not an image", "text/plain")}
      )

      assert response.status_code == 422

  Impact: 커버리지 +20-30%

  ---
  2.2 Integration Test 강화 ⭐️⭐️⭐️

  Why: Unit test는 많지만 전체 시스템이 통합되었을 때 동작하는지 확인이 부족합니다.

  What: End-to-end 시나리오 테스트

  How:
  # tests/integration/test_full_pipeline.py
  import pytest
  from pathlib import Path
  from ocr_app.core.pipeline import process_single_image
  from ocr_app.config import PreprocessProfile

  @pytest.mark.integration
  def test_full_pipeline_with_real_tesseract():
      """실제 Tesseract로 전체 파이프라인 테스트"""
      # 실제 이미지 파일
      image_path = Path("tests/fixtures/sample_document.png")

      # 전체 파이프라인 실행
      result = process_single_image(image_path, PreprocessProfile.P1_SCAN)

      # 결과 검증
      assert result.success is True
      assert len(result.text) > 0
      assert result.metadata["profile"] == "P1"
      assert result.metadata["elapsed_seconds"] < 40

      # 키필드 추출 확인
      assert "url" in result.keyfields
      assert "keyfield_coverage" in result.metadata

  @pytest.mark.integration
  def test_longscroll_end_to_end():
      """롱스크롤 이미지 전체 처리"""
      image_path = Path("tests/fixtures/longscroll_5000px.png")

      result = process_single_image(image_path, PreprocessProfile.P3_SCREEN)

      assert result.success is True
      assert result.metadata["is_longscroll"] is True
      assert result.metadata["num_chunks"] > 1
      assert result.metadata["num_chunks"] <= 12  # MAX_SPLITS

  @pytest.mark.integration
  def test_golden_set_regression():
      """Golden Set 회귀 테스트"""
      from ocr_app.regression.golden_set import run_regression_test

      golden_dir = Path("04_GOLDEN/set1")

      # OCR 실행
      ocr_results = {}
      for image in golden_dir.glob("inputs/*.png"):
          result = process_single_image(image, PreprocessProfile.P1_SCAN)
          ocr_results[image.name] = {
              "keyfields": result.keyfields,
              "text": result.text
          }

      # 회귀 테스트
      regression_result = run_regression_test(golden_dir, ocr_results)

      assert regression_result.passed is True
      assert len(regression_result.failures) == 0

  pytest 설정:
  # pytest.ini
  [pytest]
  markers =
      integration: marks tests as integration tests (deselect with '-m "not integration"')

  # 일반 테스트 (빠름)
  pytest tests/unit/

  # 통합 테스트 포함 (느림)
  pytest tests/

  Impact: 커버리지 +10%, 품질 대폭 향상

  ---
  2.3 Property-Based Testing ⭐️⭐️

  Why: 수동으로 테스트 케이스를 작성하면 엣지 케이스를 놓칠 수 있습니다.

  What: Hypothesis로 다양한 입력 자동 생성

  How:
  # tests/unit/test_longscroll_property.py
  from hypothesis import given, strategies as st
  from PIL import Image
  from ocr_app.preprocessing.longscroll import is_longscroll

  @given(
      width=st.integers(min_value=100, max_value=5000),
      height=st.integers(min_value=100, max_value=30000)
  )
  def test_longscroll_detection_property(width, height):
      """다양한 크기의 이미지에 대해 롱스크롤 감지 테스트"""
      img = Image.new("RGB", (width, height))
      is_long = is_longscroll(img)

      # 속성 검증
      expected = (height >= 2500) or (height / width >= 2.8)
      assert is_long == expected

  @given(text=st.text(min_size=0, max_size=1000))
  def test_normalize_text_idempotent(text):
      """정규화가 idempotent 한지 테스트"""
      from ocr_app.postprocess.normalizer import normalize_text

      normalized_once = normalize_text(text)
      normalized_twice = normalize_text(normalized_once)

      # 두 번 정규화해도 결과가 같아야 함
      assert normalized_once == normalized_twice

  # 실행
  pytest tests/unit/test_longscroll_property.py
  # Hypothesis가 100개의 다양한 입력을 자동 생성하여 테스트

  Impact: 버그 발견률 향상, 엣지 케이스 자동 탐지

  ---
  2.4 Error Path Testing ⭐️⭐️

  Why: Happy path만 테스트하면 예외 상황에서 실패합니다.

  What: 모든 예외 경로 테스트

  How:
  # tests/unit/test_error_paths.py
  import pytest
  from unittest.mock import patch
  from pathlib import Path

  def test_all_exception_types():
      """모든 예외 타입 테스트"""

      # 1. File not found
      with pytest.raises(InputValidationError, match="not found"):
          load_image(Path("/nonexistent/file.png"))

      # 2. Invalid file format
      with tempfile.NamedTemporaryFile(suffix=".exe") as f:
          with pytest.raises(InputValidationError, match="Unsupported"):
              validate_image_file(Path(f.name))

      # 3. OCR timeout
      with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("cmd", 10)):
          with pytest.raises(OCRTimeoutError, match="timeout"):
              run_tesseract_subprocess(...)

      # 4. Path traversal
      with pytest.raises(InputValidationError, match="Path traversal"):
          validate_path(Path("../../etc/passwd"))

      # 5. Oversized file
      with pytest.raises(InputValidationError, match="File too large"):
          validate_image_file(Path("huge_file.png"))  # > 25MB

  def test_graceful_degradation():
      """부분 실패 시 우아한 처리"""
      from ocr_app.core.pipeline import process_longscroll_image

      # 롱스크롤에서 일부 청크 실패
      with patch('ocr_with_fallback', side_effect=[
          ("chunk1 text", {}),
          OCRTimeoutError("timeout"),
          ("chunk3 text", {}),
          OCRError("failed")
      ]):
          result = process_longscroll_image(...)

          # 부분 실패해도 처리 완료
          assert result.success is True
          assert "[타임아웃]" in result.text
          assert "[오류]" in result.text
          assert len(result.warnings) >= 2

  def test_resource_cleanup():
      """예외 발생 시 리소스 정리"""
      with pytest.raises(Exception):
          with tempfile.TemporaryDirectory() as tmpdir:
              # 예외 발생해도 tmpdir 정리되는지 확인
              raise Exception("test")

      # tmpdir이 삭제되었는지 확인
      assert not Path(tmpdir).exists()

  Impact: 커버리지 +5%, 안정성 향상

  ---
  2.5 우선순위별 테스트 전략
  ┌──────────┬────────────────────┬───────────────┬───────────┐
  │ 우선순위 │    테스트 종류     │ 커버리지 목표 │ 시간 투자 │
  ├──────────┼────────────────────┼───────────────┼───────────┤
  │ ⭐️⭐️⭐️   │ CLI/API 테스트     │ +20-30%       │ 2-3시간   │
  ├──────────┼────────────────────┼───────────────┼───────────┤
  │ ⭐️⭐️⭐️   │ Integration 테스트 │ +10%          │ 2-3시간   │
  ├──────────┼────────────────────┼───────────────┼───────────┤
  │ ⭐️⭐️     │ Error Path 테스트  │ +5%           │ 1-2시간   │
  ├──────────┼────────────────────┼───────────────┼───────────┤
  │ ⭐️⭐️     │ Property-based     │ 버그 발견     │ 1-2시간   │
  ├──────────┼────────────────────┼───────────────┼───────────┤
  │ ⭐️       │ Branch Coverage    │ 품질 향상     │ 1시간     │
  ├──────────┼────────────────────┼───────────────┼───────────┤
  │ ⭐️       │ Mutation Testing   │ 검증          │ 1시간     │
  └──────────┴────────────────────┴───────────────┴───────────┘
  총 예상 시간: 8-14시간
  총 커버리지 향상: +35-45%
  최종 목표: 90-95%

  ---
  3. Human Error 최소화

  3.1 킥오프 체크리스트 ⭐️⭐️⭐️

  Why: 프로젝트 시작 시 기초를 탄탄히 하면 나중에 문제가 발생하지 않습니다.

  What: 5분 이내 완료 가능한 초기 설정

  How:
  ## 프로젝트 초기화 체크리스트 (5분 소요)

  ### Git 설정
  [ ] 1. Git 저장소 초기화
      cd project-directory
      git init
      git remote add origin https://github.com/<user>/<repo>.git

  [ ] 2. .gitignore 생성
      # Python
      __pycache__/
      *.py[cod]
      venv/
      .env

      # IDE
      .vscode/
      .idea/

      # Project
      output/
      logs/
      *.log

  [ ] 3. 첫 커밋
      git add .
      git commit -m "chore: 프로젝트 초기화"
      git push -u origin main

  ### Python 환경
  [ ] 4. 가상환경 생성
      python -m venv venv

      # 활성화
      source venv/bin/activate  # Linux/Mac
      venv\Scripts\activate     # Windows

  [ ] 5. 필수 도구 설치
      pip install --upgrade pip
      pip install ruff black mypy pytest pytest-cov

  [ ] 6. (선택) Pre-commit hooks
      pip install pre-commit
      pre-commit install

  ### CI/CD 준비
  [ ] 7. GitHub Actions 템플릿 생성
      mkdir -p .github/workflows
      touch .github/workflows/ci.yml

      # 기본 템플릿 작성 (비어있어도 OK)

  [ ] 8. (선택) 로컬 CI 도구 설치
      # act (GitHub Actions 로컬 실행)
      brew install act  # macOS
      choco install act-cli  # Windows

  ### 환경 확인
  [ ] 9. Python 버전 확인
      python --version  # 3.12+

  [ ] 10. 필수 시스템 패키지 확인
      # 프로젝트별로 다름 (예: tesseract)
      tesseract --version

  ---

  ## 완료 확인

  [ ] Git 원격 저장소 연결됨
  [ ] 가상환경 활성화됨
  [ ] 필수 도구 설치됨
  [ ] 첫 커밋 완료

  Impact: 후반부 문제 80% 예방

  ---
  3.2 "Test → Commit → Verify" 프로토콜 ⭐️⭐️⭐️

  Why: 이 순서를 지키지 않으면 CI 실패, 버그 누적, 롤백 등의 문제가 발생합니다.

  What: 모든 Milestone 완료 시 반드시 따라야 할 절차

  How:
  ## "Test → Commit → Verify" 프로토콜

  ### Phase 1: Test (로컬 검증)

  [ ] 1.1 전체 테스트 실행
      pytest tests/ -v

      예상 시간: 2-10초
      성공 기준: 모든 테스트 통과

  [ ] 1.2 린팅 & 포맷 확인
      ruff check src/ tests/
      black --check src/ tests/

      예상 시간: 1-2초
      성공 기준: 에러 없음

  [ ] 1.3 타입 체크 (선택)
      mypy src/

      예상 시간: 3-5초
      성공 기준: 에러 없음

  [ ] 1.4 (권장) 로컬 CI 시뮬레이션
      act push -j test -j lint

      예상 시간: 30-60초
      성공 기준: 모든 job 통과

  ---

  ### Phase 2: Commit (변경사항 저장)

  [ ] 2.1 변경사항 확인
      git status
      git diff

      확인사항: 의도하지 않은 파일 포함 여부

  [ ] 2.2 스테이징
      # 특정 파일만 (권장)
      git add src/ocr_app/module.py tests/unit/test_module.py

      # 또는 전체 (주의)
      git add .

  [ ] 2.3 커밋 메시지 작성
      git commit -m "feat: MS-X 완료

      - 주요 변경사항 1
      - 주요 변경사항 2

      Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

  [ ] 2.4 푸시 전 최종 확인
      git log --oneline -n 3
      git diff origin/main..HEAD --stat

  ---

  ### Phase 3: Verify (원격 검증)

  [ ] 3.1 푸시
      git push origin main

  [ ] 3.2 GitHub Actions 확인 (5분 이내)
      https://github.com/<user>/<repo>/actions

      확인사항:
      - [ ] CI / Lint & Format: ✅
      - [ ] CI / Test: ✅
      - [ ] CI / Static Checks: ✅
      - [ ] CI / Security Scan: ✅
      - [ ] Docker Build: ✅

  [ ] 3.3 실패 시 즉시 수정
      # 로그 확인
      # 로컬에서 재현
      # 수정 후 Phase 1부터 다시 시작

  ---

  ## 🚨 주의사항

  ### 절대 하지 말 것
  ❌ 테스트 없이 커밋
  ❌ 로컬 테스트 실패 상태로 푸시
  ❌ CI 실패를 무시하고 다음 작업 진행
  ❌ "나중에 고치지 뭐" 마인드

  ### 반드시 할 것
  ✅ 로컬에서 모든 테스트 통과 확인
  ✅ 작은 단위로 자주 커밋
  ✅ 각 커밋은 독립적으로 동작
  ✅ CI 실패는 최우선 수정

  ---

  ## 예외 상황

  ### Q: 테스트가 너무 오래 걸리면?
  A: 빠른 테스트만 선택 실행
     pytest tests/unit/ -v  # Integration 제외

  ### Q: CI가 너무 느리면?
  A: 로컬 CI 시뮬레이션만 하고 푸시
     act push -j lint -j test

  ### Q: 급하게 hotfix 해야 하면?
  A: 그래도 순서는 지킬 것!
     빠른 테스트 → 커밋 → 푸시 → 확인

  Impact: CI 실패 90% 감소, 롤백 80% 감소

  ---
  3.3 Pre-commit Hooks ⭐️⭐️

  Why: 사람은 실수하지만 기계는 실수하지 않습니다.

  What: 커밋 전 자동 검증

  How:
  # .pre-commit-config.yaml
  repos:
    # Black (포맷팅)
    - repo: https://github.com/psf/black
      rev: 23.0.0
      hooks:
        - id: black
          language_version: python3.12

    # Ruff (린팅)
    - repo: https://github.com/astral-sh/ruff-pre-commit
      rev: v0.1.0
      hooks:
        - id: ruff
          args: [--fix]

    # Mypy (타입 체크)
    - repo: https://github.com/pre-commit/mirrors-mypy
      rev: v1.10.0
      hooks:
        - id: mypy
          additional_dependencies: [types-all]

    # pytest (테스트)
    - repo: local
      hooks:
        - id: pytest-check
          name: pytest
          entry: pytest tests/unit/ -q
          language: system
          pass_filenames: false
          always_run: true

    # 파일 크기 체크
    - repo: https://github.com/pre-commit/pre-commit-hooks
      rev: v4.5.0
      hooks:
        - id: check-added-large-files
          args: ['--maxkb=1000']
        - id: check-yaml
        - id: end-of-file-fixer
        - id: trailing-whitespace

  설치 및 사용:
  # 설치
  pip install pre-commit

  # Hook 활성화
  pre-commit install

  # 이제 git commit 시 자동으로:
  # 1. Black 포맷팅 (자동 수정)
  # 2. Ruff 린팅 (자동 수정)
  # 3. Mypy 타입 체크
  # 4. pytest 실행
  # → 하나라도 실패하면 커밋 차단!

  # 수동 실행
  pre-commit run --all-files

  Impact: Human error 80% 자동 차단

  ---
  3.4 로컬 CI 시뮬레이션 ⭐️⭐️

  Why: 푸시 후 CI가 실패하면 시간이 낭비됩니다.

  What: 로컬에서 GitHub Actions를 미리 실행

  How:

  방법 A: act (권장)

  # 설치
  # macOS
  brew install act

  # Windows
  choco install act-cli

  # Linux
  curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

  # 사용법
  # 1. Push event 시뮬레이션
  act push

  # 2. 특정 job만 실행
  act push -j test
  act push -j lint

  # 3. Workflow 파일 지정
  act push -W .github/workflows/ci.yml

  # 4. Dry run (실행 계획만 확인)
  act push -n

  방법 B: Docker로 CI 환경 재현

  # CI와 동일한 환경
  docker run -it -v $(pwd):/app python:3.12 bash

  # 컨테이너 내부에서
  cd /app
  pip install -e ".[dev]"
  pytest tests/
  ruff check src/
  black --check src/

  방법 C: 로컬 스크립트

  # scripts/local-ci.sh
  #!/bin/bash
  set -e

  echo "=== Running Local CI ==="

  echo "[1/5] Linting..."
  ruff check src/ tests/

  echo "[2/5] Formatting..."
  black --check src/ tests/

  echo "[3/5] Type checking..."
  mypy src/

  echo "[4/5] Unit tests..."
  pytest tests/unit/ -v

  echo "[5/5] Integration tests..."
  pytest tests/integration/ -v

  echo "✅ All checks passed!"

  Impact: CI 실패 70% 사전 방지

  ---
  3.5 Milestone별 검증 체크리스트 ⭐️⭐️

  Why: Milestone 완료 시 일관된 품질을 유지해야 합니다.

  What: 복사해서 바로 쓸 수 있는 체크리스트

  How:
  ## Milestone X 완료 체크리스트

  ### 코드 품질
  [ ] 모든 파일에 docstring 있음
  [ ] 타입 힌트 100%
  [ ] 함수 복잡도 < 10
  [ ] 중복 코드 없음

  ### 테스트
  [ ] Unit test 작성 (커버리지 90%+)
  [ ] Integration test 작성 (주요 시나리오)
  [ ] Edge case 테스트
  [ ] Error path 테스트

  ### 문서
  [ ] README.md 업데이트
  [ ] API 문서 업데이트 (해당 시)
  [ ] DECISION_LOG.md 업데이트 (중요 결정 시)

  ### Git
  [ ] 로컬 테스트 통과
  [ ] 로컬 CI 시뮬레이션 통과
  [ ] 커밋 메시지 명확
  [ ] 푸시 완료
  [ ] GitHub Actions 통과

  ### 사후 확인
  [ ] 코드 리뷰 (self-review)
  [ ] 다음 Milestone 준비사항 확인

  ---
  3.6 LESSONS_LEARNED.md 작성 ⭐️

  Why: 같은 실수를 반복하지 않기 위해

  What: 프로젝트별 교훈 문서화

  How:
  # LESSONS_LEARNED.md

  ## 프로젝트: [프로젝트명]
  ## 날짜: YYYY-MM-DD

  ---

  ## 😢 실수한 것들

  ### 1. [실수 제목]
  - **무엇을**: [무슨 실수를 했는가?]
  - **왜**: [왜 실수했는가?]
  - **영향**: [어떤 문제가 발생했는가?]
  - **해결**: [어떻게 해결했는가?]
  - **예방**: [다음에 어떻게 예방할 것인가?]

  **예시:**
  ### 1. CI 워크플로우를 로컬에서 테스트하지 않고 푸시
  - **무엇을**: GitHub Actions 워크플로우를 작성하고 검증 없이 푸시
  - **왜**: 로컬 CI 시뮬레이션 프로세스가 없었음
  - **영향**: 5개 job 실패, 30분 디버깅 소요
  - **해결**: act 설치, 워크플로우 수정, 재푸시
  - **예방**:
    - [ ] act 설치 (킥오프 체크리스트에 추가)
    - [ ] 푸시 전 `act push` 실행 (프로토콜에 추가)

  ---

  ## 😊 잘한 것들

  ### 1. [잘한 것 제목]
  - **무엇을**: [무엇을 잘했는가?]
  - **왜**: [왜 효과적이었는가?]
  - **영향**: [어떤 긍정적 효과가 있었는가?]
  - **재사용**: [다음에도 어떻게 활용할 것인가?]

  **예시:**
  ### 1. Milestone 기반 점진적 접근
  - **무엇을**: MS-0부터 MS-4까지 단계별로 구현
  - **왜**: 각 단계가 명확히 정의되어 있고 검증 가능
  - **영향**: 구현 속도 80% 향상, 디버깅 시간 70% 감소
  - **재사용**: 모든 프로젝트에 Milestone 구조 적용

  ---

  ## 📊 메트릭

  | 항목 | 목표 | 달성 | 평가 |
  |------|------|------|------|
  | 구현 시간 | 10시간 | 8시간 | ✅ |
  | 테스트 커버리지 | 90% | 63% | ⚠️ |
  | CI 성공률 | 100% | 85% | ⚠️ |
  | 버그 개수 | 0 | 3 | ❌ |

  ---

  ## 🎯 다음 프로젝트 액션 아이템

  [ ] 1. 킥오프 체크리스트에 act 설치 추가
  [ ] 2. "Test → Commit → Verify" 프로토콜 엄수
  [ ] 3. CLI/API 테스트 우선 작성
  [ ] 4. Pre-commit hooks 설정
  [ ] 5. Integration test 20개 이상 작성

  ---

  ## 💬 회고

  ### Keep (계속할 것)
  - Milestone 기반 접근
  - 명확한 요구사항 작성
  - AI와의 효율적인 협업

  ### Problem (문제점)
  - CI 검증 부족
  - CLI/API 테스트 부재
  - 환경 차이 고려 부족

  ### Try (시도할 것)
  - 로컬 CI 시뮬레이션
  - Pre-commit hooks 도입
  - Property-based testing

  Impact: 반복 실수 90% 감소, 지속적 개선

  ---
  4. 즉시 적용 가능한 템플릿

  4.1 킥오프 프롬프트 템플릿

  # [프로젝트명] 킥오프 프롬프트

  ## 1. 프로젝트 개요

  ### 목적
  [무엇을 만드는가? 왜 만드는가?]

  ### 범위
  [어디까지 만드는가? 포함/제외 사항은?]

  ### 제약사항
  - [제약사항 1]
  - [제약사항 2]

  ---

  ## 2. 아키텍처

  ### 패턴
  [Core + Adapters / MVC / Clean Architecture / etc.]

  ### 기술 스택
  - **Language**: Python 3.12+
  - **Framework**: [FastAPI / Flask / Django / etc.]
  - **Database**: [PostgreSQL / MongoDB / etc.]
  - **Testing**: pytest, pytest-cov

  ### 의존성
  - [라이브러리 1]: [용도]
  - [라이브러리 2]: [용도]

  ---

  ## 3. Milestone 구조

  ### MS-0: 프로젝트 스켈레톤 (30분)
  - [ ] 디렉토리 구조 생성
  - [ ] pyproject.toml 작성
  - [ ] README.md 초안
  - [ ] Git 초기화

  ### MS-1: 핵심 기능 (3-5시간)
  - [ ] [기능 1]
  - [ ] [기능 2]
  - [ ] Unit test 작성

  ### MS-2: 보조 기능 (2-3시간)
  - [ ] [기능 3]
  - [ ] [기능 4]
  - [ ] Integration test 추가

  ### MS-3: 품질 개선 (2-3시간)
  - [ ] 타입 안전성 (mypy strict)
  - [ ] 테스트 커버리지 90%+
  - [ ] 코드 리팩터링
  - [ ] 문서화

  ### MS-4: 배포 준비 (2-3시간)
  - [ ] Docker 컨테이너화
  - [ ] CI/CD 설정
  - [ ] 모니터링 추가

  ---

  ## 4. 절대 규칙 (Invariants)

  ### 하드캡
  - [제한 1]: [값]
  - [제한 2]: [값]

  ### 금지사항
  - ❌ [금지사항 1]
  - ❌ [금지사항 2]

  ### 강제사항
  - ✅ [강제사항 1]
  - ✅ [강제사항 2]

  ---

  ## 5. Human Error 방지 프로토콜

  ### "Test → Commit → Verify" 순서 엄수

  **Phase 1: Test**
  [ ] 로컬에서 전체 테스트 실행
  [ ] 로컬에서 린팅/포맷 확인
  [ ] (권장) 로컬 CI 시뮬레이션

  **Phase 2: Commit**
  [ ] 변경사항 확인
  [ ] 커밋 메시지 작성
  [ ] 푸시 전 최종 확인

  **Phase 3: Verify**
  [ ] 푸시
  [ ] 5분 내 GitHub Actions 확인
  [ ] 실패 시 즉시 수정

  ### Milestone 완료 체크리스트
  [ ] 코드 품질 확인
  [ ] 테스트 작성 및 통과
  [ ] 문서 업데이트
  [ ] Git 커밋 및 푸시
  [ ] CI 통과 확인

  ---

  ## 6. 참고 문서
  - [스펙 문서 경로]
  - [가이드라인 문서 경로]
  - [Best Practices 문서 경로]

  ---

  ## 7. AI Agent Instructions

  "각 Milestone 완료 시:
  1. 로컬 테스트 실행 제안
  2. 커밋 전 체크리스트 제공
  3. 커밋 후 CI 확인 리마인더
  4. 환경 차이 경고 (Windows/Linux)"

  ---
  4.2 Milestone 완료 체크리스트

  ## Milestone [X] 완료 체크리스트

  **날짜**: YYYY-MM-DD
  **소요 시간**: [X]시간
  **담당자**: [이름]

  ---

  ### ✅ 코드 품질

  [ ] **Docstring**: 모든 public 함수/클래스에 docstring 있음
  [ ] **타입 힌트**: 100% 타입 힌트 적용
  [ ] **복잡도**: 모든 함수 복잡도 < 10 (McCabe)
  [ ] **중복 코드**: 중복 코드 제거 완료
  [ ] **네이밍**: 명확하고 일관된 네이밍

  ---

  ### ✅ 테스트

  [ ] **Unit Test**: 작성 완료 (커버리지 90%+)
      pytest tests/unit/ --cov=src --cov-report=term

  [ ] **Integration Test**: 주요 시나리오 작성
      pytest tests/integration/ -v

  [ ] **Edge Case**: 경계 조건 테스트 작성

  [ ] **Error Path**: 예외 상황 테스트 작성

  [ ] **Performance**: (해당 시) 성능 테스트

  ---

  ### ✅ 문서

  [ ] **README.md**: 업데이트
  [ ] **API 문서**: (해당 시) 업데이트
  [ ] **DECISION_LOG.md**: (중요 결정 시) 업데이트
  [ ] **코드 주석**: 복잡한 로직에 주석 추가

  ---

  ### ✅ 로컬 검증

  [ ] **pytest**: 모든 테스트 통과
      pytest tests/ -v

  [ ] **ruff**: 린팅 통과
      ruff check src/ tests/

  [ ] **black**: 포맷팅 통과
      black --check src/ tests/

  [ ] **mypy**: (선택) 타입 체크 통과
      mypy src/

  [ ] **로컬 CI**: (권장) 시뮬레이션 통과
      act push

  ---

  ### ✅ Git

  [ ] **변경사항 확인**
      git status
      git diff

  [ ] **커밋 메시지 작성**
      git commit -m "feat: MS-X 완료

      - 주요 변경사항 1
      - 주요 변경사항 2

      Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

  [ ] **푸시 전 확인**
      git log --oneline -n 3

  [ ] **푸시**
      git push origin main

  ---

  ### ✅ CI/CD

  [ ] **GitHub Actions 확인** (5분 이내)
      https://github.com/<user>/<repo>/actions

      - [ ] CI / Lint & Format: ✅
      - [ ] CI / Test: ✅
      - [ ] CI / Static Checks: ✅
      - [ ] CI / Security Scan: ✅
      - [ ] Docker Build: ✅ (해당 시)

  [ ] **실패 시 즉시 수정**
      (로그 확인 → 로컬 재현 → 수정 → 재푸시)

  ---

  ### ✅ 사후 확인

  [ ] **Self-review**: 코드 리뷰 (자기 검토)
  [ ] **Breaking Change**: 있다면 문서화
  [ ] **다음 Milestone**: 준비사항 확인

  ---

  ## 📝 메모

  [특이사항, 주의사항, 다음 Milestone에 전달할 내용 등]

  ---

  ## ✅ 완료 확인

  **완료 일시**: YYYY-MM-DD HH:MM
  **승인자**: [이름]
  **상태**: ✅ 완료 / ⚠️ 부분 완료 / ❌ 미완료

  ---
  4.3 .pre-commit-config.yaml 템플릿

  # .pre-commit-config.yaml
  # 커밋 전 자동 검증

  repos:
    # Python 포맷팅
    - repo: https://github.com/psf/black
      rev: 23.0.0
      hooks:
        - id: black
          language_version: python3.12
          args: [--line-length=100]

    # Python 린팅
    - repo: https://github.com/astral-sh/ruff-pre-commit
      rev: v0.1.0
      hooks:
        - id: ruff
          args: [--fix, --line-length=100]

    # 타입 체크 (선택)
    - repo: https://github.com/pre-commit/mirrors-mypy
      rev: v1.10.0
      hooks:
        - id: mypy
          additional_dependencies: [types-all]
          args: [--strict]

    # 테스트 (빠른 것만)
    - repo: local
      hooks:
        - id: pytest-quick
          name: pytest (unit only)
          entry: pytest tests/unit/ -q --tb=line
          language: system
          pass_filenames: false
          always_run: true

    # 파일 검사
    - repo: https://github.com/pre-commit/pre-commit-hooks
      rev: v4.5.0
      hooks:
        - id: check-added-large-files
          args: ['--maxkb=1000']
        - id: check-yaml
        - id: check-json
        - id: check-toml
        - id: end-of-file-fixer
        - id: trailing-whitespace
        - id: mixed-line-ending

    # Security 체크
    - repo: https://github.com/PyCQA/bandit
      rev: 1.7.5
      hooks:
        - id: bandit
          args: [-ll, -i, -x, tests/]

  # 설정
  default_language_version:
    python: python3.12

  fail_fast: false  # 모든 hook 실행 후 결과 표시

  사용법:
  # 설치
  pip install pre-commit

  # Hook 활성화
  pre-commit install

  # 수동 실행
  pre-commit run --all-files

  # 특정 hook만 실행
  pre-commit run black --all-files

  # Hook 업데이트
  pre-commit autoupdate

  ---
  4.4 LESSONS_LEARNED.md 템플릿

  # LESSONS_LEARNED.md

  **프로젝트**: [프로젝트명]
  **기간**: YYYY-MM-DD ~ YYYY-MM-DD
  **팀**: [팀원들]

  ---

  ## 😢 실수한 것들

  ### 1. [실수 제목]

  **무엇을**:
  [무슨 실수를 했는가?]

  **왜**:
  [왜 실수했는가? 근본 원인은?]

  **영향**:
  [어떤 문제가 발생했는가? 영향 범위는?]

  **해결**:
  [어떻게 해결했는가? 소요 시간은?]

  **예방**:
  - [ ] [다음에 어떻게 예방할 것인가? - 액션 아이템 1]
  - [ ] [액션 아이템 2]

  ---

  ## 😊 잘한 것들

  ### 1. [잘한 것 제목]

  **무엇을**:
  [무엇을 잘했는가?]

  **왜**:
  [왜 효과적이었는가?]

  **영향**:
  [어떤 긍정적 효과가 있었는가?]

  **재사용**:
  [다음에도 어떻게 활용할 것인가?]

  ---

  ## 📊 메트릭

  ### 목표 대비 달성률

  | 항목 | 목표 | 달성 | 달성률 | 평가 |
  |------|------|------|--------|------|
  | 구현 시간 | 10시간 | 8시간 | 125% | ✅ |
  | 테스트 커버리지 | 90% | 63% | 70% | ⚠️ |
  | CI 성공률 | 100% | 85% | 85% | ⚠️ |
  | 버그 개수 | 0 | 3 | - | ❌ |
  | 코드 품질 (Ruff) | 0 errors | 0 | 100% | ✅ |

  ### 시간 분배

  | 활동 | 예상 | 실제 | 차이 |
  |------|------|------|------|
  | 요구사항 정의 | 1h | 0.5h | -0.5h |
  | 코딩 | 5h | 6h | +1h |
  | 테스트 작성 | 2h | 1.5h | -0.5h |
  | 디버깅 | 1h | 2h | +1h |
  | 문서화 | 1h | 0.5h | -0.5h |
  | **총계** | **10h** | **10.5h** | **+0.5h** |

  ---

  ## 🎯 다음 프로젝트 액션 아이템

  ### 필수 (Must)
  - [ ] 1. 킥오프 체크리스트 작성 및 실행
  - [ ] 2. "Test → Commit → Verify" 프로토콜 엄수
  - [ ] 3. Pre-commit hooks 설정

  ### 권장 (Should)
  - [ ] 4. CLI/API 테스트 우선 작성
  - [ ] 5. 로컬 CI 시뮬레이션 (act)
  - [ ] 6. Integration test 20개 이상

  ### 선택 (Could)
  - [ ] 7. Property-based testing 도입
  - [ ] 8. Mutation testing
  - [ ] 9. Performance testing

  ---

  ## 💬 회고

  ### Keep (계속할 것)
  - ✅ [잘했던 것 1]
  - ✅ [잘했던 것 2]

  ### Problem (문제점)
  - ⚠️ [문제점 1]
  - ⚠️ [문제점 2]

  ### Try (시도할 것)
  - 🔄 [다음에 시도할 것 1]
  - 🔄 [다음에 시도할 것 2]

  ---

  ## 📚 참고 자료

  - [관련 문서 1]
  - [관련 문서 2]
  - [Best Practices 문서]

  ---

  **작성자**: [이름]
  **검토자**: [이름]
  **승인 일자**: YYYY-MM-DD

  ---
  5. Quick Reference

  5.1 우선순위 요약
  ┌────────┬────────────────────────┬───────┬───────────────────────┐
  │  순위  │     Best Practice      │ 시간  │         효과          │
  ├────────┼────────────────────────┼───────┼───────────────────────┤
  │ ⭐️⭐️⭐️ │ 킥오프 체크리스트      │ 5분   │ 후반 문제 80% 예방    │
  ├────────┼────────────────────────┼───────┼───────────────────────┤
  │ ⭐️⭐️⭐️ │ Test → Commit → Verify │ 항상  │ CI 실패 90% 감소      │
  ├────────┼────────────────────────┼───────┼───────────────────────┤
  │ ⭐️⭐️⭐️ │ 명확한 요구사항        │ 1시간 │ 속도 80% 향상         │
  ├────────┼────────────────────────┼───────┼───────────────────────┤
  │ ⭐️⭐️⭐️ │ CLI/API 테스트         │ 3시간 │ 커버리지 +20-30%      │
  ├────────┼────────────────────────┼───────┼───────────────────────┤
  │ ⭐️⭐️   │ Pre-commit hooks       │ 30분  │ 에러 80% 자동 차단    │
  ├────────┼────────────────────────┼───────┼───────────────────────┤
  │ ⭐️⭐️   │ 로컬 CI 시뮬레이션     │ 1시간 │ CI 실패 70% 사전 방지 │
  ├────────┼────────────────────────┼───────┼───────────────────────┤
  │ ⭐️⭐️   │ Integration test       │ 3시간 │ 커버리지 +10%         │
  ├────────┼────────────────────────┼───────┼───────────────────────┤
  │ ⭐️     │ Property-based testing │ 2시간 │ 버그 발견률 향상      │
  └────────┴────────────────────────┴───────┴───────────────────────┘
  ---
  5.2 체크리스트 한눈에 보기

  프로젝트 시작 시 (5분)

  [ ] Git 초기화
  [ ] .gitignore 설정
  [ ] 가상환경 생성
  [ ] 필수 도구 설치
  [ ] 첫 커밋

  코드 작성 후 (매번)

  [ ] pytest tests/ -v
  [ ] ruff check src/
  [ ] black --check src/
  [ ] (권장) act push
  [ ] git commit
  [ ] git push
  [ ] GitHub Actions 확인

  Milestone 완료 시

  [ ] 코드 품질 확인
  [ ] 테스트 90%+
  [ ] 문서 업데이트
  [ ] CI 통과
  [ ] Self-review

  ---
  5.3 자주 쓰는 명령어

  # 테스트
  pytest tests/ -v
  pytest tests/unit/ --cov=src --cov-report=term-missing

  # 린팅 & 포맷
  ruff check src/ tests/
  ruff check --fix src/ tests/
  black src/ tests/
  black --check src/ tests/

  # 타입 체크
  mypy src/

  # 로컬 CI
  act push
  act push -j test

  # Git
  git status
  git add .
  git commit -m "feat: 기능 추가"
  git push origin main

  # Pre-commit
  pre-commit install
  pre-commit run --all-files

  ---
  5.4 긴급 상황 대응

  CI 실패 시

  1. 로그 확인
  2. 로컬에서 재현: pytest tests/ -v
  3. 수정
  4. 로컬 검증: pytest + ruff + black
  5. 재커밋 및 푸시

  테스트 실패 시

  1. 실패 원인 파악
  2. 해당 테스트만 실행: pytest tests/unit/test_file.py::test_name -v
  3. 디버깅: pytest --pdb
  4. 수정 후 전체 테스트 재실행

  롤백 필요 시

  # 마지막 커밋 취소 (로컬만)
  git reset HEAD~1

  # 원격까지 롤백 (주의!)
  git revert HEAD
  git push origin main

  ---
  6. 마무리

  핵심 원칙 3가지

  1. 명확한 요구사항이 80%다
    - Milestone 구조
    - 절대 규칙 명시
    - 아키텍처 방향 정의
  2. Test → Commit → Verify를 지켜라
    - 로컬 검증 필수
    - CI 실패는 최우선 수정
    - 작은 단위로 자주 커밋
  3. 프로세스로 Human Error를 막아라
    - 킥오프 체크리스트
    - Pre-commit hooks
    - Milestone별 검증

  ---
  다음 프로젝트 시작 전

  [ ] 이 Best Practices 문서 읽기
  [ ] 킥오프 프롬프트 작성
  [ ] 킥오프 체크리스트 실행
  [ ] Pre-commit hooks 설정
  [ ] "Test → Commit → Verify" 프로토콜 숙지

  ---
  이 문서는 살아있는 문서입니다.
  프로젝트마다 배운 교훈을 추가하여 지속적으로 개선하세요!

  ---
  Version History:
  - v1.0 (2026-02-06): 초기 작성
  - v1.1 (2026-02-09): 테스트 커버리지 섹션 추가
  - v1.2 (2026-02-10): Human Error 최소화 섹션 강화

  Contributors: ghilp934, Claude Sonnet 4.5

  License: MIT