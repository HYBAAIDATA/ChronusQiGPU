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
});
