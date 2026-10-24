import { beforeEach, describe, expect, it, vi } from "vitest";
import { miningDashboardAccess } from "../access";
const json = (body:unknown,status=200) => new Response(JSON.stringify(body),{status});
describe("HttpOnly mining dashboard entitlement", () => {
  beforeEach(() => window.sessionStorage.clear());
  it("checks the server with cookies and no JavaScript-readable credential", async () => {
    const controller=new AbortController();
    const mock=vi.fn(async(_input:RequestInfo|URL,_init?:RequestInit)=>json({principal_id:"owner",role:"ceo"}));
    expect(await miningDashboardAccess(mock as typeof fetch,controller.signal)).toEqual({allowed:true,principalId:"owner",role:"ceo",reason:"authorized"});
    expect(mock).toHaveBeenCalledWith("/api/v1/control/session",expect.objectContaining({credentials:"include",cache:"no-store",signal:controller.signal}));
    const init=mock.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("Authorization")).toBeNull();
    expect(new Headers(init.headers).get("X-PYTHIA-Principal")).toBeNull();
  });
  it("does not treat stale browser identity as authority or reject the actual cookie identity", async()=>{
    window.sessionStorage.setItem("pythia.operatorPrincipal","old-user");
    window.sessionStorage.setItem("pythia.operatorKey","old-secret");
    const mock=vi.fn(async(_input:RequestInfo|URL,_init?:RequestInit)=>json({principal_id:"new-user",role:"ceo"}));
    expect((await miningDashboardAccess(mock as typeof fetch)).principalId).toBe("new-user");
  });
  it.each(["operator","analyst","auditor","founder_ceo","CEO"])("refuses noncanonical/unprivileged role %s",async(role)=>{
    const mock=vi.fn(async(_input:RequestInfo|URL,_init?:RequestInit)=>json({principal_id:"owner",role}));
    expect((await miningDashboardAccess(mock as typeof fetch)).reason).toBe("ceo_role_required");
  });
  it.each([null,[],{}, {principal_id:"",role:"ceo"}, {principal_id:"  ",role:"ceo"},{principal_id:123,role:"ceo"},{principal_id:"owner",role:123}])("refuses malformed session %j",async(body)=>{
    const mock=vi.fn(async(_input:RequestInfo|URL,_init?:RequestInit)=>json(body));
    expect((await miningDashboardAccess(mock as typeof fetch)).reason).toBe("invalid_control_session");
  });
  it.each([401,403,500,503])("fails closed on HTTP %i",async(code)=>{
    const mock=vi.fn(async(_input:RequestInfo|URL,_init?:RequestInit)=>json({},code));
    expect((await miningDashboardAccess(mock as typeof fetch)).allowed).toBe(false);
  });
  it("reports a missing endpoint",async()=>{
    const mock=vi.fn(async(_input:RequestInfo|URL,_init?:RequestInit)=>json({},404));
    expect((await miningDashboardAccess(mock as typeof fetch)).reason).toBe("control_session_entitlement_unavailable");
  });
  it("fails closed on a transport exception",async()=>{
    const mock=vi.fn(async(_input:RequestInfo|URL,_init?:RequestInit)=>{throw new Error("offline");});
    expect((await miningDashboardAccess(mock as typeof fetch)).reason).toBe("control_session_unreachable");
  });
});
