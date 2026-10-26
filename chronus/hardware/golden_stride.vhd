-- Chronus golden-stride ordering generator with a fixed Fibonacci(6) FIFO.
-- Arithmetic is explicitly modulo 2^32, matching the OpenCL nonce contract.
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity chronus_golden_stride is
    port (
        clk, reset, start : in std_logic;
        seed : in unsigned(31 downto 0);
        out_ready : in std_logic;
        out_valid : out std_logic;
        nonce : out unsigned(31 downto 0);
        level : out natural range 0 to 8
    );
end entity;

architecture ring_fifo of chronus_golden_stride is
    function fibonacci(n : natural) return natural is
        variable a : natural := 0;
        variable b : natural := 1;
        variable next_value : natural;
    begin
        for i in 1 to n loop
            next_value := a + b;
            a := b;
            b := next_value;
        end loop;
        return a;
    end function;
    constant depth : positive := fibonacci(6);
    constant stride : unsigned(31 downto 0) := x"9E3779B9";
    type fifo_type is array(0 to depth - 1) of unsigned(31 downto 0);
    signal fifo : fifo_type := (others => (others => '0'));
    signal head, tail : natural range 0 to depth - 1 := 0;
    signal count : natural range 0 to depth := 0;
    signal cursor : unsigned(31 downto 0) := (others => '0');
    signal running : boolean := false;
begin
    assert depth = 8 report "golden FIFO must be Fibonacci(6) = 8" severity failure;
    out_valid <= '1' when count > 0 else '0';
    nonce <= fifo(head);
    level <= count;
    process(clk)
        variable pop, push : boolean;
    begin
        if rising_edge(clk) then
            if reset = '1' then
                head <= 0;
                tail <= 0;
                count <= 0;
                running <= false;
                cursor <= (others => '0');
            elsif start = '1' then
                head <= 0;
                tail <= 0;
                count <= 0;
                cursor <= seed;
                running <= true;
            else
                pop := count > 0 and out_ready = '1';
                push := running and (count < depth or pop);
                if pop then
                    head <= (head + 1) mod depth;
                end if;
                if push then
                    fifo(tail) <= cursor;
                    cursor <= cursor + stride;
                    tail <= (tail + 1) mod depth;
                end if;
                if push and not pop then
                    count <= count + 1;
                elsif pop and not push then
                    count <= count - 1;
                end if;
            end if;
        end if;
    end process;
end architecture;
