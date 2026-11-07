// Known-answer testbench for the 32-lane carry-free Zeckendorf ALU array.
`timescale 1ns/1ps

module tb_zeckendorf_alu_32lane;
    reg  [32*64-1:0] zv_array_in;
    wire [32*65-1:0] zv_array_out;
    wire [31:0]      canonical_mask;
    wire             all_canonical;
    integer errors = 0;

    qigpu_zeckendorf_alu_32lane dut (
        .zv_array_in(zv_array_in),
        .zv_array_out(zv_array_out),
        .canonical_mask(canonical_mask),
        .all_canonical(all_canonical)
    );

    task check_cond(input cond, input [127:0] label);
        begin
            if (!cond) begin
                $display("FAIL: %0s", label);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        // All lanes zero: canonical, fold is identity.
        zv_array_in = {(32*64){1'b0}}; #1;
        check_cond(all_canonical === 1'b1, "zero array canonical");
        check_cond(zv_array_out === {(32*65){1'b0}}, "zero fold identity");

        // Lane 0 holds 0b011 (F2 + F3): folds to F4, lane not canonical.
        zv_array_in = {(32*64){1'b0}};
        zv_array_in[0 +: 64] = 64'b011; #1;
        check_cond(all_canonical === 1'b0, "non-canonical lane detected");
        check_cond(canonical_mask[0] === 1'b0, "lane 0 flagged");
        check_cond(canonical_mask[31:1] === 31'h7FFFFFFF, "other lanes canonical");
        check_cond(zv_array_out[0 +: 65] === 65'b100, "lane 0 folded 011 -> 100");

        // Lane 31 folds independently of lane 0.
        zv_array_in = {(32*64){1'b0}};
        zv_array_in[31*64 +: 64] = 64'b011; #1;
        check_cond(zv_array_out[31*65 +: 65] === 65'b100, "lane 31 folded 011 -> 100");
        check_cond(canonical_mask === 32'h7FFFFFFF, "only lane 31 non-canonical");

        // Every lane carries 0b011: full-array parallel fold in one sweep.
        zv_array_in = {32{64'b011}}; #1;
        check_cond(all_canonical === 1'b0, "full array non-canonical");
        check_cond(zv_array_out === {32{65'b100}}, "all 32 lanes folded in parallel");

        // Canonical registers pass through unchanged and report canonical.
        zv_array_in = {32{64'b1010101010101010}}; #1;
        check_cond(all_canonical === 1'b1, "canonical array reported");
        check_cond(zv_array_out === {32{65'b1010101010101010}}, "canonical passthrough");

        // Overlap pattern 1111 preserves value: F2..F5 = 11 = F4 + F6.
        zv_array_in = {(32*64){1'b0}};
        zv_array_in[0 +: 64] = 64'b1111; #1;
        check_cond(zv_array_out[0 +: 65] === 65'b10100, "1111 -> 10100 value preserved");

        if (errors == 0) $display("TB PASS");
        else begin $display("TB FAIL: %0d errors", errors); $fatal(1); end
        $finish;
    end
endmodule
