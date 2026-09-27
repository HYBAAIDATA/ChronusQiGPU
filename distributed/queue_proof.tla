---- MODULE queue_proof ----
EXTENDS Naturals, Sequences

CONSTANTS MaxInFlight

VARIABLES pending, inFlight, seen

TypeOK ==
  /\ pending \in Seq(STRING)
  /\ inFlight \in Seq(STRING)
  /\ seen \in [STRING -> STRING]

Init ==
  /\ pending = << >>
  /\ inFlight = << >>
  /\ seen = [k \in {} |-> ""]

Enqueue(key, id) ==
  \/ /\ key \in DOMAIN seen
     /\ UNCHANGED <<pending, inFlight, seen>>
  \/ /\ key \notin DOMAIN seen
     /\ Len(inFlight) < MaxInFlight
     /\ pending' = Append(pending, id)
     /\ seen' = seen @@ [key |-> id]
     /\ UNCHANGED inFlight

Dequeue ==
  \/ /\ pending = << >>
     /\ UNCHANGED <<pending, inFlight, seen>>
  \/ /\ pending # << >>
     /\ pending' = Tail(pending)
     /\ inFlight' = Append(inFlight, Head(pending))
     /\ UNCHANGED seen

Next == (\E k, i : Enqueue(k, i)) \/ Dequeue

Spec == Init /\ [][Next]_<<pending, inFlight, seen>>
====
