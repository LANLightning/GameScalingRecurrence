"""Behavioral tests with synthetic game states. Does not launch Minecraft."""
import json
import unittest
from dataclasses import replace
from pathlib import Path
from state_guard import Guard, Entity, Snapshot, AttackIntent, IntentFrames

ROOT = Path(__file__).resolve().parent

def sample(seq=1, at=0., entity=None, **kw):
    return Snapshot('game-A', 'world-A', 1, seq, at,
                    (entity or Entity('mob-7', 1),), **kw)

def intent(token='decision-1', **kw):
    data = dict(token=token, instance='game-A', world='world-A', epoch=1,
                observed_seq=1, target='mob-7', generation=1, expires_at=.2)
    data.update(kw)
    return AttackIntent(**data)

class Scenarios(unittest.TestCase):
    def setUp(self):
        self.g = Guard()
        self.g.ingest(sample(), 0., resync=True)

    def start(self):
        self.assertTrue(self.g.submit(intent(), 0.))
        self.assertTrue(self.g.pulse(0.))

    def no_more_attack(self, now):
        before = sum(x['action']=='attack_pulse' for x in self.g.effects)
        self.assertFalse(self.g.pulse(now))
        self.assertEqual(before, sum(x['action']=='attack_pulse' for x in self.g.effects))

    def test_death_during_generation_rejects_late_intent(self):
        self.g.ingest(sample(2, .05, Entity('mob-7', 1, lifecycle='dead')), .05)
        self.assertFalse(self.g.submit(intent(), .06))
        self.assertEqual(len(self.g.effects), 0)

    def test_death_interrupts_existing_lease_before_next_step(self):
        self.start()
        self.g.ingest(sample(2, .01, Entity('mob-7', 1, lifecycle='dead')), .01)
        self.assertEqual(self.g.effects[-1]['action'], 'release_attack')
        self.no_more_attack(.011)
        self.g.export(ROOT/'state-guard-example.jsonl')

    def test_pooled_object_still_allocated_is_not_attackable(self):
        self.start()
        self.g.ingest(sample(2, .01, Entity('mob-7', 1, lifecycle='pooled')), .01)
        self.no_more_attack(.02)
        evidence = self.g.terminal_evidence('mob-7', 1, .02)
        self.assertTrue(evidence['confirmed'])
        self.assertTrue(evidence['memory_present'])
        self.assertEqual(evidence['kill_credit'], 'unknown')

    def test_non_targetable_ghost_even_without_death_flag(self):
        self.start()
        self.g.ingest(sample(2, .01, Entity('mob-7', 1, targetable=False)), .01)
        self.no_more_attack(.02)
        self.assertFalse(self.g.terminal_evidence('mob-7', 1, .02)['confirmed'])

    def test_recycled_entity_id_requires_new_generation_intent(self):
        self.start()
        self.g.ingest(sample(2, .01, Entity('mob-7', 2)), .01)
        self.no_more_attack(.02)
        self.assertFalse(self.g.submit(intent('old'), .02))
        self.assertTrue(self.g.submit(intent('new', generation=2, observed_seq=2), .02))

    def test_out_of_order_alive_packet_cannot_undo_death(self):
        self.g.ingest(sample(2, .01, Entity('mob-7', 1, lifecycle='dead')), .01)
        self.assertFalse(self.g.ingest(sample(), .02))
        self.assertFalse(self.g.submit(intent(), .02))

    def test_sequence_gap_stops_until_full_resync(self):
        self.start()
        self.g.ingest(sample(3, .01), .01)
        self.no_more_attack(.02)
        self.assertFalse(self.g.submit(intent('next'), .02))
        self.g.ingest(sample(4, .03), .03, resync=True)
        self.assertTrue(self.g.submit(intent('next'), .03))

    def test_source_restart_invalidates_old_plan(self):
        self.start()
        self.g.ingest(replace(sample(1, .01), epoch=2), .01, resync=True)
        self.no_more_attack(.02)
        self.assertFalse(self.g.submit(intent('old'), .02))
        self.assertTrue(self.g.submit(intent('new', epoch=2), .02))

    def test_disconnect_or_stalled_source_expires_even_without_events(self):
        self.start()
        self.no_more_attack(.16)
        self.assertEqual(self.g.records[-1]['reason'], 'stale_snapshot')

    def test_lease_expires_despite_fresh_samples(self):
        self.start()
        self.g.ingest(sample(2, .19), .19)
        self.no_more_attack(.201)
        self.assertEqual(self.g.records[-1]['reason'], 'lease_expired')

    def test_wrong_instance_cannot_drive_bound_game(self):
        self.assertFalse(self.g.submit(intent(instance='game-B'), .01))
        self.assertFalse(self.g.ingest(replace(sample(2, .01), instance='game-B'), .01))
        self.assertEqual(self.g.snapshot.seq, 1)

    def test_unrelated_world_change_does_not_restart_valid_action(self):
        self.start()
        s = sample(2, .01)
        self.g.ingest(replace(s, entities=s.entities + (Entity('tree-9', 1),)), .01)
        self.assertTrue(self.g.pulse(.02))

    def test_range_and_visibility_checked_on_each_step(self):
        for delta in [dict(distance=8.), dict(line_of_sight=False), dict(distance=float('nan'))]:
            g = Guard()
            g.ingest(sample(), 0., resync=True)
            self.assertTrue(g.submit(intent(), 0.))
            g.ingest(sample(2, .01, replace(Entity('mob-7', 1), **delta)), .01)
            self.assertFalse(g.pulse(.02))

    def test_prediction_without_authority_is_insufficient(self):
        self.start()
        self.g.ingest(sample(2, .01, authoritative=False), .01)
        self.no_more_attack(.02)

    def test_pending_and_duplicate_actions_do_not_double_execute(self):
        self.start()
        self.assertFalse(self.g.submit(intent(), .01))
        self.assertFalse(self.g.submit(intent('second'), .01))
        self.g.stop('manual_cancel')
        self.assertFalse(self.g.submit(intent(), .02))
        self.assertEqual(self.g.pending, {})

    def test_failed_assertion_does_not_restore_budget(self):
        g = Guard(budget=1)
        g.ingest(sample(), 0., resync=True)
        self.assertTrue(g.submit(intent(), 0.))
        g.stop('step_finished')
        self.assertFalse(g.hard_verify(intent(target='not-present'), .01))
        self.assertEqual(g.budget, 0)
        self.assertFalse(g.submit(intent('new'), .01))
        self.assertTrue(g.hard_verify(intent('new'), .01))
        self.assertTrue(g.submit(intent('new'), .01))

    def test_missing_entity_is_not_automatically_confirmed_kill(self):
        self.start()
        self.g.ingest(replace(sample(2, .01), entities=()), .01)
        self.no_more_attack(.02)
        self.assertFalse(self.g.terminal_evidence('mob-7', 1, .02)['confirmed'])

    def test_complete_intermediate_record_can_precede_final_response(self):
        decoder = IntentFrames()
        self.assertEqual(decoder.feed('{"type":"intent","target":'), [])
        ready = decoder.feed('"mob-7"}\n{"type":')
        self.assertEqual(ready, [{'type':'intent', 'target':'mob-7'}])
        self.assertEqual(decoder.buffer, '{"type":')

    def test_player_death_and_menu_cancel_attack(self):
        for flags in [dict(player_alive=False), dict(controls_available=False)]:
            g = Guard()
            g.ingest(sample(), 0., resync=True)
            g.submit(intent(), 0.)
            g.ingest(sample(2, .01, **flags), .01)
            self.assertFalse(g.pulse(.02))

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Scenarios)
    names = [t.id() for t in suite]
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = dict(scope='synthetic state-machine validation; no live Minecraft, no real input',
                  tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                  passed=result.wasSuccessful(), scenarios=names)
    (ROOT/'state-guard-test-results.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    raise SystemExit(0 if result.wasSuccessful() else 1)
