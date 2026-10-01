import unittest
from datetime import datetime,timezone,timedelta
from coldledger.reefer.setpoints import Instruction,ConflictError,at,decide
UTC=timezone.utc
T0=datetime(2026,1,1,8,tzinfo=UTC)
def ins(start_h,setpoint,priority=1,revision=1,span_h=4):
    s=T0+timedelta(hours=start_h);return Instruction(s,s+timedelta(hours=span_h),setpoint,priority,revision)
class ReeferSetpointTests(unittest.TestCase):
    def test_newer_revision_supersedes_older(self):
        old=ins(0,5.0,revision=1);new=ins(0,3.0,revision=2)
        self.assertEqual(at([old,new],T0+timedelta(hours=1)),3.0)
        self.assertEqual(at([new,old],T0+timedelta(hours=1)),3.0)
    def test_later_activation_supersedes(self):
        early=ins(0,5.0);late=ins(1,4.0)
        self.assertEqual(at([early,late],T0+timedelta(hours=2)),4.0)
    def test_priority_dominates_activation_and_revision(self):
        low=ins(1,9.0,priority=1,revision=9);high=ins(0,2.0,priority=2,revision=1)
        self.assertEqual(at([low,high],T0+timedelta(hours=2)),2.0)
    def test_full_tie_conservative_picks_colder_regardless_of_input_order(self):
        a=ins(0,5.0);b=ins(0,3.0)
        self.assertEqual(at([a,b],T0+timedelta(hours=1)),3.0)
        self.assertEqual(at([b,a],T0+timedelta(hours=1)),3.0)
        d=decide([a,b],T0+timedelta(hours=1))
        self.assertTrue(d.conflict);self.assertEqual(d.reason,'conservative-colder-setpoint')
    def test_full_tie_reject_raises_with_replayable_basis(self):
        a=ins(0,5.0);b=ins(0,3.0)
        with self.assertRaises(ConflictError) as ctx:
            decide([a,b],T0+timedelta(hours=1),on_conflict='reject')
        d=ctx.exception.decision
        self.assertTrue(d.conflict)
        self.assertEqual({i.setpoint for i in d.candidates},{3.0,5.0})
        self.assertEqual(d.when,T0+timedelta(hours=1))
    def test_identical_duplicates_are_not_a_conflict(self):
        a=ins(0,4.0);b=ins(0,4.0)
        d=decide([a,b],T0+timedelta(hours=1))
        self.assertFalse(d.conflict);self.assertEqual(d.reason,'duplicate-instructions')
        self.assertEqual(d.winner.setpoint,4.0)
    def test_decision_records_reason_and_key(self):
        old=ins(0,5.0,revision=1);new=ins(0,3.0,revision=2)
        d=decide([old,new],T0+timedelta(hours=1))
        self.assertEqual(d.reason,'revision-supersedes')
        self.assertEqual(d.key,(1,T0,2,-3.0))
        self.assertIs(d.winner,new)
        self.assertEqual(d.candidates[0],new)
    def test_no_active_instruction(self):
        self.assertIsNone(at([],T0))
        d=decide([ins(0,4.0)],T0+timedelta(hours=10))
        self.assertIsNone(d.winner);self.assertEqual(d.reason,'no-active-instruction')
    def test_interval_bounds(self):
        i=ins(0,4.0,span_h=2)
        self.assertEqual(at([i],T0),4.0)
        self.assertIsNone(at([i],T0+timedelta(hours=2)))
    def test_bad_interval_rejected(self):
        bad=Instruction(T0,T0,4.0,1,1)
        with self.assertRaises(ValueError):at([bad],T0)
    def test_unknown_policy_rejected(self):
        with self.assertRaises(ValueError):decide([ins(0,4.0)],T0,on_conflict='yolo')
if __name__=='__main__':unittest.main()
