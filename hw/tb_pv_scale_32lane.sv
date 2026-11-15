// Known-answer testbench: PV companion-matrix scaling in hardware.
`timescale 1ns/1ps

module tb_pv_scale_32lane;
    reg clk = 0;
    reg load = 0;
    reg step = 0;
    reg signed [32*64-1:0] a_array;
    reg signed [32*64-1:0] b_array;
    wire signed [32*64-1:0] a_scaled;
    wire signed [32*64-1:0] b_scaled;
    integer errors = 0;
    integer k;

    qigpu_pv_scale_32lane dut (
        .clk(clk), .load(load), .step(step),
        .a_array(a_array), .b_array(b_array),
        .a_scaled(a_scaled), .b_scaled(b_scaled)
    );

    always #1 clk = ~clk;

    task check_lane(input integer lane, input [63:0] ea, input [63:0] eb);
        begin
            if (a_scaled[lane*64 +: 64] !== ea || b_scaled[lane*64 +: 64] !== eb) begin
                $display("FAIL lane %0d: got (%0d, %0d), expected (%0d, %0d)",
                         lane, a_scaled[lane*64 +: 64], b_scaled[lane*64 +: 64], ea, eb);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        // Lane 0 climbs the Fibonacci ladder from phi^1 = (0, 1).
        // Lane 1 climbs the Lucas ladder from (2, 1).
        // Lane 2 carries a mixed lattice element (3, -2) for composition checks.
        // All other lanes hold (1, 0) = phi^0, the identity anchor.
        a_array = {(32*64){1'b0}};
        b_array = {(32*64){1'b0}};
        a_array[0 +: 64] = 64'sd0;  b_array[0 +: 64] = 64'sd1;
        a_array[64 +: 64] = 64'sd2; b_array[64 +: 64] = 64'sd1;
        a_array[128 +: 64] = 64'sd3; b_array[128 +: 64] = -64'sd2;
        for (k = 3; k < 32; k = k + 1) begin
            a_array[k*64 +: 64] = 64'sd1;
            b_array[k*64 +: 64] = 64'sd0;
        end
        load = 1;
        @(posedge clk);
        #1 load = 0;

        // 10 steps: lane 0 -> phi^11 = (F_10, F_11) = (55, 89).
        step = 1;
        for (k = 0; k < 10; k = k + 1) @(posedge clk);
        #1;
        check_lane(0, 64'sd55, 64'sd89);
        // Lane 1 after 10 steps from (2,1): L_11 = 199, L_12 = 322? ladder is
        // (L_k, L_{k+1}) after k steps: (2,1)->k=10 -> (L_10, L_11) = (123, 199).
        check_lane(1, 64'sd123, 64'sd199);
        // Identity lanes must still be (F_9, F_10) = (34, 55) after 10 steps
        // from phi^0 = (1,0): (a,b)*phi^10 = (F_9, F_10).
        check_lane(3, 64'sd34, 64'sd55);

        // 80 more steps: lane 0 reaches phi^91 = (F_90, F_91).
        for (k = 0; k < 80; k = k + 1) @(posedge clk);
        #1;
        check_lane(0, 64'sd2880067194370816120, 64'sd4660046610375530309);
        // Lane 1 reaches (L_90, L_91); L_91 = 2*F_92 - F_91.
        check_lane(1, 64'sd6440026026380244498, 64'sd10420180999117162549);

        if (errors == 0) $display("TB PASS");
        else begin $display("TB FAIL: %0d errors", errors); $fatal(1); end
        $finish;
    end
endmodule
