import subprocess
import sys

result = subprocess.run(
    [sys.executable, 'deep_quality_audit.py'],
    capture_output=True,
    text=True,
    cwd=r'C:\Users\ghilp\OneDrive\바탕 화면\배성무일반\0_디플런트 D!FFERENT\Decisionproof\decisionproof_api_platform\dpp'
)

print(result.stdout)
if result.stderr:
    # Filter out JSON logging
    for line in result.stderr.split('\n'):
        if not line.startswith('{"timestamp"'):
            print(line, file=sys.stderr)
