"""Packaged OpenCL kernels required by the production mining runtime.

The mining hasher resolves ``kernels/bitcoin_sha256d.cl`` relative to the
installed package root, so these data files must ship with the service rather
than relying on a source checkout.
"""
