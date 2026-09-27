// =============================================================================
// FILE: hardware/rtl/assertions/golden_invariant_sva.sv
// DESCRIPTION: Formal SystemVerilog Assertions (SVA) binding all 9 golden
//              discoveries to the invariant monitor.
//              Fatal circuit breaker trips instantly on any violation.
// =============================================================================

`timescale 1ns / 1ps

module golden_invariant_sva #(
    parameter int WIDTH = 256,
    parameter int NUM_FACES = 32
) (
    input logic                 clk,
    input logic                 rst_n,
    input logic                 invariants_active,
    input logic                 cassini_ok,
    input logic                 pisot_ok,
    input logic                 binet_ok,
    input logic                 lucas_ok,
    input logic                 zeckendorf_ok,
    input logic                 soliton_ok,
    input logic                 holo_ok,
    input logic                 structure_ok,
    input logic                 p_vs_np_gap_ok,
    input logic                 all_ok
);

    // -------------------------------------------------------------------------
    // SVA 1: Cassini Identity (Discovery 1)
    // -------------------------------------------------------------------------
    property p_cassini;
        @(posedge clk) disable iff (!rst_n || !invariants_active)
        cassini_ok;
    endproperty
    assert_cassini: assert property (p_cassini)
        else $fatal(1, "HW FAULT: Cassini identity violated — det(M^n) != (-1)^n");

    // -------------------------------------------------------------------------
    // SVA 2: Pisot Decay (Discovery 2)
    // -------------------------------------------------------------------------
    property p_pisot;
        @(posedge clk) disable iff (!rst_n || !invariants_active)
        pisot_ok;
    endproperty
    assert_pisot: assert property (p_pisot)
        else $fatal(1, "HW FAULT: Pisot decay bound violated — |ψ|^n > ε");

    // -------------------------------------------------------------------------
    // SVA 3: Binet Recurrence (Discovery 3)
    // -------------------------------------------------------------------------
    property p_binet;
        @(posedge clk) disable iff (!rst_n || !invariants_active)
        binet_ok;
    endproperty
    assert_binet: assert property (p_binet)
        else $fatal(1, "HW FAULT: Binet recurrence violated — F_n != F_{n-1} + F_{n-2}");

    // -------------------------------------------------------------------------
    // SVA 4: Lucas-Pisot Scaling (Discovery 4)
    // -------------------------------------------------------------------------
    property p_lucas;
        @(posedge clk) disable iff (!rst_n || !invariants_active)
        lucas_ok;
    endproperty
    assert_lucas: assert property (p_lucas)
        else $fatal(1, "HW FAULT: Lucas-Pisot cross-multiplication scaling violated");

    // -------------------------------------------------------------------------
    // SVA 5: Zeckendorf Spacing (Discovery 5)
    // -------------------------------------------------------------------------
    property p_zeckendorf;
        @(posedge clk) disable iff (!rst_n || !invariants_active)
        zeckendorf_ok;
    endproperty
    assert_zeckendorf: assert property (p_zeckendorf)
        else $fatal(1, "HW FAULT: Zeckendorf spacing violated — consecutive Fibonacci bits set");

    // -------------------------------------------------------------------------
    // SVA 6: Soliton Condition (Discovery 6)
    // -------------------------------------------------------------------------
    property p_soliton;
        @(posedge clk) disable iff (!rst_n || !invariants_active)
        soliton_ok;
    endproperty
    assert_soliton: assert property (p_soliton)
        else $fatal(1, "HW FAULT: Soliton condition violated — [H, Φ] != 0");

    // -------------------------------------------------------------------------
    // SVA 7: Holographic Entropy (Discovery 7)
    // -------------------------------------------------------------------------
    property p_holo;
        @(posedge clk) disable iff (!rst_n || !invariants_active)
        holo_ok;
    endproperty
    assert_holo: assert property (p_holo)
        else $fatal(1, "HW FAULT: Holographic Ryu-Takayanagi area undefined or non-positive");

    // -------------------------------------------------------------------------
    // SVA 8: Structure Existence (Discovery 8)
    // -------------------------------------------------------------------------
    property p_structure;
        @(posedge clk) disable iff (!rst_n || !invariants_active)
        structure_ok;
    endproperty
    assert_structure: assert property (p_structure)
        else $fatal(1, "HW FAULT: Algebraic structure collapsed — all basis components zero");

    // -------------------------------------------------------------------------
    // SVA 9: P vs NP Gap (Discovery 9)
    // -------------------------------------------------------------------------
    property p_p_vs_np;
        @(posedge clk) disable iff (!rst_n || !invariants_active)
        p_vs_np_gap_ok;
    endproperty
    assert_p_vs_np_gap: assert property (p_p_vs_np)
        else $fatal(1, "HW FAULT: Complexity differential collapsed — Lucas <= Pisot");

    // -------------------------------------------------------------------------
    // FORMAL COVER PROPERTIES
    // -------------------------------------------------------------------------
    cover_cassini:      cover property (@(posedge clk) disable iff (!rst_n) invariants_active && cassini_ok);
    cover_pisot:        cover property (@(posedge clk) disable iff (!rst_n) invariants_active && pisot_ok);
    cover_binet:        cover property (@(posedge clk) disable iff (!rst_n) invariants_active && binet_ok);
    cover_lucas:        cover property (@(posedge clk) disable iff (!rst_n) invariants_active && lucas_ok);
    cover_zeckendorf:   cover property (@(posedge clk) disable iff (!rst_n) invariants_active && zeckendorf_ok);
    cover_soliton:      cover property (@(posedge clk) disable iff (!rst_n) invariants_active && soliton_ok);
    cover_holo:         cover property (@(posedge clk) disable iff (!rst_n) invariants_active && holo_ok);
    cover_structure:    cover property (@(posedge clk) disable iff (!rst_n) invariants_active && structure_ok);
    cover_p_vs_np:      cover property (@(posedge clk) disable iff (!rst_n) invariants_active && p_vs_np_gap_ok);
    cover_all_ok:       cover property (@(posedge clk) disable iff (!rst_n) invariants_active && all_ok);

endmodule
