"""Canonical MLA1517 platform scripts package.

Regular package marker: a site-packages .pth may inject sibling repos onto
sys.path (e.g. HYBA_Phi-main); a namespace ``scripts`` directory would lose
import resolution to those foreign regular packages. This file pins
``import scripts.*`` to this directory.
"""
