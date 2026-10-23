import React,{act} from "react";
import {createRoot,type Root} from "react-dom/client";
import {beforeEach,afterEach,describe,it,expect,vi} from "vitest";
import {ControlSession} from "../ControlSession";
import {useConsole} from "../../lib/useConsole";
let host:HTMLDivElement,root:Root;
const flush=async()=>{await act(async()=>{for(let i=0;i<40;i++)await Promise.resolve();});};
const json=(v:unknown,status=200)=>new Response(JSON.stringify(v),{status});
function Journey(){const state=useConsole();return <><ControlSession onChanged={state.refresh}/><pre data-state>{JSON.stringify(state)}</pre></>;}
const state=()=>JSON.parse(host.querySelector('[data-state]')!.textContent!);
beforeEach(()=>{vi.useFakeTimers();window.sessionStorage.clear();(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;host=document.createElement('div');document.body.append(host);root=createRoot(host);});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();vi.useRealTimers();vi.unstubAllGlobals();});
async function enter(index:number,value:string){await act(async()=>{const input=host.querySelectorAll('input')[index];Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,value);input.dispatchEvent(new Event('input',{bubbles:true}));});}
async function submit(){await act(async()=>{host.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));});await flush();}
describe('rendered cookie-session journey (transport fixture, not deployed proof)',()=>{
 it('signs in, loads authorized data, and signs out without a JS operator key',async()=>{
  let signedIn=false;
  const mock=vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{
   expect(init?.credentials).toBe('include');
   const path=String(input);
   if(path.endsWith('/auth/login')){expect(JSON.parse(String(init?.body))).toEqual({principal_id:'owner',credential:'test-only'});signedIn=true;return json({role:'founder_ceo'});}
   if(path.endsWith('/auth/logout')){signedIn=false;return json({ok:true});}
   if(!signedIn)return json({error:'SESSION_REQUIRED'},401);
   if(path.endsWith('control/session'))return json({principal_id:'owner',role:'ceo'});
   if(path.endsWith('mla1517/status'))return json({schema_version:'chronus.mla1517.status/1',generated_at:new Date().toISOString(),ready_to_mine:{ready:false,reason:'fixture_no_pool'}});
   return json({evidence_available:false});
  });
  vi.stubGlobal('fetch',mock);await act(async()=>root.render(<Journey/>));await flush();
  expect(state().access.allowed).toBe(false);
  await enter(0,'owner');await enter(1,'test-only');await submit();
  expect(state().access.allowed).toBe(true);expect(state().status).not.toBeNull();
  expect(window.sessionStorage.getItem('pythia.operatorKey')).toBeNull();
  expect(window.sessionStorage.getItem('pythia.operatorPrincipal')).toBeNull();
  expect(host.querySelectorAll('input')[1].value).toBe('');
  await act(async()=>{(Array.from(host.querySelectorAll('button')).find(b=>b.textContent==='Sign out')!).click();});await flush();
  expect(state().access.allowed).toBe(false);expect(state().status).toBeNull();expect(state().evidence).toBeNull();
 });
 it('surfaces a refused login and clears the password without fetching mining status',async()=>{
  const mock=vi.fn(async(_input:RequestInfo|URL)=>json({error:'INVALID_CREDENTIAL'},401));vi.stubGlobal('fetch',mock);
  await act(async()=>root.render(<Journey/>));await flush();await enter(0,'owner');await enter(1,'wrong');await submit();
  expect(host.textContent).toContain('INVALID_CREDENTIAL');expect(state().access.allowed).toBe(false);
  expect(host.querySelectorAll('input')[1].value).toBe('');
  expect(mock.mock.calls.some(c=>String(c[0]).endsWith('mla1517/status'))).toBe(false);
 });
});
