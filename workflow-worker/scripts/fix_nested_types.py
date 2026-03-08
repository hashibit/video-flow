#!/usr/bin/env python3
"""
Fix nested type annotations like list[List[X]] -> list[list[X]]
"""
import os
import re

def fix_nested_types(file_path):
    """Fix nested type annotations in a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Fix list[List[X]] -> list[list[X]]
        content = re.sub(r'\blist\[List\[', r'list[list[', content)

        # Fix list[Dict[X]] -> list[dict[X]]
        content = re.sub(r'\blist\[Dict\[', r'list[dict[', content)

        # Fix list[Tuple[X]] -> list[tuple[X]]
        content = re.sub(r'\blist\[Tuple\[', r'list[tuple[', content)

        # Fix dict[str, List[X]] -> dict[str, list[X]]
        content = re.sub(r'\bdict\[str, List\[', r'dict[str, list[', content)
        content = re.sub(r'\bdict\[str, Dict\[', r'dict[str, dict[', content)

        # Fix any remaining bare List/Dict/Tuple in type annotations
        # These should be caught by Python's parser
        content = re.sub(r':\s*List\[', ': list[', content)
        content = re.sub(r':\s*Dict\[', ': dict[', content)
        content = re.sub(r':\s*Tuple\[', ': tuple[', content)

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"❌ Failed to process {file_path}: {e}")
        return False

def main():
    """Main function"""
    print("🔄 Fixing nested type annotations...")
    print()

    count = 0
    for root, dirs, files in os.walk("src/"):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                if fix_nested_types(file_path):
                    count += 1
                    print(f"  ✅ {file_path}")

    if count == 0:
        print("  ℹ️  No nested type issues found")
    else:
        print()
        print("=" * 50)
        print(f"📊 Fixed {count} files")
        print("=" * 50)

if __name__ == "__main__":
    main()
