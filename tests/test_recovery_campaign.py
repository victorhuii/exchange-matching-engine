import unittest
from scripts.recovery_campaign import mixed_campaign,torn_tail_campaign


class RecoveryCampaignTests(unittest.TestCase):
    def test_mixed_restarts_snapshot_and_ack_boundaries(self):
        result=mixed_campaign(seeds=(3,17),count=90,interruptions=4)
        self.assertEqual(result['commands'],180)
        self.assertEqual(result['before_journal_exits']+result['after_journal_exits'],8)
        self.assertEqual(result['duplicate_retries'],24)
        self.assertGreater(result['before_journal_exits'],0);self.assertGreater(result['after_journal_exits'],0)
        self.assertGreater(result['post_ack_kills'],0);self.assertGreater(result['snapshots'],0)

    def test_every_byte_prefix_of_final_candidate_record(self):
        result=torn_tail_campaign()
        self.assertEqual(result['prefix_cuts_tested'],result['final_record_bytes']+1)
        self.assertTrue(result['all_repaired_or_deduplicated'])
