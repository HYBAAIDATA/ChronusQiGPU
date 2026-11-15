# fix_mining_page2.py - Remove JSX blocks for removed functions
path = "c:/Users/leonn/OneDrive/Desktop/chronus-quantum-igpu/frontend/app/mining/page.tsx"
with open(path, "r", encoding="utf-8") as f:
    c = f.read()


def rep(old, new):
    global c
    assert old in c, "NOT FOUND: " + old[:100]
    c = c.replace(old, new)


# 1. Remove Inject Reorg and DSW Heal buttons
rep('''              <div className="flex flex-wrap gap-3 pt-2">
                <button
                  onClick={handleInjectAnomaly}
                  className="flex items-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3.5 py-2 text-xs font-mono font-medium text-rose-300 hover:bg-rose-500/20"
                >
                  <AlertCircle className="h-3.5 w-3.5" />
                  <span>Inject Reorg / Stratum Vortex</span>
                </button>
                <button
                  onClick={handleHealAnomaly}
                  className="flex items-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3.5 py-2 text-xs font-mono font-medium text-emerald-300 hover:bg-emerald-500/20"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  <span>Execute 1-Cycle DSW Instanton Heal</span>
                </button>
              </div>
''', '')

# 2. Remove Multi-Pool E2E Simulation Engine section
rep('''              {/* Multi-Pool E2E Simulation Engine */}
              <div className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4 space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-semibold text-white uppercase tracking-wider">
                    Stratum Multi-Pool End-to-End Handshake & Share Verification
                  </span>
                  <button
                    onClick={handleRunSimulation}
                    disabled={simulationRunning}
                    className="flex items-center gap-2 rounded-md bg-amber-500/20 border border-amber-500/40 px-3 py-1.5 text-xs font-mono font-semibold text-amber-300 hover:bg-amber-500/30 disabled:opacity-50"
                  >
                    <Play className="h-3.5 w-3.5" />
                    <span>{simulationRunning ? 'Running 4-Pool Handshake...' : 'Run Master E2E Simulation'}</span>
                  </button>
                </div>

                {simulationStatus && (
                  <div className="rounded border border-emerald-500/30 bg-emerald-500/10 p-2 text-xs font-mono text-emerald-300">
                    {simulationStatus}
                  </div>
                )}

                {simulationLogs.length > 0 && (
                  <div className="rounded border border-neutral-800 bg-neutral-950 p-3 max-h-40 overflow-y-auto space-y-1 font-mono text-[11px] text-neutral-300">
                    {simulationLogs.map((log, idx) => (
                      <div key={idx} className={log.includes('VERIFIED') || log.includes('Accepted') ? 'text-emerald-400' : 'text-neutral-300'}>
                        {log}
                      </div>
                    ))}
                  </div>
                )}
              </div>
''', '')

# Write
with open(path, "w", encoding="utf-8") as f:
    f.write(c)

print("OK: mining page.tsx step 2 updated")
