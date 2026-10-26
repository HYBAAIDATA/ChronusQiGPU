import React, { useState } from "react";
import { apiUrl, operatorPrincipal, setOperatorKey, setOperatorPrincipal, setSubscriptionCreds } from "../lib/api";
export function ControlSession({ onChanged }: { onChanged?: () => void }) {
  const [principal, setPrincipal] = useState(operatorPrincipal() ?? "");
  const [credential, setCredential] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function authenticate(logout = false) {
    setBusy(true);
    try {
      const response = await fetch(apiUrl(logout ? "/api/auth/logout" : "/api/auth/login"), {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(logout ? {} : {principal_id: principal.trim(), credential}),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
      // Migrate away from JavaScript-readable operator credentials.
      setOperatorKey(null); setOperatorPrincipal(null); setCredential("");
      if (logout) setSubscriptionCreds(null);
      setMessage(logout ? "Signed out" : `Authenticated · ${body.role}`);
      onChanged?.();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Authentication unavailable"); }
    finally { setCredential(""); setBusy(false); }
  }
  const [tenant, setTenant] = useState("");
  const [actor, setActor] = useState("");
  const [subscriptionToken, setSubscriptionToken] = useState("");
  return <details className="console-surface mt-6 p-4"><summary>Control session</summary>
    <form className="console-session" onSubmit={e => { e.preventDefault(); if (!principal.trim() || !credential) return; void authenticate(); }}>
      <label>Principal<input autoComplete="username" value={principal} onChange={e => setPrincipal(e.target.value)} required /></label>
      <label>Operator credential<input type="password" autoComplete="current-password" value={credential} onChange={e => setCredential(e.target.value)} required /></label>
      <button type="submit" disabled={busy}>Authenticate</button>
      <button type="button" disabled={busy} onClick={() => { void authenticate(true); }}>Sign out</button>
    </form>
    <p role="status">{message}</p>
    <details className="mt-4"><summary>Tenant subscription for mining evidence</summary>
      <form className="console-session" onSubmit={e => { e.preventDefault(); if (!tenant.trim() || !actor.trim() || !subscriptionToken) return; setSubscriptionCreds({tenant:tenant.trim(), actor:actor.trim(), token:subscriptionToken}); setSubscriptionToken(""); onChanged?.(); }}>
        <label>Tenant<input autoComplete="off" value={tenant} onChange={e => setTenant(e.target.value)} required /></label>
        <label>Actor<input autoComplete="off" value={actor} onChange={e => setActor(e.target.value)} required /></label>
        <label>Subscription bearer<input type="password" autoComplete="off" value={subscriptionToken} onChange={e => setSubscriptionToken(e.target.value)} required /></label>
        <button type="submit">Bind subscription</button>
      </form><p className="console-source">AL HARAS validates this independently. A local tenant label or CEO role is not a subscription grant.</p>
    </details><p className="console-source">Server-confirmed role only. Operator sessions use a Secure HttpOnly cookie; no client role grants. Subscription credentials remain a separate guardian boundary.</p>
  </details>;
}
