import Std
set_option autoImplicit false
namespace Chronos
-- This is the same invertible coordinate step Q=[[1,1],[1,0]] used in v1.
def step (m : Nat) (p : Nat × Nat) : Nat × Nat := ((p.1+p.2)%m,p.1)
def undo (m : Nat) (p : Nat × Nat) : Nat × Nat := (p.2,(p.1+m-p.2)%m)
def bounded (m : Nat) (p : Nat × Nat) : Prop := p.1<m ∧ p.2<m

theorem step_bounded (m : Nat) (hm : 0<m) (p : Nat × Nat) (hp : bounded m p) : bounded m (step m p) := by
  simp only [bounded,step]
  exact ⟨Nat.mod_lt _ hm,hp.1⟩

theorem undo_step (m : Nat) (hm : 0<m) (p : Nat × Nat) (hp : bounded m p) : undo m (step m p)=p := by
  rcases p with ⟨a,b⟩
  simp only [bounded] at hp
  have hr : ((a+b)%m+m-a)%m=b := by
    by_cases h : a+b<m
    · rw [Nat.mod_eq_of_lt h]
      have he : a+b+m-a=b+m := by omega
      rw [he]
      simp [Nat.add_mod,Nat.mod_eq_of_lt hp.2]
    · rw [Nat.mod_eq_sub_mod (by omega : m≤a+b), Nat.mod_eq_of_lt (by omega : a+b-m<m)]
      have he : a+b-m+m-a=b := by omega
      rw [he,Nat.mod_eq_of_lt hp.2]
  exact Prod.ext rfl hr

theorem step_undo (m : Nat) (hm : 0<m) (p : Nat × Nat) (hp : bounded m p) : step m (undo m p)=p := by
  rcases p with ⟨a,b⟩
  simp only [bounded] at hp
  have hr : (b+(a+m-b)%m)%m=a := by
    by_cases h : a<b
    · rw [Nat.mod_eq_of_lt (by omega : a+m-b<m)]
      have he : b+(a+m-b)=a+m := by omega
      rw [he]
      simp [Nat.add_mod,Nat.mod_eq_of_lt hp.1]
    · rw [Nat.mod_eq_sub_mod (by omega : m≤a+m-b),Nat.mod_eq_of_lt (by omega : a+m-b-m<m)]
      have he : b+(a+m-b-m)=a := by omega
      rw [he,Nat.mod_eq_of_lt hp.1]
  exact Prod.ext hr rfl

def fold (m : Nat) : Nat → Nat × Nat → Nat × Nat
  | 0,p => p
  | n+1,p => step m (fold m n p)
def unfold (m : Nat) : Nat → Nat × Nat → Nat × Nat
  | 0,p => p
  | n+1,p => unfold m n (undo m p)

theorem fold_bounded (m : Nat) (hm : 0<m) (n : Nat) (p : Nat × Nat) (hp : bounded m p) : bounded m (fold m n p) := by
  induction n with
  | zero => exact hp
  | succ n ih => exact step_bounded m hm _ ih

theorem unfold_fold (m : Nat) (hm : 0<m) (n : Nat) (p : Nat × Nat) (hp : bounded m p) : unfold m n (fold m n p)=p := by
  induction n with
  | zero => rfl
  | succ n ih =>
    simp only [fold,unfold]
    rw [undo_step m hm _ (fold_bounded m hm n p hp)]
    exact ih
-- Constructive preimage of low-coordinate projection. The two free coordinates
-- high and right enumerate its fiber. Python additionally constructs Q^-index.
theorem projection_surjection (base : Nat) (hb : 0<base) (r : Nat) (hr : r<base) (high : Nat) : (high*base+r)%base=r := by
  simp [Nat.add_mod,Nat.mul_mod,Nat.mod_eq_of_lt hr]

theorem fiber_unique (base : Nat) (hb : 0<base) (r r' high high' : Nat) (hr : r<base) (hr' : r'<base)
    (h : high*base+r=high'*base+r') : high=high' ∧ r=r' := by
  have hmod := congrArg (fun x : Nat => x%base) h
  have hdiv := congrArg (fun x : Nat => x/base) h
  simp [Nat.add_mod,Nat.mul_mod,Nat.mod_eq_of_lt hr,Nat.mod_eq_of_lt hr'] at hmod
  have hx : (high*base+r)/base=high := by
    rw [Nat.add_comm, Nat.add_mul_div_right r high hb, Nat.div_eq_of_lt hr]
    simp
  have hy : (high'*base+r')/base=high' := by
    rw [Nat.add_comm, Nat.add_mul_div_right r' high' hb, Nat.div_eq_of_lt hr']
    simp
  change (high*base+r)/base=(high'*base+r')/base at hdiv
  rw [hx,hy] at hdiv
  exact ⟨hdiv,hmod⟩
#print axioms unfold_fold
#print axioms projection_surjection
#print axioms fiber_unique
end Chronos
namespace Chronos
 theorem undo_bounded (m : Nat) (hm : 0<m) (p : Nat × Nat) (hp : bounded m p) : bounded m (undo m p) := by
  simp only [bounded,undo]
  exact ⟨hp.2,Nat.mod_lt _ hm⟩
 theorem unfold_bounded (m : Nat) (hm : 0<m) (n : Nat) (p : Nat × Nat) (hp : bounded m p) : bounded m (unfold m n p) := by
  induction n generalizing p with
  | zero => exact hp
  | succ n ih => exact ih _ (undo_bounded m hm p hp)
 theorem fold_unfold (m : Nat) (hm : 0<m) (n : Nat) (p : Nat × Nat) (hp : bounded m p) : fold m n (unfold m n p)=p := by
  induction n generalizing p with
  | zero => rfl
  | succ n ih =>
    simp only [unfold,fold]
    rw [ih _ (undo_bounded m hm p hp)]
    exact step_undo m hm p hp
 theorem fold_injective (m : Nat) (hm : 0<m) (n : Nat) (p q : Nat × Nat) (hp : bounded m p) (hq : bounded m q)
      (h : fold m n p=fold m n q) : p=q := by
  have hx := congrArg (unfold m n) h
  rw [unfold_fold m hm n p hp,unfold_fold m hm n q hq] at hx
  exact hx
 #print axioms fold_unfold
 #print axioms fold_injective
end Chronos
