import sys, threading, unittest
from pathlib import Path
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rag import Retriever

class CacheTests(unittest.TestCase):
    def make(self, limit=2):
        r=Retriever.__new__(Retriever)
        r._query_cache=OrderedDict(); r._cache_lock=threading.Lock()
        r._cache_limit=limit; r._cache_ttl=900
        r._cache_hits=r._cache_misses=0
        class Encoder:
            calls=0
            def encode(self, text, prefix):
                self.calls+=1
                return np.array([[len(text[0]),1]],dtype=np.float32)
        r.encoder=Encoder()
        return r
    def test_repeat_concurrent_and_bound(self):
        r=self.make()
        with ThreadPoolExecutor(4) as ex:
            vectors=list(ex.map(r._query_vector,['same']*8))
        self.assertEqual(r.encoder.calls,1)
        self.assertTrue(all(np.array_equal(v,vectors[0]) for v in vectors))
        r._query_vector('second'); r._query_vector('third')
        self.assertEqual(len(r._query_cache),2)
        r._query_vector('same'); self.assertEqual(r.encoder.calls,4)
        self.assertTrue(all(isinstance(k,bytes) for k in r._query_cache))
    def test_expiry_and_disable(self):
        r=self.make(); r._query_vector('same')
        r._cache_ttl=0; r._query_vector('same')
        self.assertEqual(r.encoder.calls,2)
        r=self.make(0); r._query_vector('x'); r._query_vector('x')
        self.assertEqual(r.encoder.calls,2)


if __name__ == '__main__': unittest.main()
