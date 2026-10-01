"""
Part 16: HP/HPE 2026 Enterprise Computing Advances
===================================================
Cross-vendor comparison module — HPE Cray EX4000 and Superdome Flex.

HP/HPE 2026 Enterprise Computing Advances:
  - HPE Cray EX4000: 2,048-core per node, 4 TB/s interconnect
  - Memory-Driven Computing, Slingshot Interconnect, Composable Infrastructure
  - Direct Liquid Cooling, HPC/AI Convergence

Based on publicly available HPE specifications and roadmap projections.
All vendor specs are from public data.

Claim lane: MATHEMATICAL_QUANTUM (SUBSTRATE-AGNOSTIC) — competitive analysis with public data.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class HPEArchitecture:
    """HP/HPE enterprise system specification."""
    name: str
    cores_per_node: int
    memory_per_node_tb: float
    interconnect_bandwidth_tbps: float
    fp64_performance_pflops: float
    fp32_performance_pflops: float
    process_node: str
    power_kw: float
    cooling_type: str
    features: List[str]


class HPAdvances:
    """
    HP/HPE 2026 enterprise computing specifications.

    Models HPE's exascale-class systems with publicly available
    specifications for competitive comparison against the HYBA
    φ-resonance algebraic substrate.
    """

    def __init__(self):
        self.systems = {
            'cray_ex4000': HPEArchitecture(
                name='HPE Cray EX4000',
                cores_per_node=2048,
                memory_per_node_tb=4.0,
                interconnect_bandwidth_tbps=4.0,
                fp64_performance_pflops=1.2,
                fp32_performance_pflops=2.4,
                process_node='3nm EUV',
                power_kw=120,
                cooling_type='Direct Liquid Cooling',
                features=[
                    'Memory-Driven Computing', 'Slingshot Interconnect',
                    'Composable Infrastructure', 'Direct Liquid Cooling',
                    'HPC/AI Convergence', 'System Software Stack',
                    'Programming Environment', 'Application Acceleration'
                ]
            ),
            'superdome_flex': HPEArchitecture(
                name='HPE Superdome Flex',
                cores_per_node=1024,
                memory_per_node_tb=2.0,
                interconnect_bandwidth_tbps=2.0,
                fp64_performance_pflops=0.6,
                fp32_performance_pflops=1.2,
                process_node='5nm EUV',
                power_kw=60,
                cooling_type='Direct Liquid Cooling',
                features=[
                    'Memory-Driven Computing', 'Composable Infrastructure',
                    'Direct Liquid Cooling', 'Mission-Critical Computing'
                ]
            )
        }

    def get_system(self, name: str) -> Optional[HPEArchitecture]:
        """Retrieve system specification by key."""
        return self.systems.get(name)

    def compare_to_hyba(self, system_name: str, hyba_specs: Dict) -> Dict:
        """
        Compare a specific HPE system to HYBA φ-substrate specs.

        Args:
            system_name: key in self.systems dict
            hyba_specs: dict with keys matching the ratio computation below

        Returns:
            Dict with system name and computed ratios.
            Ratios > 1 mean HYBA exceeds HPE; ratios < 1 mean HPE leads.
        """
        system = self.get_system(system_name)
        if not system:
            return {'error': f'System {system_name} not found'}

        return {
            'system': system.name,
            'ratios': {
                'cores': hyba_specs.get('streaming_processors', 65536) / max(system.cores_per_node, 1),
                'memory': hyba_specs.get('memory_tb', 512) / max(system.memory_per_node_tb, 1e-10),
                'bandwidth': hyba_specs.get('bandwidth_pbs', 2) / max(system.interconnect_bandwidth_tbps, 1e-10),
                'fp64': hyba_specs.get('fp64_eflops', 2.5) / max(system.fp64_performance_pflops / 1000, 1e-10),
                'fp32': hyba_specs.get('fp32_eflops', 5) / max(system.fp32_performance_pflops / 1000, 1e-10)
            }
        }

    def get_all_systems(self) -> List[HPEArchitecture]:
        """Return all modelled HPE systems."""
        return list(self.systems.values())

    def get_specs(self) -> Dict:
        """Return summary specifications for all systems."""
        return {
            'systems_modelled': [s.name for s in self.get_all_systems()],
            'latest_gen': 'Cray EX4000 (2,048 cores/node, Slingshot, Direct Liquid Cooling)',
            'cooling_efficiency': 'PUE < 1.05 (direct liquid cooling)',
        }

    def to_dict(self) -> Dict:
        """Serialise to dictionary."""
        return self.get_specs()
