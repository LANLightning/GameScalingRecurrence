"""State guard prototype: no game attachment, memory reads or real input.
Adapter calls are serialized on the game simulation thread. External SendInput
cannot make the final check+action atomic. Times are adapter monotonic seconds.
"""
from dataclasses import dataclass, asdict
from collections import deque
import json
import math

@dataclass(frozen=True)
class Entity:
    uid: str
    generation: int
    lifecycle: str = 'alive'
    targetable: bool = True
    damageable: bool = True
    line_of_sight: bool = True
    distance: float = 2.0

@dataclass(frozen=True)
class Snapshot:
    instance: str
    world: str
    epoch: int
    seq: int
    sampled_at: float
    entities: tuple[Entity, ...]
    authoritative: bool = True
    player_alive: bool = True
    controls_available: bool = True

@dataclass(frozen=True)
class AttackIntent:
    token: str
    instance: str
    world: str
    epoch: int
    observed_seq: int
    target: str
    generation: int
    expires_at: float

class Guard:
    """Pending writes, deterministic assertions, budget, recorder, binding.
    One short attack lease. No GC/delete operation. Adapter owns timing,
    identity, authority, range. Replay uses a dummy actuator by default.
    """
    def __init__(self, instance='game-A', world='world-A', freshness=.15,
                 reach=3.0, budget=3, max_lease=.2):
        self.instance, self.world = instance, world
        self.freshness, self.reach, self.max_lease = freshness, reach, max_lease
        self.limit = budget
        self.budget = budget
        self.snapshot = None
        self.needs_resync = True
        self.active = None
        self.pending = {}
        self.retired = deque(maxlen=2048)
        self.records = deque(maxlen=2048)
        self.effects = deque(maxlen=2048)

    def record(self, event, **fields):
        self.records.append(dict(event=event, **fields))

    def stop(self, reason):
        if self.active:
            token = self.active.token
            self.effects.append(dict(action='release_attack', token=token))
            self.record('cancelled', token=token, reason=reason)
            self.pending.pop(token, None)
            self.retired.append(token)
            self.active = None

    def ingest(self, sample, now, resync=False):
        """Full snapshots. A gap requires explicit fresh authoritative resync.
        Resync flag must be set by a trusted adapter after a new full sample;
        it must not be attached to a cached or partial transport packet.
        """
        if (sample.instance, sample.world) != (self.instance, self.world):
            self.record('ignored_foreign_snapshot')
            return False
        if not math.isfinite(sample.sampled_at) or sample.sampled_at > now:
            self.needs_resync = True
            self.stop('invalid_sample_time')
            return False
        ids = [e.uid for e in sample.entities]
        if len(ids) != len(set(ids)):
            self.needs_resync = True
            self.stop('duplicate_identity')
            return False
        old = self.snapshot
        if old and sample.epoch < old.epoch:
            self.record('ignored_old_epoch')
            return False
        if old and sample.epoch == old.epoch and sample.seq <= old.seq:
            self.record('ignored_out_of_order', seq=sample.seq)
            return False
        changed_epoch = old is not None and sample.epoch != old.epoch
        gap = old is not None and not changed_epoch and sample.seq != old.seq + 1
        if changed_epoch or gap:
            self.needs_resync = True
            self.stop('source_restarted' if changed_epoch else 'sequence_gap')
        self.snapshot = sample
        if resync and sample.authoritative and 0 <= now-sample.sampled_at <= self.freshness:
            self.needs_resync = False
        self.record('snapshot', snapshot=asdict(sample), resync=resync)
        if self.active:
            reason = self.check(self.active, now)
            if reason:
                self.stop(reason)
        return True

    def check(self, intent, now):
        s = self.snapshot
        if (intent.instance, intent.world) != (self.instance, self.world):
            return 'binding_mismatch'
        if s is None or self.needs_resync:
            return 'resync_required'
        if intent.epoch != s.epoch:
            return 'source_epoch_changed'
        if intent.observed_seq > s.seq:
            return 'future_observation'
        if not math.isfinite(intent.expires_at) or now >= intent.expires_at:
            return 'lease_expired'
        if now < s.sampled_at or now-s.sampled_at > self.freshness:
            return 'stale_snapshot'
        if not s.authoritative:
            return 'unverified_source'
        if not s.player_alive or not s.controls_available:
            return 'player_unavailable'
        e = next((e for e in s.entities if e.uid == intent.target), None)
        if e is None:
            return 'target_missing'
        if e.generation != intent.generation:
            return 'target_reused'
        if e.lifecycle != 'alive':
            return 'target_' + e.lifecycle
        if not e.targetable or not e.damageable:
            return 'target_ineligible'
        if not e.line_of_sight:
            return 'occluded'
        if not math.isfinite(e.distance) or not 0 <= e.distance <= self.reach:
            return 'out_of_range'
        return None

    def submit(self, intent, now):
        if intent.token in self.retired or intent.token in self.pending:
            self.record('rejected', token=intent.token, reason='duplicate_token')
            return False
        reason = self.check(intent, now)
        if not reason and intent.expires_at-now > self.max_lease:
            reason = 'lease_too_long'
        if not reason and self.active:
            reason = 'previous_write_pending'
        if not reason and self.budget <= 0:
            reason = 'verification_budget_exhausted'
        if reason:
            self.record('rejected', token=intent.token, reason=reason)
            return False
        self.budget -= 1
        self.active = intent
        self.pending[intent.token] = dict(status='pending_observation', seq=self.snapshot.seq)
        self.record('accepted', intent=asdict(intent))
        return True

    def pulse(self, now):
        """Recheck each simulation step, including while model generation waits."""
        if self.active is None:
            return False
        reason = self.check(self.active, now)
        if reason:
            self.stop(reason)
            return False
        self.effects.append(dict(action='attack_pulse', token=self.active.token,
                                 target=self.active.target, generation=self.active.generation))
        self.record('executed', token=self.active.token, seq=self.snapshot.seq)
        return True

    def hard_verify(self, intent, now):
        """Failed assertion does not refill the execution budget."""
        reason = self.check(intent, now)
        passed = reason is None
        self.record('assertion', passed=passed, reason=reason)
        if passed:
            self.budget = self.limit
        return passed

    def terminal_evidence(self, target, generation, now):
        """Nonattackability, kill credit, and deallocation are separate facts."""
        s = self.snapshot
        if (not s or self.needs_resync or not s.authoritative or
                not 0 <= now-s.sampled_at <= self.freshness):
            return {'confirmed': False, 'reason': 'no_current_evidence'}
        e = next((e for e in s.entities if e.uid == target and e.generation == generation), None)
        if e is None:
            return {'confirmed': False, 'reason': 'missing_is_not_proof_of_death'}
        return {'confirmed': e.lifecycle in ('dead', 'pooled', 'despawned'),
                'memory_present': True, 'kill_credit': 'unknown', 'seq': s.seq}

    def export(self, path):
        with open(path, 'w', encoding='utf8') as f:
            for row in self.records:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')

class IntentFrames:
    """Proposed supervisor NDJSON; NOT GameScaling's existing action grammar.
    Only complete committed records are candidates for validation. A partial
    token, reasoning fragment or speculative draft cannot drive input.
    """
    def __init__(self):
        self.buffer = ''

    def feed(self, text):
        self.buffer += text
        if len(self.buffer) > 8192:
            self.buffer = ''
            raise ValueError('Intent frame exceeds limit')
        ready = []
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            item = json.loads(line)
            if not isinstance(item, dict) or item.get('type') != 'intent':
                raise ValueError('Expected complete intent record')
            ready.append(item)
        return ready
