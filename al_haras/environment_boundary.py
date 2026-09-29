"""Classify environmental failures without turning missing tools into passes."""
from enum import Enum
class FailureClass(str,Enum):ENV_LEAK="ENV_LEAK";ENV_MISSING_DECLARED_DEP="ENV_MISSING_DECLARED_DEP";PLATFORM_POSIX_ONLY="PLATFORM_POSIX_ONLY";PLATFORM_CHARMAP="PLATFORM_CHARMAP";GENUINE_DRIFT="GENUINE_DRIFT";UNCLASSIFIED="UNCLASSIFIED"
DRIFT_TESTS={"test_operating_model.test_substrate_freeze_sha_1","test_operating_model.test_substrate_freeze_sha_2","test_system_fabric.test_forensic_map_names"}
def classify_failure(test_name:str,error:BaseException,platform:str)->FailureClass:
 text=str(error)
 if isinstance(error,ModuleNotFoundError) and "turing_universal_quantum_computer" in text:return FailureClass.ENV_LEAK
 if isinstance(error,(ImportError,ModuleNotFoundError)) and any(dep in text for dep in ("sympy","fastapi")):return FailureClass.ENV_MISSING_DECLARED_DEP
 if isinstance(error,ImportError) and "fcntl" in text:return FailureClass.PLATFORM_POSIX_ONLY
 if isinstance(error,UnicodeDecodeError) and platform.casefold().startswith("win"):return FailureClass.PLATFORM_CHARMAP
 if isinstance(error,AssertionError) and test_name in DRIFT_TESTS:return FailureClass.GENUINE_DRIFT
 return FailureClass.UNCLASSIFIED
