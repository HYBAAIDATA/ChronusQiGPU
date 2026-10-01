"""Real-world dataset references (metadata only, no bulk downloads).

Each entry is a citation-quality reference to a public dataset that maps
into one of the four application case studies. Populated lazily; no network
calls are made at import time.
"""
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class DatasetRef:
    name: str
    url: str
    domain: str
    citation: str
    licence: str = "see source"
    notes: str = ""


DATASETS: List[DatasetRef] = [
    DatasetRef(
        name="CERN Open Data - CMS 2015 Higgs 4-lepton",
        url="http://opendata.cern.ch/record/5500",
        domain="particle_physics",
        citation="CMS collaboration, CERN Open Data Portal.",
        licence="CC0",
    ),
    DatasetRef(
        name="ERA5 hourly reanalysis (Copernicus)",
        url="https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-single-levels",
        domain="climate",
        citation="Hersbach et al., 2020, QJRMS.",
        licence="Copernicus Licence",
    ),
    DatasetRef(
        name="NCBI Reference Sequences (RefSeq)",
        url="https://www.ncbi.nlm.nih.gov/refseq/",
        domain="genomics",
        citation="O'Leary et al., 2016, NAR.",
    ),
    DatasetRef(
        name="QM9 molecular property dataset",
        url="http://quantum-machine.org/datasets/",
        domain="quantum_chemistry",
        citation="Ramakrishnan et al., 2014, Scientific Data.",
        licence="CC BY 4.0",
    ),
]


def by_domain(domain: str) -> List[DatasetRef]:
    return [d for d in DATASETS if d.domain == domain]


def summary() -> Dict[str, int]:
    d: Dict[str, int] = {}
    for ref in DATASETS:
        d[ref.domain] = d.get(ref.domain, 0) + 1
    return d
