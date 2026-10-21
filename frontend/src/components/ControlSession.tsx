import React, { useState } from "react";
import { operatorPrincipal, setOperatorKey, setOperatorPrincipal, setSubscriptionCreds } from "../lib/api";
export function ControlSession({ onChanged }: { onChanged?: () => void }) {
  const [principal, setPrincipal] = useState(operatorPrincipal() ?? "");
  const [credential, setCredential] = useState("");
  const [tenant, setTenant] = useState("");
  const [actor, setActor] = useState("");
  const [subscriptionToken, setSubscriptionToken] = useState("");
  return <details className="console-surface mt-6 p-4"><summary>Control session</summary>
    <form className="console-session" onSubmit={e => { e.preventDefault(); if (!principal.trim() || !credential) return; setOperatorPrincipal(principal.trim()); setOperatorKey(credential); setCredential(""); }}>
      <label>Principal<input autoComplete="username" value={principal} onChange={e => setPrincipal(e.target.value)} required /></label>
      <label>Session bearer<input type="password" autoComplete="current-password" value={credential} onChange={e => setCredential(e.target.value)} required /></label>
      <button type="submit">Authenticate</button>
      <button type="button" onClick={() => { setOperatorKey(null); setOperatorPrincipal(null); setSubscriptionCreds(null); setCredential(""); }}>Sign out</button>
    </form>
    <details className="mt-4"><summary>Tenant subscription for mining evidence</summary>
      <form className="console-session" onSubmit={e => { e.preventDefault(); if (!tenant.trim() || !actor.trim() || !subscriptionToken) return; setSubscriptionCreds({tenant:tenant.trim(), actor:actor.trim(), token:subscriptionToken}); setSubscriptionToken(""); onChanged?.(); }}>
        <label>Tenant<input autoComplete="off" value={tenant} onChange={e => setTenant(e.target.value)} required /></label>
        <label>Actor<input autoComplete="off" value={actor} onChange={e => setActor(e.target.value)} required /></label>
        <label>Subscription bearer<input type="password" autoComplete="off" value={subscriptionToken} onChange={e => setSubscriptionToken(e.target.value)} required /></label>
        <button type="submit">Bind subscription</button>
      </form><p className="console-source">AL HARAS validates this independently. A local tenant label or CEO role is not a subscription grant.</p>
    </details><p className="console-source">Server-confirmed role only. Credentials remain in this tab's session storage.</p>
  </details>;
}
