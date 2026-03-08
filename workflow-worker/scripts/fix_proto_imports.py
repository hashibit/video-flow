#!/usr/bin/env python3
"""
Fix proto file imports to use relative imports
"""
import os
import re

def fix_proto_imports(file_path):
    """Fix imports in a generated proto file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Fix imports like: import base_pb2 as xxx
        # to: from . import base_pb2 as xxx
        content = re.sub(
            r'^import ([\w_]+_pb2) as ',
            r'from . import \1 as ',
            content,
            flags=re.MULTILINE
        )

        # Fix from engine.protos imports if any
        content = re.sub(
            r'from engine\.protos import',
            r'from . import',
            content
        )

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
    proto_dir = "src/workflow_worker/domain/entities/proto"

    print("🔄 Fixing proto file imports...")
    print()

    count = 0
    for file in os.listdir(proto_dir):
        if file.endswith('_pb2.py') or file.endswith('_pb2_grpc.py'):
            file_path = os.path.join(proto_dir, file)
            if fix_proto_imports(file_path):
                count += 1
                print(f"  ✅ {file}")

    print()
    print("=" * 50)
    print(f"📊 Fixed {count} proto files")
    print("=" * 50)

if __name__ == "__main__":
    main()
