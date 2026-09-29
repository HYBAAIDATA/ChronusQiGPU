"""Profile-bound SLOs, dashboard models, and alert-rule rendering."""
from __future__ import annotations
from dataclasses import asdict,dataclass
from typing import Any
@dataclass(frozen=True)
class SLO:name:str;service:str;indicator:str;objective:float;window:str;error_budget:float;alert_policy:str
SLOS=(
 SLO("guardian_availability","guardian",'sum(rate(guardian_verdict_total{overall!="DENY"}[5m])) / clamp_min(sum(rate(guardian_verdict_total[5m])),1)',0.9995,"30d",0.0005,"burn_rate_fast+burn_rate_slow"),
 SLO("primedb_integrity","primedb","1 - clamp_max(rate(primedb_cassini_failures_total[5m]),1)",0.99999,"7d",0.00001,"burn_rate_fast"),
 SLO("witness_anchor_freshness","witness","time() - max(witness_anchor_timestamp_seconds)",0.9999,"30d",0.0001,"freshness_alert"),
 SLO("folded_execution_parity","fold_execution","sum(rate(folded_parity_pass_total[5m])) / clamp_min(sum(rate(folded_parity_total[5m])),1)",1.0,"30d",0.0,"any_failure_page"),
 SLO("rehydration_disclosure","fold_execution","sum(rate(rehydration_receipt_match_total[5m])) / clamp_min(sum(rate(rehydration_receipt_total[5m])),1)",1.0,"30d",0.0,"any_failure_page"),
 SLO("backend_attestation_freshness","guard","time() - max(backend_attestation_timestamp_seconds)",0.999,"30d",0.001,"freshness_alert"))
_BY_NAME={s.name:s for s in SLOS}
PROFILE_SLOS={"developer":("primedb_integrity",),"edge":("guardian_availability","primedb_integrity"),"enterprise":("guardian_availability","primedb_integrity","witness_anchor_freshness","folded_execution_parity","rehydration_disclosure"),"sovereign":tuple(s.name for s in SLOS),"hyperscaler":tuple(s.name for s in SLOS)}
PANELS=(
 ("Guardian verdicts by surface","guardian_surface_status","timeseries"),("Witness anchoring health","witness_anchor_total","stat"),("PRIME-DB integrity","primedb_cassini_failures_total","timeseries"),("Execution backend distribution","mla1517_backend_selected_total","piechart"),("Bytes moved by operation","mla1517_bytes_moved_total","timeseries"),("Proof cost per result","mla1517_proof_bytes","histogram"),("Resource truth","mla1517_energy_joules","timeseries"),("Rehydration events","primedb_rehydration_count","timeseries"),("Agent action rate","services_agent_fabric_actions_total","timeseries"),("Evidence receipts","services_evidence_receipts_total","timeseries"))
def slos_for(profile):
 if profile not in PROFILE_SLOS:raise ValueError(profile)
 return tuple(_BY_NAME[n] for n in PROFILE_SLOS[profile])
def prometheus_config():return {"global":{"scrape_interval":"15s"},"scrape_configs":[{"job_name":"mla1517-core","metrics_path":"/metrics","static_configs":[{"targets":["mla1517-core:9100"],"labels":{"role":"core"}}]},{"job_name":"mla1517-pythia","static_configs":[{"targets":["mla1517-pythia:9101"],"labels":{"role":"miner"}}]},{"job_name":"hyba-enterprise","static_configs":[{"targets":["hyba-enterprise:9102"],"labels":{"role":"enterprise"}}]}]}
def otel_config(core_version,profile,tenant):
 if not tenant:raise ValueError("tenant required")
 return {"service_name":"mla1517","exporter":"otlp","endpoint":"otel-collector:4317","resource_attributes":{"service.version":core_version,"deployment.profile":profile,"tenant.id":tenant},"sampling":{"kind":"parent_based","root":{"kind":"traceidratio","ratio":0.05}},"propagators":["tracecontext","baggage"],"metric_export_interval_ms":15000}
def render_dashboard(profile):return {"dashboard":{"title":f"MLA1517 — {profile}","refresh":"30s","panels":[{"title":title,"targets":[{"expr":expr,"legendFormat":"{{tenant}} / {{instance}}"}],"type":kind} for title,expr,kind in PANELS],"slo_names":[s.name for s in slos_for(profile)]}}
def alert_rules(profile,policy_max_age_seconds=900):
 rules=[]
 for slo in slos_for(profile):
  if slo.alert_policy=="any_failure_page":rules.append({"alert":f"{slo.name}_failure","expr":f"({slo.indicator}) < 1","for":"0m","labels":{"severity":"page","slo":slo.name}})
  elif slo.alert_policy=="freshness_alert":rules.append({"alert":f"{slo.name}_stale","expr":f"({slo.indicator}) > {int(policy_max_age_seconds)}","for":"5m","labels":{"severity":"page","slo":slo.name}})
  else:
   rules.append({"alert":f"{slo.name}_burn_rate_fast","expr":f"(1 - ({slo.indicator})) > {14.4*slo.error_budget}","for":"2m","labels":{"severity":"page","slo":slo.name}})
   if "slow" in slo.alert_policy:rules.append({"alert":f"{slo.name}_burn_rate_slow","expr":f"(1 - ({slo.indicator})) > {6*slo.error_budget}","for":"15m","labels":{"severity":"ticket","slo":slo.name}})
 return {"groups":[{"name":f"mla1517-{profile}-slos","rules":rules}]}
