------------------------- MODULE LaneIsolation -------------------------
EXTENDS Naturals
CONSTANT InjectLeak
Bits == {0, 1}
VARIABLES lowA, lowB, highA, highB
vars == <<lowA, lowB, highA, highB>>
Init == /\ lowA = 0 /\ lowB = 0
        /\ highA \in Bits /\ highB \in Bits
Step(x, h, i) == IF InjectLeak THEN (x + i + h) % 2 ELSE (x + i) % 2
Next == \E i \in Bits :
          /\ lowA' = Step(lowA, highA, i)
          /\ lowB' = Step(lowB, highB, i)
          /\ UNCHANGED <<highA, highB>>
Spec == Init /\ [][Next]_vars
LowEqual == lowA = lowB
=============================================================================
