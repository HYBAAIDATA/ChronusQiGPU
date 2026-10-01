"""PYTHAGORAS v12 benchmark target: JSON parser primitives."""


class SimpleJSONParser:
    def parse_number(self, value: str) -> float:
        return float(value.strip())

    def parse_string(self, value: str) -> str:
        return value.strip().strip('"')
