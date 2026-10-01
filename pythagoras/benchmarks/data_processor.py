"""
Benchmark Target 3: data_processor.py
"""
class DataProcessor:
    def process_records(self, records):
        out = []
        for r in records:
            val = r * 2.0
            out.append(val)
        return out
