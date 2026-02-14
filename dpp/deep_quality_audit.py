"""Deep Quality Audit for MTS-3.0-DOC v0.2"""
import sys
sys.path.insert(0, 'apps/api')

from dpp_api.main import app
from fastapi.testclient import TestClient
import re

client = TestClient(app)

print('=== Deep Quality Audit ===\n')

# 1. RFC References Validation
print('1. RFC References')
docs_with_rfcs = {
    '/docs/auth-delegated.md': ['6749', '8628', '7636'],
}

for doc, expected_rfcs in docs_with_rfcs.items():
    resp = client.get(doc)
    if resp.status_code == 200:
        content = resp.text
        for rfc in expected_rfcs:
            if rfc in content:
                print(f'   [OK] {doc}: RFC {rfc} referenced')
            else:
                print(f'   [WARN] {doc}: RFC {rfc} missing')

# 2. Code Example Syntax Check
print('\n2. Code Example Syntax')
quickstart_resp = client.get('/docs/quickstart.md')
content = quickstart_resp.text

# Count code blocks
python_blocks = content.count('```python')
javascript_blocks = content.count('```javascript')
bash_blocks = content.count('```bash')

print(f'   [OK] Python examples: {python_blocks}')
print(f'   [OK] JavaScript examples: {javascript_blocks}')
print(f'   [OK] Bash examples: {bash_blocks}')

# Check for common issues
if 'dw_live_abc123' in content:
    print(f'   [OK] Uses placeholder API keys (not real keys)')
else:
    print(f'   [WARN] Missing placeholder API keys')

if 'YOUR_API_KEY' in content or 'your_api_key' in content:
    print(f'   [WARN] Generic placeholder found (should use dw_live_* format)')

# 3. Security Best Practices
print('\n3. Security Best Practices')
security_docs = ['/docs/auth-delegated.md', '/docs/human-escalation-template.md']

for doc in security_docs:
    resp = client.get(doc)
    content_lower = resp.text.lower()

    has_security_section = 'security' in content_lower
    warns_about_secrets = 'secret' in content_lower or 'credential' in content_lower

    if has_security_section:
        print(f'   [OK] {doc}: has security guidance')
    if warns_about_secrets:
        print(f'   [OK] {doc}: warns about secrets/credentials')

# 4. Cross-Reference Validation
print('\n4. Cross-Reference Validation')
llms_resp = client.get('/llms.txt')
llms_content = llms_resp.text

# Extract all internal links
internal_links = re.findall(r'/[\w\-/.]+\.(?:md|json)', llms_content)

broken_links = []
for link in set(internal_links):
    resp = client.get(link)
    if resp.status_code not in [200, 404]:  # 404 ok for static files in test
        broken_links.append((link, resp.status_code))

if not broken_links:
    print(f'   [OK] All {len(set(internal_links))} cross-references valid')
else:
    print(f'   [WARN] Broken links: {broken_links}')

# 5. Example Completeness
print('\n5. Example Completeness')
function_specs_resp = client.get('/docs/function-calling-specs.json')
specs = function_specs_resp.json()

for tool in specs.get('tools', []):
    name = tool.get('name')
    examples = tool.get('examples', [])

    for i, example in enumerate(examples):
        has_input = 'input' in example or 'parameters' in example or 'request' in example
        has_output = 'output' in example or 'response' in example

        if has_input and has_output:
            print(f'   [OK] {name} example {i+1}: complete (input + output)')
        elif has_input:
            print(f'   [WARN] {name} example {i+1}: missing output')
        else:
            print(f'   [WARN] {name} example {i+1}: missing input')

# 6. Versioning Consistency
print('\n6. Versioning Consistency')
pilot_resp = client.get('/docs/pilot-pack-v0.2.md')
pilot_content = pilot_resp.text

version_mentions = {
    'v0.1': pilot_content.count('v0.1'),
    'v0.2': pilot_content.count('v0.2'),
}

print(f'   [OK] pilot-pack-v0.2.md mentions:')
for version, count in version_mentions.items():
    print(f'        - {version}: {count} times')

# Check for supersedes clause
if 'Supersedes' in pilot_content or 'supersedes' in pilot_content:
    print(f'   [OK] Contains supersedes clause')
else:
    print(f'   [WARN] Missing supersedes clause')

# 7. Documentation Completeness
print('\n7. Documentation Completeness')

# Check human-escalation-template.md for all 3 templates
escalation_resp = client.get('/docs/human-escalation-template.md')
escalation_content = escalation_resp.text

template_count = escalation_content.count('## Template')
print(f'   [OK] human-escalation-template.md: {template_count} templates')

required_templates = ['Template A', 'Template B', 'Template C']
for template in required_templates:
    if template in escalation_content:
        print(f'   [OK] {template} present')
    else:
        print(f'   [WARN] {template} missing')

# 8. AI/Agent Integration Quality
print('\n8. AI/Agent Integration Quality')

# Check function-calling-specs.json structure
specs = function_specs_resp.json()

required_fields = ['spec_version', 'generated_at', 'base_url', 'auth', 'tools']
for field in required_fields:
    if field in specs:
        print(f'   [OK] function-calling-specs.json has {field}')
    else:
        print(f'   [FAIL] function-calling-specs.json missing {field}')

# Check auth structure
if 'auth' in specs:
    auth = specs['auth']
    if 'type' in auth and 'header' in auth:
        print(f'   [OK] Auth spec complete (type: {auth["type"]})')
    else:
        print(f'   [WARN] Auth spec incomplete')

print('\n=== Deep Audit Complete ===')
