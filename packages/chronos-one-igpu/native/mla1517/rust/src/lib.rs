#![deny(unsafe_code)]

pub fn fibonacci(n: usize) -> u128 {
    let (mut a, mut b) = (0u128, 1u128);
    for _ in 0..n { (a, b) = (b, a + b); }
    a
}

pub fn lucas(n: usize) -> u128 {
    let (mut a, mut b) = (2u128, 1u128);
    for _ in 0..n { (a, b) = (b, a + b); }
    a
}

pub fn cassini(n: usize) -> i128 {
    fibonacci(n.saturating_sub(1)) as i128 * fibonacci(n + 1) as i128
        - fibonacci(n) as i128 * fibonacci(n) as i128
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn verified_values() {
        assert_eq!(fibonacci(15), 610);
        assert_eq!(lucas(15), 1364);
        for n in 1..=40 { assert_eq!(cassini(n), if n % 2 == 0 { 1 } else { -1 }); }
    }
}
