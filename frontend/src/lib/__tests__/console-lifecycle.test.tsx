import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useConsole } from "../useConsole";
import { setOperatorKey, setOperatorPrincipal } from "../api";
let host: HTMLDivElement, root: Root;
const payload = { schema_version:"chronus.mla1517.status/1", generated_at:"2026-10-20T23:00:00Z", ready_to_mine:{ready:true, reason:"backend_fixture_only"} };
function Probe() { const v=useConsole(); return <pre>{JSON.stringify(v)}</pre>; }
const flush = async () => { await act(async () => { for(let i=0;i<30;i++) await Promise.resolve(); }); };
const json = (body:unknown,status=200) => new Response(JSON.stringify(body),{status});
beforeEach(() => {
  vi.useFakeTimers(); window.sessionStorage.clear();
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
  setOperatorPrincipal("owner");setOperatorKey("test-only");
  host=document.createElement("div");document.body.append(host);root=createRoot(host);
});
afterEach(async()=>{ await act(async()=>root.unmount());host.remove();vi.useRealTimers();vi.unstubAllGlobals(); });
const mount=async()=>{ await act(async()=>root.render(<Probe/>));await flush(); };
const state=()=>JSON.parse(host.textContent!);
function backend(options:{role?:string;status?:number}={}) {
  return vi.fn(async(input:RequestInfo|URL)=> {
    const path=String(input);
    if(path.endsWith("control/session")) return json({principal_id:"owner",role:options.role??"ceo"});
    if(path.endsWith("mla1517/status")) return json(payload,options.status??200);
    return json({evidence_available:false});
  });
}
describe("fail-closed console lifecycle",()=>{
  it("renders only a backend-confirmed verdict", async()=>{
    const mock=backend();vi.stubGlobal("fetch",mock);await mount();
    expect(state().status.ready_to_mine.ready).toBe(true);
    expect(mock.mock.calls.filter(c=>String(c[0]).endsWith("mla1517/status"))).toHaveLength(1);
  });
  it("does not read any mining endpoint without CEO role", async()=>{
    const mock=backend({role:"operator"});vi.stubGlobal("fetch",mock);await mount();
    expect(state().access.allowed).toBe(false);expect(state().status).toBeNull();expect(mock).toHaveBeenCalledTimes(1);
  });
  it.each([401,403,500,503])("clears stale green on status HTTP %i",async(code)=>{
    const options={status:200};vi.stubGlobal("fetch",backend(options));await mount();
    options.status=code;await act(async()=>{await vi.advanceTimersByTimeAsync(5000);});await flush();
    expect(state().status).toBeNull();expect(state().evidence).toBeNull();
    expect(code<500?state().access.allowed:state().offline).toBe(code>=500);
  });
  it("clears stale green on transport failure",async()=>{
    const mock=backend();vi.stubGlobal("fetch",mock);await mount();
    mock.mockImplementation(async()=>{throw new Error("backend stopped");});
    await act(async()=>{await vi.advanceTimersByTimeAsync(5000);});await flush();
    expect(state().offline).toBe(true);expect(state().status).toBeNull();
  });
  it("hides all snapshots on the 30s role revocation check",async()=>{
    const options={role:"ceo"};vi.stubGlobal("fetch",backend(options));await mount();options.role="operator";
    await act(async()=>{await vi.advanceTimersByTimeAsync(30000);});await flush();
    expect(state().access.reason).toBe("ceo_role_required");expect(state().status).toBeNull();
  });
  it("rejects late in-flight data after sign-out",async()=>{
    let resolveStatus:(value:Response)=>void=()=>{};
    const mock=backend();mock.mockImplementation(async(input)=>String(input).endsWith("mla1517/status")?await new Promise<Response>(resolve=>{resolveStatus=resolve;}):json({principal_id:"owner",role:"ceo"}));
    vi.stubGlobal("fetch",mock);await mount();
    await act(async()=>{setOperatorKey(null);});resolveStatus(json(payload));await flush();
    expect(state().status).toBeNull();expect(state().access.allowed).toBe(false);
  });
  it("aborts a hung request rather than keeping a green snapshot forever",async()=>{
    const mock=backend();vi.stubGlobal("fetch",mock);await mount();
    mock.mockImplementation(async(_input,init?:RequestInit)=>await new Promise<Response>((_resolve,reject)=>init?.signal?.addEventListener("abort",()=>reject(new DOMException("Aborted","AbortError")))));
    await act(async()=>{await vi.advanceTimersByTimeAsync(15000);});await flush();
    expect(state().status).toBeNull();expect(state().offline).toBe(true);
  });
});
