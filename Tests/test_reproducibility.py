"""
TestSphere AI — Dataset Generation Reproducibility Tests
Verifies that dataset generation with the same seed produces byte-for-byte identical CSV outputs.
"""
import hashlib
import sys
import tempfile
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Data_Generation.generate_dataset import generate_and_load


def test_dataset_reproducibility_byte_identical():
    """Generating with the same seed twice must produce byte-for-byte identical CSV files."""
    seed = 12345
    with tempfile.TemporaryDirectory() as dir_a, tempfile.TemporaryDirectory() as dir_b:
        path_a = Path(dir_a)
        path_b = Path(dir_b)

        # Run generation A
        res_a = generate_and_load(seed=seed, output_dir=path_a, load_db=False, verbose=False)

        # Run generation B
        res_b = generate_and_load(seed=seed, output_dir=path_b, load_db=False, verbose=False)

        assert res_a["tests"] == res_b["tests"] == 1000
        assert res_a["dependencies"] == res_b["dependencies"]
        assert res_a["failures"] == res_b["failures"]
        assert res_a["changes"] == res_b["changes"]
        assert res_a["ground_truth"] == res_b["ground_truth"]

        files_a = sorted([f.name for f in path_a.glob("*.csv")])
        files_b = sorted([f.name for f in path_b.glob("*.csv")])
        assert files_a == files_b
        assert len(files_a) == 6

        for filename in files_a:
            content_a = (path_a / filename).read_bytes()
            content_b = (path_b / filename).read_bytes()

            hash_a = hashlib.sha256(content_a).hexdigest()
            hash_b = hashlib.sha256(content_b).hexdigest()

            assert content_a == content_b, f"File {filename} differed between runs with seed {seed}"
            assert hash_a == hash_b, f"SHA256 mismatch for {filename}: {hash_a} != {hash_b}"
