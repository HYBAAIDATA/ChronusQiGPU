"""
Family registry — maps family numbers to their test functions.
"""

from .results import CheckRegistry

FAMILY_REGISTRY = [
    {"num": 1, "name": "φ + Lucas",           "purpose": "SCALING",   "module": "families.scaling"},
    {"num": 2, "name": "φ + Binet/Pisot",     "purpose": "FOLDING",   "module": "families.folding"},
    {"num": 3, "name": "φ + Fibonacci",       "purpose": "STORING",   "module": "families.storing"},
    {"num": 4, "name": "φ + Cassini",         "purpose": "SIGNAL",    "module": "families.signal"},
    {"num": 5, "name": "φ + Eigenstructure",  "purpose": "TRANSFORM", "module": "families.transform"},
    {"num": 6, "name": "φ + Continued Frac",  "purpose": "SAMPLING",  "module": "families.sampling"},
    {"num": 7, "name": "φ + Golden Angle",    "purpose": "LAYOUT",     "module": "families.layout"},
    {"num": 8, "name": "φ + KAM",             "purpose": "STABILITY",  "module": "families.stability"},
    {"num": 9, "name": "Runtime Infrastructure", "purpose": "RUNTIME",  "module": "families.runtime"},
    {"num": 10, "name": "Mathematical Identities", "purpose": "IDENTITIES", "module": "families.hyba_math"},
]
