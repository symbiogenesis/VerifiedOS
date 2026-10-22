// SPDX-License-Identifier: Apache-2.0
//
// The same immediate assertion is evaluated with and without the runtime lock.
// Its pass action witnesses actual evaluation; its failure message distinguishes
// an assertion refusal from a compiler refusal or an unrelated simulator crash.
module vos_assertion_policy_tb;
  initial begin
    $assertoff(0);
    $display("assertion-policy: disable requested");
    assert (!$test$plusargs("fail")) begin
      $display("assertion-policy: assertion passed");
    end else begin
      $fatal(1, "assertion-policy: assertion failed");
    end
    $display("assertion-policy: completed");
    $finish;
  end
endmodule
