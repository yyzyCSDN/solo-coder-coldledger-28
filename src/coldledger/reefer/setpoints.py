from dataclasses import dataclass
from datetime import datetime,timezone
@dataclass(frozen=True)
class Instruction: start:datetime;end:datetime;setpoint:float;priority:int;revision:int
@dataclass(frozen=True)
class Decision: when:datetime;winner:Instruction|None;candidates:tuple;key:tuple|None;conflict:bool;reason:str
class ConflictError(ValueError):
    def __init__(self,decision):
        self.decision=decision;super().__init__(f'conflicting instructions at {decision.when.isoformat()}')
def _key(i): return (i.priority,i.start.astimezone(timezone.utc),i.revision,-i.setpoint)
def decide(instructions,when,on_conflict='conservative'):
    if on_conflict not in ('conservative','reject'):raise ValueError('unknown conflict policy')
    x=when.astimezone(timezone.utc);rows=[]
    for i in instructions:
        s,e=i.start.astimezone(timezone.utc),i.end.astimezone(timezone.utc)
        if e<=s:raise ValueError('bad interval')
        if s<=x<e:rows.append(i)
    rows.sort(key=_key,reverse=True)
    if not rows:return Decision(x,None,(),None,False,'no-active-instruction')
    winner=rows[0];wk=_key(winner);tied=[i for i in rows if _key(i)[:3]==wk[:3]]
    conflict=len({i.setpoint for i in tied})>1
    if len(tied)>1:reason='conservative-colder-setpoint' if conflict else 'duplicate-instructions'
    elif len(rows)==1:reason='uncontested'
    else:
        nk=_key(rows[1]);reason='priority-supersedes' if nk[0]!=wk[0] else 'activation-supersedes' if nk[1]!=wk[1] else 'revision-supersedes'
    d=Decision(x,winner,tuple(rows),wk,conflict,reason)
    if conflict and on_conflict=='reject':raise ConflictError(d)
    return d
def at(instructions,when,on_conflict='conservative'):
    d=decide(instructions,when,on_conflict)
    return None if d.winner is None else d.winner.setpoint
