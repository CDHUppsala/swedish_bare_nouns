"""
test_engine.py - Unit and integration tests for Grew search engine.
"""

import os
import unittest
import engine


class TestEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine.init_backend()
        cls.files = engine.discover_corpus_files("data")

    def test_corpus_discovery(self):
        self.assertGreater(len(self.files), 0)
        self.assertTrue(all(f.endswith(".conllu") for f in self.files))

    def test_single_corpus_search(self):
        query = 'pattern { V [xpos="VB"]; N [xpos="NN"]; V -[SS]-> N; }'
        matches, total_sents = engine.search_single_corpus(
            self.files[0], query, extract_sentence_text=True, max_matches=5
        )
        self.assertEqual(len(matches), 5)
        self.assertGreater(total_sents, 0)
        first = matches[0]
        self.assertIn("chunk", first)
        self.assertIn("sent_id", first)
        self.assertIn("sentence_text", first)
        self.assertIn("matched_tokens", first)
        self.assertIn("V", first["matched_tokens"])
        self.assertIn("N", first["matched_tokens"])

    def test_iterate_corpora_search(self):
        query = 'pattern { V [xpos="VB"]; N [xpos="NN"]; V -[SS]-> N; }'
        subset = self.files[:3]
        results = list(engine.iterate_corpora_search(subset, query, extract_sentence_text=False))
        self.assertEqual(len(results), 3)
        for res in results:
            self.assertIn("chunk", res)
            self.assertIn("matches_count", res)
            self.assertGreater(res["matches_count"], 0)
            self.assertEqual(res["sentences_count"], 1000)

    def test_unified_dataset_search(self):
        query = 'pattern { V [xpos="VB"]; N [xpos="NN"]; V -[SS]-> N; }'
        subset = self.files[:3]
        res = engine.search_unified_dataset(subset, query, max_display_matches=10)
        self.assertEqual(res["total_files"], 3)
        self.assertEqual(res["total_sentences"], 3000)
        self.assertEqual(res["total_matches"], 1952)
        self.assertEqual(len(res["sample_matches"]), 10)
        self.assertEqual(len(res["chunk_stats"]), 3)


if __name__ == "__main__":
    unittest.main()
