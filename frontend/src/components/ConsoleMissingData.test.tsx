import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Mla1517MiningPanel } from "./Mla1517MiningPanel";
import { MiningEvidencePanel } from "./MiningEvidencePanel";
describe("incomplete backend documents", () => {
  it("never renders undefined/NaN endpoints or arm bounds", () => {
    const html=renderToStaticMarkup(<Mla1517MiningPanel status={{host:{stratum:{} as any},runtime:{},console:{}}} ready={null} offline={false}/>);
    expect(html).not.toContain("undefined");expect(html).not.toContain("NaN");
    expect(html).toContain("arm bounds not reported");expect(html).toContain("not reported");
  });
  it("does not invent missing receipt fields or claim pool acceptance", () => {
    const html=renderToStaticMarkup(<MiningEvidencePanel evidence={null} offline={false}/>);
    expect(html).toContain("not reported");expect(html).not.toContain("receipt_id: 0");
  });
  it("preserves a backend-reported zero share count",()=>{
    const html=renderToStaticMarkup(<Mla1517MiningPanel status={{workers:{test:{state:"running",effectiveness:{hashrate:0,shares_accepted:0}} as any}}} ready={null} offline={false}/>);
    expect(html).toContain("0 H/s");expect(html).toMatch(/shares.*?0<\/span>/s);
  });
});
