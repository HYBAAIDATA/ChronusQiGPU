// =============================================================================
// CHRONUS QUANTUM iGPU: TESTBENCH FOR 128-BIT CYCLOTOMIC MULTIPLIER
// =============================================================================

`timescale 1ns / 1ps

module tb_cyclotomic_mul_128bit;

    reg clk;
    reg rst_n;
    reg enable;
    reg signed [127:0] a_in;
    reg signed [127:0] b_in;
    wire signed [127:0] c_out;
    wire valid_out;

    // Instantiate Unit Under Test (UUT)
    cyclotomic_mul_128bit uut (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .a_in(a_in),
        .b_in(b_in),
        .c_out(c_out),
        .valid_out(valid_out)
    );

    // Clock generator: 100 MHz (10ns period)
    always #5 clk = ~clk;

    // Helper functions to pack 4 signed coefficients into 128-bit word
    function signed [127:0] pack_z5(
        input signed [31:0] c0,
        input signed [31:0] c1,
        input signed [31:0] c2,
        input signed [31:0] c3
    );
        pack_z5 = {c3, c2, c1, c0};
    endfunction

    integer errors = 0;

    initial begin
        clk = 0;
        rst_n = 0;
        enable = 0;
        a_in = 0;
        b_in = 0;

        #20;
        rst_n = 1;
        #10;

        // ---------------------------------------------------------------------
        // TEST 1: Identity Multiplication A * 1 == A
        // A = (5, -7, 11, -13), 1 = (1, 0, 0, 0)
        // ---------------------------------------------------------------------
        @(posedge clk);
        enable <= 1;
        a_in   <= pack_z5(32'sd5, -32'sd7, 32'sd11, -32'sd13);
        b_in   <= pack_z5(32'sd1, 32'sd0, 32'sd0, 32'sd0);

        @(posedge clk);
        #1;
        if (c_out !== pack_z5(32'sd5, -32'sd7, 32'sd11, -32'sd13)) begin
            $display("[FAIL] Test 1: Identity Failed. Got: %h", c_out);
            errors = errors + 1;
        end else begin
            $display("[PASS] Test 1: Identity Multiplication (A * 1 == A)");
        end

        // ---------------------------------------------------------------------
        // TEST 2: Fundamental Root Multiplication zeta * zeta^4 == 1
        // zeta   = (0, 1, 0, 0)
        // zeta^4 = (-1, -1, -1, -1)
        // Product must be 1 = (1, 0, 0, 0)
        // ---------------------------------------------------------------------
        @(posedge clk);
        a_in <= pack_z5(32'sd0, 32'sd1, 32'sd0, 32'sd0);
        b_in <= pack_z5(-32'sd1, -32'sd1, -32'sd1, -32'sd1);

        @(posedge clk);
        #1;
        if (c_out !== pack_z5(32'sd1, 32'sd0, 32'sd0, 32'sd0)) begin
            $display("[FAIL] Test 2: Root Product Failed. Got: %h", c_out);
            errors = errors + 1;
        end else begin
            $display("[PASS] Test 2: Fundamental Root Product (zeta * zeta^4 == 1)");
        end

        // ---------------------------------------------------------------------
        // TEST 3: Golden Ratio Invariant phi * phi == phi + 1
        // phi = -(zeta^2 + zeta^3) = (0, 0, -1, -1)
        // phi^2 must be (1, 0, -1, -1) == 1 + phi
        // ---------------------------------------------------------------------
        @(posedge clk);
        a_in <= pack_z5(32'sd0, 32'sd0, -32'sd1, -32'sd1);
        b_in <= pack_z5(32'sd0, 32'sd0, -32'sd1, -32'sd1);

        @(posedge clk);
        #1;
        if (c_out !== pack_z5(32'sd1, 32'sd0, -32'sd1, -32'sd1)) begin
            $display("[FAIL] Test 3: Golden Ratio Squared Failed. Got: %h", c_out);
            errors = errors + 1;
        end else begin
            $display("[PASS] Test 3: Golden Ratio Invariant (phi^2 == phi + 1)");
        end

        // ---------------------------------------------------------------------
        // TEST 4: Complex Multi-Coefficient Test Vector
        // A = (2, 3, 5, 7)
        // B = (11, 13, 17, 19)
        // Expected: (3, -41, -105, -2)
        // ---------------------------------------------------------------------
        @(posedge clk);
        a_in <= pack_z5(32'sd2, 32'sd3, 32'sd5, 32'sd7);
        b_in <= pack_z5(32'sd11, 32'sd13, 32'sd17, 32'sd19);

        @(posedge clk);
        #1;
        if (c_out !== pack_z5(32'sd3, -32'sd41, -32'sd105, -32'sd2)) begin
            $display("[FAIL] Test 4: Complex Multiplier Test Vector Failed. Got: %h", c_out);
            errors = errors + 1;
        end else begin
            $display("[PASS] Test 4: Complex Multiplier Vector (A * B == Expected)");
        end

        // Final Summary
        #20;
        if (errors == 0) begin
            $display("=================================================================");
            $display(" ALL 4 CYCLOTOMIC MULTIPLIER TESTS PASSED IN EXACT 1 CLOCK CYCLE ");
            $display(" TB PASS: cyclotomic_mul_128bit");
            $display("=================================================================");
        end else begin
            $display("FAILED with %0d errors", errors);
        end

        $finish;
    end

endmodule
