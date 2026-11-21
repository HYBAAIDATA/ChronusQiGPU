# Index-linked counterfactual — proposed contractual profile

The existing CIaaS endpoint remains an unverified preview. This profile is a controlled candidate for the separate authoritative settlement path, subject to contract and finance acceptance.

Freeze the contract epoch, currency, minor-unit base price per GB, published index source, base index rational value and vintage. For each reporting period record the observed index numerator and denominator, vintage, measured GB numerator and denominator, baseline/reporting dates, measurement boundary, adjustments and admitted input digests. Recompute the counterfactual from these fields alone. The index source cannot change after contract admission. No index value or client amount is supplied by default.

Exact formula: counterfactual minor units = half-even rounded (base price × measured GB × current index / base index) + approved signed adjustments; net = max(0, counterfactual − actual − incremental). Fee = floor(net / 4), consistent with the existing CIaaS preview. Client retains net less fee. The agreed contract must disclose these rounding and adjustment rules.

Pre-charge disputes are resolved through a separate admitted acceptance receipt. The recognition event must carry the same vintage and cannot occur before the agreed dispute period has elapsed. AL HARAS authenticates the authority, and THESEUS supplies admitted receipt bytes and continuity. The calculator does neither. An illustrative US$5,500 net gives US$1,375 fee and US$4,125 retained; this is not evidence of realised customer savings. No production invoice is authorised.

Option C is the only supported calculation profile in this candidate. A specific measurement plan must still establish applicability and conformity. Option D needs committed calibrated model/inputs and is not implied by this calculation. Grid-flex credits require admitted provider evidence for the certified interruptible and portable workload; otherwise the line is rejected.
