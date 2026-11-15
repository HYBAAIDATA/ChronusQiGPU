`timescale 1ns/1ps
// Qualification counterexample: exact integer ring output is not 32-bit closed.
module tb_cyclotomic_overflow_finding;
  reg clk=0, rst_n=0, enable=0;
  reg signed [127:0] a_in=0, b_in=0;
  wire signed [127:0] c_out;
  wire valid_out;
  cyclotomic_mul_128bit dut(.clk(clk),.rst_n(rst_n),.enable(enable),.a_in(a_in),.b_in(b_in),.c_out(c_out),.valid_out(valid_out));
  always #5 clk=~clk;
  initial begin
    #2; rst_n=0; #10; rst_n=1;
    @(negedge clk); a_in=128'd65536; b_in=128'd65536; enable=1;
    @(posedge clk); #1;
    if (!valid_out) $fatal(1,"missing valid output");
    $display("inputs=(65536,0,0,0)*(65536,0,0,0)");
    $display("exact c0=4294967296, RTL packed c0=%0d", $signed(c_out[31:0]));
    // Compare widened signed output against the true unbounded coefficient.
    if ($signed({{32{c_out[31]}}, c_out[31:0]}) !== 64'sd4294967296)
      $fatal(1,"exact ring result is not representable by this output interface");
    $finish;
  end
endmodule
