#!/usr/bin/env python3
"""
Fix old import paths from engine, framework, apis to new DDD structure
"""
import os
import re

def fix_file(file_path):
    """Fix old imports in a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Fix logging imports
        content = re.sub(
            r'from engine import logging',
            'from workflow_worker.shared.logging import get_logger',
            content
        )

        # Fix engine.tasks.person_tracking.processor
        content = re.sub(
            r'from engine\.tasks\.person_tracking\.processor import PersonTrackingProcessor',
            'from workflow_worker.applications.jobs.person_tracking.processor import PersonTrackingProcessor',
            content
        )

        # Fix engine.tasks.base.reporter
        content = re.sub(
            r'from engine\.tasks\.base\.reporter import Reporter',
            'from workflow_worker.applications.jobs.base.reporter import Reporter',
            content
        )

        # Fix engine.tasks.common.ocr.*
        content = re.sub(
            r'from engine\.tasks\.common\.ocr\.ocr_id_generator import',
            'from workflow_worker.applications.jobs.common.ocr.ocr_id_generator import',
            content
        )

        content = re.sub(
            r'from engine\.tasks\.common\.ocr\.ocr_info_manager import',
            'from workflow_worker.applications.jobs.common.ocr.ocr_info_manager import',
            content
        )

        # Fix engine.tasks.subtitle_matching.diff
        content = re.sub(
            r'from engine\.tasks\.subtitle_matching\.diff import diff_match_patch',
            'from workflow_worker.applications.jobs.subtitle_matching.diff import diff_match_patch',
            content
        )

        # Fix engine.protos.* imports
        content = re.sub(
            r'from engine\.protos import ([\w_]+)',
            r'from workflow_worker.domain.entities.proto.\1',
            content
        )

        # Fix any remaining engine.protos.*
        content = re.sub(
            r'from engine\.protos\.([\w_]+) import',
            r'from workflow_worker.domain.entities.proto.\1 import',
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
    import sys

    print("🔄 Fixing old import paths...")
    print()

    count = 0
    for root, dirs, files in os.walk("src/"):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                if fix_file(file_path):
                    count += 1
                    print(f"  ✅ {file_path}")

    print()
    print("=" * 50)
    print(f"📊 Fixed {count} files")
    print("=" * 50)

if __name__ == "__main__":
    main()
