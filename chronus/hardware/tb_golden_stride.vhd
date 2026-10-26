library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.all;

entity tb_golden_stride is end entity;
architecture checks of tb_golden_stride is
    signal clk : std_logic := '0';
    signal reset : std_logic := '1';
    signal start, ready, valid : std_logic := '0';
    signal seed, nonce : unsigned(31 downto 0) := (others => '0');
    signal level : natural range 0 to 8;
begin
    clk <= not clk after 5 ns;
    dut : entity work.chronus_golden_stride port map(clk, reset, start, seed, ready, valid, nonce, level);
    process
        variable expected, stalled : unsigned(31 downto 0);
        variable accepted : natural := 0;
        variable was_stalled : boolean := false;
    begin
        wait until rising_edge(clk);
        wait for 1 ns;
        assert valid = '0' and level = 0 severity failure;
        reset <= '0';
        for trial in 0 to 2 loop
            if trial = 0 then seed <= x"00000539";
            elsif trial = 1 then seed <= x"0000002a";
            else seed <= x"fffffffa";
            end if;
            start <= '1';
            wait until rising_edge(clk);
            wait for 1 ns;
            expected := seed;
            start <= '0';
            ready <= '0';
            -- Fill, then hold. The head must remain stable under backpressure.
            for cycle in 1 to 10 loop
                wait until rising_edge(clk);
                wait for 1 ns;
            end loop;
            assert level = 8 and nonce = expected severity failure;
            was_stalled := false;
            for cycle in 0 to 127 loop
                if cycle mod 7 < 3 then ready <= '0'; else ready <= '1'; end if;
                wait until falling_edge(clk);
                if was_stalled then assert valid = '1' and nonce = stalled severity failure; end if;
                was_stalled := valid = '1' and ready = '0';
                stalled := nonce;
                if valid = '1' and ready = '1' then
                    assert nonce = expected report "golden-stride ordering mismatch" severity failure;
                    expected := expected + x"9e3779b9";
                    accepted := accepted + 1;
                end if;
                wait until rising_edge(clk);
                wait for 1 ns;
            end loop;
            ready <= '0';
        end loop;
        reset <= '1';
        wait until rising_edge(clk);
        wait for 1 ns;
        assert valid = '0' and level = 0 severity failure;
        assert accepted > 100 severity failure;
        report "PASS golden FIFO: backpressure, reset, reseed and uint32 wrap";
        stop;
        wait;
    end process;
end architecture;
