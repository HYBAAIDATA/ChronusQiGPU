"""Optional native extension; portable C by default, OpenSSL when explicitly requested."""
from setuptools import setup,Extension
import os
use_crypto=os.environ.get('CHRONOS_USE_OPENSSL')=='1'
extensions=[] if os.environ.get('CHRONOS_DISABLE_NATIVE')=='1' else [Extension('chronos_one_igpu.igpu._sha256d_native',sources=['src/chronos_one_igpu/igpu/native/sha256d_native.c'],optional=not use_crypto,libraries=['crypto']if use_crypto else[],define_macros=[('CHRONOS_OPENSSL','1')]if use_crypto else[])]
if os.environ.get('CHRONOS_DISABLE_NATIVE')!='1':extensions.append(Extension('chronos_one_igpu.igpu._structured_native',sources=['src/chronos_one_igpu/igpu/native/structured_native.c'],optional=True))
setup(ext_modules=extensions)
