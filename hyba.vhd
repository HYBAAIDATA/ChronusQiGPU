-- Bounded exact Chronus arithmetic reference RTL. No timing closure is claimed.
-- Z[phi] coefficients are signed 16-bit inputs and full signed 34-bit outputs.
-- GF(2^8) uses x^8+x^4+x^3+x+1. Validity is delayed by one rising edge.
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity hyba is
    port (
        clk, reset, valid_in : in std_logic;
        xa, xb, ya, yb : in signed(15 downto 0);
        gx, gy : in unsigned(7 downto 0);
        phi_a, phi_b : out signed(33 downto 0);
        gf_product : out unsigned(7 downto 0);
        valid_out : out std_logic
    );
end entity;

architecture exact_datapath of hyba is
    function gf8_multiply(x, y : unsigned(7 downto 0)) return unsigned is
        variable a : unsigned(7 downto 0) := x;
        variable result : unsigned(7 downto 0) := (others => '0');
        variable carry : std_logic;
    begin
        for bit_index in 0 to 7 loop
            if y(bit_index) = '1' then
                result := result xor a;
            end if;
            carry := a(7);
            a := shift_left(a, 1);
            if carry = '1' then
                a := a xor x"1b";
            end if;
        end loop;
        return result;
    end function;
begin
    process(clk)
    begin
        if rising_edge(clk) then
            if reset = '1' then
                valid_out <= '0';
                phi_a <= (others => '0');
                phi_b <= (others => '0');
                gf_product <= (others => '0');
            else
                valid_out <= valid_in;
                if valid_in = '1' then
                    -- phi^2 = phi + 1; widen each product before summation.
                    phi_a <= resize(xa * ya, 34) + resize(xb * yb, 34);
                    phi_b <= resize(xa * yb, 34) + resize(xb * ya, 34) + resize(xb * yb, 34);
                    gf_product <= gf8_multiply(gx, gy);
                end if;
            end if;
        end if;
    end process;
end architecture;
