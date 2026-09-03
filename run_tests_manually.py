import pytest
import sys

if __name__ == "__main__":
    print("Running pytest suite...")
    sys.exit(pytest.main(["Tests/test_csv_validation.py"]))
