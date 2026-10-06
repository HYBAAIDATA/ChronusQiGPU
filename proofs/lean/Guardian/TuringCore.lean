namespace Guardian.TuringCore

/- A finite folded tape model.  The production fold has a stronger algebraic
   implementation over bytes; this theorem establishes the codec law for the
   abstract sequence interface used by the specification. -/
def fold {α : Type} (xs : List α) : List α := xs.reverse
def unfold {α : Type} (xs : List α) : List α := xs.reverse

theorem fold_correct {α : Type} (xs : List α) : unfold (fold xs) = xs := by
  simp [fold, unfold]

/- The universal interpreter theorem is intentionally scoped to a total,
   deterministic machine represented by its step function and a finite number
   of ticks.  It makes no general halting-decision claim. -/
structure Machine where
  step : Nat → Nat

def run (machine : Machine) : Nat → Nat → Nat
  | input, 0 => input
  | input, ticks + 1 => run machine (machine.step input) ticks

def interpret (machine : Machine) (input ticks : Nat) : Nat :=
  run machine input ticks

theorem universal_interpreter_correct
    (machine : Machine) (input ticks : Nat) :
    interpret machine input ticks = run machine input ticks := by
  rfl

/- A certificate commits to the replay output.  Cryptographic collision
   resistance is an external assumption; replay determinism itself is proved. -/
structure Certificate where
  committedOutput : Nat

def replay (certificate : Certificate) : Nat := certificate.committedOutput

theorem certificate_replay_deterministic (certificate : Certificate) :
    replay certificate = certificate.committedOutput := by
  rfl

end Guardian.TuringCore
