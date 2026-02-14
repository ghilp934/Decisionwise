"""
Rename Decisionproof → Decisionproof across entire project
"""
import os
import re
from pathlib import Path

# Base directory
BASE_DIR = Path(r"C:\Users\ghilp\OneDrive\바탕 화면\배성무일반\0_디플런트 D!FFERENT\Decisionproof\decisionproof_api_platform")

# File extensions to process
EXTENSIONS = ['.md', '.py', '.txt', '.json', '.yaml', '.yml', '.toml', '.cfg', '.ini', '.sh']

# Files to skip (binary, large, etc)
SKIP_PATTERNS = [
    '.git/',
    '__pycache__/',
    '.pytest_cache/',
    'node_modules/',
    '.next/',
    'venv/',
    'env/',
    '.egg-info/',
    'dist/',
    'build/',
]

def should_skip(filepath):
    """Check if file should be skipped"""
    path_str = str(filepath)
    for pattern in SKIP_PATTERNS:
        if pattern in path_str:
            return True
    return False

def find_files_with_decisionproof():
    """Find all files containing 'Decisionproof'"""
    files_found = []

    for root, dirs, files in os.walk(BASE_DIR):
        # Skip certain directories
        if should_skip(root):
            continue

        for file in files:
            filepath = Path(root) / file

            # Check extension
            if filepath.suffix not in EXTENSIONS:
                continue

            # Check if file contains "Decisionproof"
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'Decisionproof' in content or 'decisionproof' in content:
                        count = content.count('Decisionproof') + content.count('decisionproof')
                        files_found.append((filepath, count))
            except Exception as e:
                print(f"[SKIP] {filepath}: {e}")

    return files_found

def replace_in_file(filepath):
    """Replace Decisionproof → Decisionproof in file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Replace variations
        content = content.replace('Decisionproof', 'Decisionproof')
        content = content.replace('decisionproof', 'decisionproof')
        content = content.replace('DECISIONPROOF', 'DECISIONPROOF')

        # Also handle URLs
        content = content.replace('api.decisionproof.ai', 'api.decisionproof.ai')  # Already correct
        content = content.replace('auth.decisionproof.ai', 'auth.decisionproof.ai')  # Already correct

        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False

    except Exception as e:
        print(f"[ERROR] {filepath}: {e}")
        return False

if __name__ == '__main__':
    print("=== Decisionproof → Decisionproof Rename ===\n")

    print("1. Finding files...")
    files = find_files_with_decisionproof()

    print(f"   Found {len(files)} files with 'Decisionproof'\n")

    # Group by type
    readme_files = [f for f, c in files if f.name == 'README.md']
    doc_files = [f for f, c in files if f.suffix == '.md' and f.name != 'README.md']
    code_files = [f for f, c in files if f.suffix in ['.py', '.json', '.yaml', '.yml']]
    other_files = [f for f, c in files if f not in readme_files and f not in doc_files and f not in code_files]

    print(f"   README.md files: {len(readme_files)}")
    print(f"   Other .md files: {len(doc_files)}")
    print(f"   Code files: {len(code_files)}")
    print(f"   Other files: {len(other_files)}\n")

    print("2. Processing files...")

    processed = 0

    # Process README files first
    for filepath in readme_files:
        if replace_in_file(filepath):
            print(f"   [OK] {filepath.relative_to(BASE_DIR)}")
            processed += 1

    # Process other docs
    for filepath in doc_files:
        if replace_in_file(filepath):
            print(f"   [OK] {filepath.relative_to(BASE_DIR)}")
            processed += 1

    # Process code files
    for filepath in code_files:
        if replace_in_file(filepath):
            print(f"   [OK] {filepath.relative_to(BASE_DIR)}")
            processed += 1

    # Process other files
    for filepath in other_files:
        if replace_in_file(filepath):
            print(f"   [OK] {filepath.relative_to(BASE_DIR)}")
            processed += 1

    print(f"\n=== Complete ===")
    print(f"Processed {processed} files")
