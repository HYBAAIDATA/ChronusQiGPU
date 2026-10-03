"""
Benchmark Target 6: json_parser.py
"""
class SimpleJSONParser:
    def parse_number(self, s: str) -> float:
        return float(s.strip())

    def parse_string(self, s: str) -> str:
        return s.strip().strip('"')
