"""Offline tests: data minimisation, deletion handling and purge. No network access."""
import os, tempfile, unittest
import reddit_reader as rr


class ReaderTest(unittest.TestCase):
    def test_minimal_drops_usernames(self):
        row = rr.minimal("comment", {"name": "t1_abc", "subreddit": "hobbycnc", "created_utc": 1791000000.0,
                                     "body": "The Z1 cut 6061 fine.", "score": 4, "link_id": "t3_x1",
                                     "author": "some_user"})
        self.assertNotIn("author", row)
        self.assertEqual(row["is_official"], 0)
        self.assertEqual(row["text"], "The Z1 cut 6061 fine.")

    def test_official_account_flagged(self):
        row = rr.minimal("post", {"name": "t3_p1", "title": "Studio update", "selftext": "", "author": "makera_offical"})
        self.assertEqual(row["is_official"], 1)

    def test_deleted_and_removed_detected(self):
        self.assertTrue(rr.is_gone({"name": "t1_a", "author": "[deleted]", "body": "x"}))
        self.assertTrue(rr.is_gone({"name": "t1_b", "author": "u", "body": "[removed]"}))
        self.assertTrue(rr.is_gone({"name": "t3_c", "author": "u", "selftext": "", "removed_by_category": "moderator"}))
        self.assertFalse(rr.is_gone({"name": "t3_d", "author": "u", "selftext": "My first PCB"}))

    def test_walk_skips_deleted_and_more(self):
        tree = [{"kind": "t1", "data": {"name": "t1_1", "author": "a", "body": "ok", "replies": {"data": {"children": [
                    {"kind": "t1", "data": {"name": "t1_2", "author": "[deleted]", "body": "[deleted]", "replies": ""}},
                    {"kind": "more", "data": {}}]}}}}]
        out = []
        rr.walk(tree, out)
        self.assertEqual([r["id"] for r in out], ["t1_1"])

    def test_purge_removes_dataset(self):
        with tempfile.TemporaryDirectory() as d:
            rr.DB = os.path.join(d, "data", "study.sqlite")
            con = rr.db()
            rr.save(con, [rr.minimal("post", {"name": "t3_z", "title": "t", "selftext": "s", "author": "u"})])
            con.close()
            rr.purge()
            self.assertFalse(os.path.exists(rr.DB))


if __name__ == "__main__":
    unittest.main()
