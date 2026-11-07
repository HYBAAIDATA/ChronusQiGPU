// Known-answer testbench for the QiGPU phi-ALU.
`timescale 1ns/1ps

module tb_qigpu_phi_alu;
    reg  [8:0]  a, b;
    reg  [63:0] zv_in;
    wire [8:0]  norm;
    wire [64:0] zv_out;
    integer errors = 0;

    qigpu_phi_alu dut (.a(a), .b(b), .zv_in(zv_in), .norm(norm), .zv_out(zv_out));

    task check_norm(input [8:0] x, input [8:0] y, input [8:0] expected);
        begin
            a = x; b = y; zv_in = 64'd0; #1;
            if (norm !== expected) begin
                $display("NORM FAIL: N(%0d,%0d) = %0d, expected %0d", x, y, norm, expected);
                errors = errors + 1;
            end
        end
    endtask

    task check_fold(input [63:0] in, input [64:0] expected);
        begin
            a = 9'd0; b = 9'd0; zv_in = in; #1;
            if (zv_out !== expected) begin
                $display("FOLD FAIL: fold(%b) = %b, expected %b", in, zv_out, expected);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        // Galois norm over F_257[phi]: N(a,b) = a^2 + a*b - b^2 mod 257.
        check_norm(9'd1,   9'd0,   9'd1);    // N(1) = 1
        check_norm(9'd0,   9'd1,   9'd256);  // N(phi) = -1
        check_norm(9'd1,   9'd1,   9'd1);    // N(1+phi) = 1
        check_norm(9'd3,   9'd4,   9'd5);    // 9 + 12 - 16 = 5
        check_norm(9'd256, 9'd255, 9'd256);  // (-1)^2 + (-1)(-2) - (-2)^2 = -1 mod 257
        check_norm(9'd200, 9'd111, 9'd21);   // 40000+22200-12321 = 49879 = 194*257 + 21

        // Carry-free fold sweep: 011 -> 100 on even pairs only.
        check_fold(64'b011, 65'b100);                 // F2 + F3 -> F4
        check_fold(64'b011011, 65'b11100);            // even pair folds; odd pair waits
        check_fold(64'b1111, 65'b10100);              // F2..F5 = 11 = F4 + F6
        check_fold(64'b10101010, 65'b10101010);       // canonical input unchanged
        check_fold(64'b0, 65'b0);                     // zero stays zero

        if (errors == 0) $display("TB PASS");
        else begin $display("TB FAIL: %0d errors", errors); $fatal(1); end
        $finish;
    end
endmodule
