import unittest
from fractions import Fraction
from itertools import product
from hyba.unification.field import QPhi

Z, O, P = QPhi(0, 0), QPhi(1, 0), QPhi(0, 1)

class Invariant(unittest.TestCase):
    def test_bounded_exhaustive_roundtrip(self):
        for a, b in product(range(-4, 5), repeat=2):
            x = QPhi(a,b)
            self.assertEqual(QPhi.from_cyclotomic_coordinates(x.cyclotomic_coordinates()), x)
            self.assertEqual(x + Z, x)
            self.assertEqual(x * O, x)
            if x != Z: self.assertEqual(x * x.inverse(), O)

class Adversarial(unittest.TestCase):
    def test_bad_coefficients_and_nonreal_rejected(self):
        for x in (1.5, True, '3', None, float('nan')):
            with self.assertRaises(TypeError): QPhi(x, 0)
            with self.assertRaises(TypeError): QPhi.from_cyclotomic_coordinates((x,0,0,0))
        for x in ((0,1,0,0), (0,0,1,0), (), 'bad'):
            with self.assertRaises(ValueError): QPhi.from_cyclotomic_coordinates(x)
        with self.assertRaises(ValueError): QPhi(Fraction(1,2),0).integral_cyclotomic_coordinates()

class Edge(unittest.TestCase):
    def test_phi_powers_and_zero(self):
        self.assertEqual(P * P, P + O)
        self.assertEqual(P ** 0, O)
        self.assertEqual(P ** -1, P - O)
        a,b = 0,1
        for n in range(1,101):
            self.assertEqual(P**n, QPhi(a,b)); a,b=b,a+b
        with self.assertRaises(ZeroDivisionError): Z.inverse()
        with self.assertRaises(ZeroDivisionError): Z ** -1
        with self.assertRaises(TypeError): P ** 0.5

class Unit(unittest.TestCase):
    def test_arithmetic(self):
        x,y=QPhi(Fraction(1,2), 2),QPhi(3,-1)
        self.assertEqual(x+y,QPhi(Fraction(7,2),1))
        self.assertEqual(x-y,QPhi(Fraction(-5,2),3))
        self.assertEqual(-x,QPhi(Fraction(-1,2),-2))
        self.assertEqual(x*y,QPhi(Fraction(-1,2),Fraction(7,2)))
        self.assertEqual((x/y)*y,x)
        self.assertEqual(P.integral_cyclotomic_coordinates(),(0,0,-1,-1))
        with self.assertRaises(TypeError): x + 1
        with self.assertRaises(TypeError): x - 1
        with self.assertRaises(TypeError): x * 1
        with self.assertRaises(TypeError): x / 1

if __name__ == '__main__': unittest.main()
