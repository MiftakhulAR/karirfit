import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from e5_numpy import cpu_quota_threads, blas_threads

class CpuBudgetTests(unittest.TestCase):
    def test_cgroup_v2_fractional_and_unlimited(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.assertIsNone(cpu_quota_threads(root))
            (root/'cpu.max').write_text('10000 100000')
            self.assertEqual(cpu_quota_threads(root),1)
            (root/'cpu.max').write_text('250000 100000')
            self.assertEqual(cpu_quota_threads(root),3)
            (root/'cpu.max').write_text('max 100000')
            self.assertIsNone(cpu_quota_threads(root))
            (root/'cpu.max').write_text('invalid')
            self.assertIsNone(cpu_quota_threads(root))

    def test_cgroup_v1(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'cpu').mkdir()
            (root/'cpu/cpu.cfs_quota_us').write_text('50000')
            (root/'cpu/cpu.cfs_period_us').write_text('100000')
            self.assertEqual(cpu_quota_threads(root),1)
            (root/'cpu/cpu.cfs_quota_us').write_text('-1')
            self.assertIsNone(cpu_quota_threads(root))

    def test_explicit_override_and_validation(self):
        for value, expected in [('native',None),('0',None),('1',1),('2',2)]:
            with patch.dict(os.environ,{'E5_BLAS_THREADS':value}):
                self.assertEqual(blas_threads(),expected)
        for value in ['-1','65','typo']:
            with patch.dict(os.environ,{'E5_BLAS_THREADS':value}):
                with self.assertRaises(ValueError): blas_threads()

if __name__=='__main__': unittest.main()
