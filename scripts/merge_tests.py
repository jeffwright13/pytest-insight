"""Script to merge and organize test files."""
import shutil
import os

def organize_tests():
    """Organize test files into appropriate categories."""
    moves = [
        # Unit tests
        ('tests-new/test_filters.py', 'tests/unit/test_filters.py'),
        ('tests-new/test_storage.py', 'tests/unit/test_storage.py'),
        ('tests-new/test_analyzer.py', 'tests/unit/test_analyzer.py'),

        # Integration tests
        ('tests-new/test_server.py', 'tests/integration/test_server.py'),
        ('tests-new/test_grafana.py', 'tests/integration/test_grafana.py'),

        # CLI tests
        ('tests-new/test_cli.py', 'tests/cli/test_commands.py'),
        ('tests-new/test_display.py', 'tests/cli/test_display.py'),

        # API tests
        ('tests-new/test_api.py', 'tests/api/test_endpoints.py'),
        ('tests-new/test_metrics.py', 'tests/api/test_metrics.py'),
    ]

    for src, dst in moves:
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            print(f"Moved {src} → {dst}")

if __name__ == "__main__":
    organize_tests()
