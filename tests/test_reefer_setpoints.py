import unittest
from datetime import datetime,timezone
from coldledger.reefer.setpoints import (Instruction,decide,at,replay,
                                        OnConflict,InstructionConflict)
UTC=timezone.utc
def t(h): return datetime(2026,10,1,h,tzinfo=UTC)
class ReeferSetpointTests(unittest.TestCase):
    def test_new_revision_wins_regardless_of_input_order(self):
        # Old revision entered after the revised one must not override it.
        old=Instruction(t(8),t(20),5.0,priority=1,revision=1)
        new=Instruction(t(8),t(20),2.0,priority=1,revision=2)
        self.assertEqual(at([new,old],t(12)),2.0)
        self.assertEqual(at([old,new],t(12)),2.0)
        self.assertEqual(at([new,old],t(12),OnConflict.REJECT),2.0)
    def test_old_revision_starting_later_still_loses(self):
        # The original bug: start time outranked revision.
        old=Instruction(t(10),t(20),5.0,priority=1,revision=1)
        new=Instruction(t(8),t(20),2.0,priority=1,revision=2)
        self.assertEqual(at([old,new],t(12)),2.0)
    def test_priority_outranks_revision(self):
        hi_old=Instruction(t(8),t(20),4.0,priority=2,revision=1)
        lo_new=Instruction(t(8),t(20),2.0,priority=1,revision=9)
        self.assertEqual(at([lo_new,hi_old],t(12)),4.0)
    def test_later_activation_wins_on_equal_revision(self):
        a=Instruction(t(8),t(20),5.0,priority=1,revision=1)
        b=Instruction(t(9),t(20),3.0,priority=1,revision=1)
        self.assertEqual(at([a,b],t(12)),3.0)
    def test_tighter_tolerance_wins(self):
        loose=Instruction(t(8),t(20),3.0,priority=1,revision=1,tolerance=2.0)
        tight=Instruction(t(8),t(20),3.0,priority=1,revision=1,tolerance=0.5)
        d=decide([loose,tight],t(12))
        self.assertEqual(d.winner.tolerance,0.5)
        self.assertFalse(d.conflict)
    def test_reject_policy_raises_on_true_conflict(self):
        a=Instruction(t(8),t(20),5.0,priority=1,revision=1,received=1)
        b=Instruction(t(8),t(20),2.0,priority=1,revision=1,received=1)
        with self.assertRaises(InstructionConflict) as cm:
            decide([a,b],t(12),OnConflict.REJECT)
        self.assertTrue(cm.exception.decision.conflict)
        self.assertEqual(set(c.index for c in cm.exception.decision.candidates),{0,1})
    def test_conservative_adopts_later_received(self):
        a=Instruction(t(8),t(20),5.0,priority=1,revision=1,received=1)
        b=Instruction(t(8),t(20),2.0,priority=1,revision=1,received=2)
        d=decide([a,b],t(12))
        self.assertEqual(d.setpoint,2.0)
        self.assertTrue(d.conflict)
        self.assertEqual(d.winner.index,1)
        # Input order cannot change the outcome.
        d2=decide([b,a],t(12))
        self.assertEqual(d2.setpoint,2.0)
        self.assertEqual(d2.winner.received,2)
    def test_conservative_input_order_is_last_resort(self):
        a=Instruction(t(8),t(20),5.0,priority=1,revision=1)
        b=Instruction(t(8),t(20),2.0,priority=1,revision=1)
        self.assertEqual(at([a,b],t(12)),2.0)
        self.assertEqual(at([b,a],t(12)),5.0)
    def test_no_active_instruction(self):
        self.assertIsNone(at([Instruction(t(8),t(10),5.0)],t(12)))
    def test_bad_interval(self):
        with self.assertRaises(ValueError):
            at([Instruction(t(10),t(8),5.0)],t(9))
    def test_decision_is_replayable(self):
        rows=[Instruction(t(8),t(20),5.0,priority=1,revision=1,received=1),
              Instruction(t(8),t(20),2.0,priority=1,revision=1,received=2)]
        d=decide(rows,t(12))
        again=replay(d.basis,rows)
        self.assertEqual(again.setpoint,d.setpoint)
        self.assertEqual(again.basis,d.basis)
        # Tampering with an instruction must invalidate the replay.
        tampered=[Instruction(t(8),t(20),9.9,priority=1,revision=1,received=1),rows[1]]
        with self.assertRaises(AssertionError):
            replay(d.basis,tampered)
    def test_rejected_conflict_is_replayable(self):
        rows=[Instruction(t(8),t(20),5.0,priority=1,revision=1),
              Instruction(t(8),t(20),2.0,priority=1,revision=1)]
        try:
            decide(rows,t(12),OnConflict.REJECT)
        except InstructionConflict as ex:
            basis=ex.decision.basis
        else:
            self.fail('expected conflict')
        with self.assertRaises(InstructionConflict) as cm:
            replay(basis,rows)
        self.assertTrue(cm.exception.decision.conflict)
if __name__=='__main__':unittest.main()
