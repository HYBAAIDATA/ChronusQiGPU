# Chronus Production Configuration
import os

class ChronusConfig:
    VERSION = "36.0.0"
    ENVIRONMENT = os.environ.get("CHRONUS_ENV", "production")
    OUT_DIR = os.environ.get("CHRONUS_OUT_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../manifests")))
    MAX_SRAM_BYTES = 64 * 1024
    MAX_DRAM_BYTES = 64 * 1024 * 1024
    DEFAULT_REGION = "us-east-1"
