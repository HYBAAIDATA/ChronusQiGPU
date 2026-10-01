import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Header } from "./Header";

describe("Header", () => {
  it("labels a CPU-hosted logical substrate without claiming OpenCL", () => {
    const html = renderToStaticMarkup(
      <Header
        offline={false}
        ready={{ ready: false, reason: "worker_unavailable" }}
        status={{
          gpu: {
            available: true,
            opencl_device_count: 0,
            physical_gpu_available: false,
            logical_substrate: {
              name: "hyba-super-gpu",
              available: true,
              active: false,
              host_backend: "cpu",
              fallback_used: true,
            },
          },
        }}
      />,
    );

    expect(html).toContain("Super-GPU · CPU host");
    expect(html).not.toContain("OpenCL ×1");
  });

  it("labels the Chronus contract device as the system GPU identity", () => {
    const html = renderToStaticMarkup(
      <Header
        offline={false}
        ready={{ ready: false, reason: "worker_unavailable" }}
        status={{
          gpu: {
            available: true,
            opencl_device_count: 0,
            physical_gpu_available: false,
            contract_device: { name: "MLA1517 iGPU", vendor: "hyba", backend: "chronus" },
            logical_substrate: {
              name: "hyba-super-gpu",
              available: true,
              active: false,
              host_backend: "cpu",
              fallback_used: true,
            },
          },
        }}
      />,
    );

    expect(html).toContain("Chronus · MLA1517 iGPU");
    expect(html).not.toContain("Super-GPU · CPU host");
  });
});
