library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.std_logic_textio.all;
use std.textio.all;
use std.env.all;

entity tb_exact_datapath is
    generic (vectors_path : string := "phi_vectors.txt");
end entity;
architecture checks of tb_exact_datapath is
    signal clk : std_logic := '0';
    signal reset : std_logic := '1';
    signal valid_in, valid_out : std_logic := '0';
    signal xa, xb, ya, yb : signed(15 downto 0) := (others => '0');
    signal gx, gy, gf_product : unsigned(7 downto 0) := (others => '0');
    signal phi_a, phi_b : signed(33 downto 0);
    -- Independent polynomial long-reduction oracle, not the DUT's shift loop.
    function polynomial_product(x, y : natural) return unsigned is
        variable p : unsigned(15 downto 0) := (others => '0');
        constant modulus : unsigned(15 downto 0) := x"011b";
        variable xx : unsigned(15 downto 0) := to_unsigned(x, 16);
        variable yy : unsigned(7 downto 0) := to_unsigned(y, 8);
    begin
        for k in 0 to 7 loop
            if yy(k) = '1' then p := p xor shift_left(xx, k); end if;
        end loop;
        for k in 14 downto 8 loop
            if p(k) = '1' then p := p xor shift_left(modulus, k - 8); end if;
        end loop;
        return p(7 downto 0);
    end function;
begin
    clk <= not clk after 5 ns;
    dut : entity work.hyba port map(clk, reset, valid_in, xa, xb, ya, yb, gx, gy, phi_a, phi_b, gf_product, valid_out);
    process
        file vectors : text open read_mode is vectors_path;
        variable row : line;
        variable a, b, c, d : integer;
        variable ea, eb : std_logic_vector(63 downto 0);
        variable total : natural := 0;
    begin
        wait until rising_edge(clk);
        wait for 1 ns;
        assert valid_out = '0' severity failure;
        reset <= '0';
        while not endfile(vectors) loop
            readline(vectors, row);
            read(row, a); read(row, b); read(row, c); read(row, d);
            hread(row, ea); hread(row, eb);
            xa <= to_signed(a, 16); xb <= to_signed(b, 16);
            ya <= to_signed(c, 16); yb <= to_signed(d, 16);
            valid_in <= '1';
            wait until rising_edge(clk);
            wait for 1 ns;
            assert valid_out = '1' severity failure;
            assert resize(phi_a, 64) = signed(ea) report "Z[phi] coefficient a mismatch" severity failure;
            assert resize(phi_b, 64) = signed(eb) report "Z[phi] coefficient b mismatch" severity failure;
            total := total + 1;
        end loop;
        for x in 0 to 255 loop
            for y in 0 to 255 loop
                gx <= to_unsigned(x, 8); gy <= to_unsigned(y, 8);
                wait until rising_edge(clk);
                wait for 1 ns;
                assert gf_product = polynomial_product(x, y) report "GF(256) mismatch" severity failure;
            end loop;
        end loop;
        valid_in <= '0';
        wait until rising_edge(clk);
        wait for 1 ns;
        assert valid_out = '0' report "invalid input reported as valid" severity failure;
        report "PASS exact algebraic RTL: " & integer'image(total) & " phi vectors and 65536 GF products";
        stop;
        wait;
    end process;
end architecture;
