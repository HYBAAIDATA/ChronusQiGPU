# Mining expectation gate — analytical definition only

Status: DOCUMENTED; measured hashrate, replay, pool acceptance and four-hour heartbeat qualification NOT RUN here.

For constant measured SHA256d hashrate H hashes/s and share difficulty D using the conventional difficulty-one approximation:

- mean waiting time E[T] = D * 2^32 / H seconds;
- expected share count over t seconds: lambda = H * t / (D * 2^32);
- under an independent stationary Poisson approximation, P(no share in t) = exp(-lambda).

The owner's illustrative 508 MH/s assumption gives approximately 2.4 h at difficulty 1024 and 19.2 h at 8192. These are mean waits, not deadlines or measured device rates. A zero-share window is interpreted with its duration, actual pool difficulty, job validity and measured H; zero shares is not automatically PASS or failure. Variable difficulty/rate requires the time-integrated expectation.

EUCLID must receive measured share outcomes, not expected counts mislabeled as observed outcomes. PYTHIA retains SearchPlan/share authority; independent double-SHA256 and actual pool acceptance retain their boundaries. This document changes no mining execution or authority and contains no live-pool receipt.
