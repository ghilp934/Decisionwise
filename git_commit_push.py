"""Git commit and push renamed project"""
import subprocess
import os

# Change to project directory
os.chdir(r'C:\Users\ghilp\OneDrive\바탕 화면\배성무일반\0_디플런트 D!FFERENT\Decisionwise\decisionwise_api_platform')

print("=== Git Commit & Push ===\n")

# 1. Check status
print("1. Checking git status...")
result = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True)
print(result.stdout[:500])

# 2. Add all changes
print("\n2. Staging all changes...")
subprocess.run(['git', 'add', '-A'], check=True)
print("   [OK] All changes staged")

# 3. Commit
print("\n3. Committing changes...")
commit_message = """refactor: Rebrand Decisionwise → Decisionproof

## Changes

- Renamed all instances of "Decisionwise" to "Decisionproof"
- Updated 37 files across the project:
  - 1 README.md
  - 20 documentation files (.md)
  - 13 code files (.py, .json)
  - 3 other files (.txt)

## Files Modified

Documentation:
- README.md
- All docs/*.md files
- All public/docs/*.md files
- llms.txt, llms-full.txt

Code:
- apps/api/dpp_api/main.py
- apps/api/dpp_api/pricing/*.py
- apps/api/tests/unit/*.py
- pricing/fixtures/*.json

## URLs Updated

- API Base URL: api.decisionwise.ai → api.decisionproof.ai
- Auth URL: auth.decisionwise.ai → auth.decisionproof.ai
- Dashboard: app.decisionwise.ai → app.decisionproof.ai

## Git Remote

- Updated remote: https://github.com/ghilp934/Decisionproof

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
"""

result = subprocess.run(
    ['git', 'commit', '-m', commit_message],
    capture_output=True,
    text=True
)

if result.returncode == 0:
    print("   [OK] Committed successfully")
    print(result.stdout)
else:
    print("   [INFO]", result.stdout)
    print("   [INFO]", result.stderr)

# 4. Push
print("\n4. Pushing to GitHub...")
result = subprocess.run(
    ['git', 'push', 'origin', 'master'],
    capture_output=True,
    text=True
)

if result.returncode == 0:
    print("   [OK] Pushed successfully")
    print(result.stdout)
    print(result.stderr)  # Git push uses stderr for progress
else:
    print("   [ERROR] Push failed")
    print(result.stdout)
    print(result.stderr)

print("\n=== Complete ===")
