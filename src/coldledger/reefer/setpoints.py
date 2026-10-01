from dataclasses import dataclass
from datetime import datetime,timezone
from enum import Enum
UTC=timezone.utc
@dataclass(frozen=True)
class Instruction:
    start:datetime;end:datetime;setpoint:float
    priority:int=0;revision:int=1;tolerance:float=0.0
    received:int=0
class OnConflict(str,Enum):
    REJECT='reject'
    CONSERVATIVE='conservative'
class InstructionConflict(RuntimeError):
    def __init__(self,msg,decision=None):
        super().__init__(msg); self.decision=decision
@dataclass(frozen=True)
class Candidate:
    index:int;priority:int;revision:int;start:datetime;end:datetime
    setpoint:float;tolerance:float;received:int
    key:tuple
@dataclass(frozen=True)
class Decision:
    at:datetime;setpoint:float;tolerance:float
    policy:OnConflict;conflict:bool
    winner:Candidate;candidates:tuple
    basis:dict
def _u(v):
    if v.tzinfo is None or v.utcoffset() is None: raise ValueError('timezone-aware datetime required')
    return v.astimezone(UTC)
def _candidate(i,index):
    s,e=_u(i.start),_u(i.end)
    if e<=s: raise ValueError('bad interval')
    if i.tolerance<0: raise ValueError('tolerance must be non-negative')
    # One adjudication order for every field. Higher priority first; then the
    # newest revision (a revision can never be beaten by an earlier one); then
    # the later activation time; then the tighter temperature band; and finally
    # the later-received instruction as an explicit, replayable tie-break.
    key=(i.priority,i.revision,s.timestamp(),-i.tolerance,i.received,index)
    return Candidate(index,i.priority,i.revision,s,e,float(i.setpoint),float(i.tolerance),i.received,key)
def _rank(c): return c.key
def _same_rank(a,b): return a.key[:4]==b.key[:4]
def _basis(when,cands,winner,conflict,policy,setpoint,tolerance):
    return {
        'at':_u(when).isoformat(),'policy':policy.value,
        'conflict':conflict,'setpoint':setpoint,'tolerance':tolerance,
        'winner':None if winner is None else winner.index,
        'instructions':[
            {'index':c.index,'priority':c.priority,'revision':c.revision,
             'start':c.start.isoformat(),'end':c.end.isoformat(),
             'setpoint':c.setpoint,'tolerance':c.tolerance,
             'received':c.received,'key':list(c.key)}
            for c in cands],
    }
def decide(instructions,when,on_conflict=OnConflict.CONSERVATIVE):
    policy=OnConflict(on_conflict)
    x=_u(when)
    active=tuple(sorted((_candidate(i,k) for k,i in enumerate(instructions)),
                        key=lambda c:c.index))
    active=tuple(c for c in active if c.start<=x<c.end)
    if not active:
        return Decision(x,None,None,policy,False,None,(),
                        _basis(x,(),None,False,policy,None,None))
    ranked=sorted(active,key=_rank,reverse=True)
    winner=ranked[0]
    # A genuine conflict: another active instruction ties on priority,
    # revision, activation time and tolerance but carries a different setpoint.
    tied=tuple(c for c in ranked[1:] if _same_rank(c,winner))
    conflicting=tuple(c for c in tied if c.setpoint!=winner.setpoint)
    conflict=bool(conflicting)
    if conflict and policy is OnConflict.REJECT:
        d=Decision(x,None,None,policy,True,None,ranked,
                   _basis(x,ranked,None,True,policy,None,None))
        idx=[winner.index]+[c.index for c in conflicting]
        raise InstructionConflict(
            f'overlapping same-priority instructions {sorted(idx)} demand different setpoints at {x.isoformat()}',d)
    # Conservative policy: adopt the newer instruction. Rank already resolves
    # revision/activation/tolerance; an irreducible tie falls to the instruction
    # received later, else the later input. Nothing is silently discarded.
    setpoint=winner.setpoint;tolerance=winner.tolerance
    return Decision(x,setpoint,tolerance,policy,conflict,winner,ranked,
                    _basis(x,ranked,winner,conflict,policy,setpoint,tolerance))
def at(instructions,when,on_conflict=OnConflict.CONSERVATIVE):
    d=decide(instructions,when,on_conflict)
    return d.setpoint
def replay(basis,instructions):
    """Re-adjudicate from a recorded basis; the result must reproduce it."""
    when=datetime.fromisoformat(basis['at'])
    policy=OnConflict(basis['policy'])
    try:
        d=decide(instructions,when,policy)
    except InstructionConflict as ex:
        d=ex.decision
    if d is None: raise AssertionError('replay produced no decision')
    got=_basis(d.at,d.candidates,d.winner,d.conflict,d.policy,d.setpoint,d.tolerance)
    if got!=basis: raise AssertionError('replay does not reproduce recorded decision')
    if basis['policy']==OnConflict.REJECT.value and basis['conflict']:
        raise InstructionConflict('replay of recorded conflict',d)
    return d
