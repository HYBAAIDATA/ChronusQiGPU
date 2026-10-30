"""Build the optional C++ accelerator (chronos._native); pure Python is the fallback."""

from setuptools import setup

try:
    from pybind11.setup_helpers import Pybind11Extension, build_ext

    ext_modules = [
        Pybind11Extension(
            "chronos._native",
            ["src/chronos/cpp/native.cpp"],
            cxx_std=17,
            extra_compile_args=["-O3", "-pthread"],
            extra_link_args=["-pthread"],
            optional=True,
        )
    ]
    cmdclass = {"build_ext": build_ext}
except ImportError:
    ext_modules, cmdclass = [], {}

setup(ext_modules=ext_modules, cmdclass=cmdclass)
