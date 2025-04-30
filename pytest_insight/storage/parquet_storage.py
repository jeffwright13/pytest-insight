"""
ParquetStorage: Parquet-backed storage profile for pytest-insight TestSession objects.

- Stores and loads full TestSession (with rerun groups, preserving context)
- Uses pandas/pyarrow for Parquet I/O
- Serializes complex/nested fields as JSON strings
- Designed to be used as a plug-in storage profile (not core)
"""
import json
from typing import List, Optional
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pytest_insight.core.models import TestSession

class ParquetStorage:
    """
    Parquet-backed storage for TestSession objects.
    Stores each session as a row, serializing nested fields to JSON.
    """
    def __init__(self, path: str):
        self.path = path

    def save_sessions(self, sessions: List[TestSession]) -> None:
        """Save a list of TestSession objects to Parquet."""
        records = [self._session_to_row(s) for s in sessions]
        df = pd.DataFrame(records)
        table = pa.Table.from_pandas(df)
        pq.write_table(table, self.path)

    def load_sessions(self, batch_size: int = 1000) -> List[TestSession]:
        """Load TestSession objects from Parquet file using chunked/lazy loading."""
        import logging
        import pyarrow.parquet as pq
        session_rows = []
        try:
            parquet_file = pq.ParquetFile(self.path)
            for batch in parquet_file.iter_batches(batch_size):
                df = batch.to_pandas()
                for _, row in df.iterrows():
                    try:
                        py_row = self._to_py(dict(row))
                        session_rows.append(py_row)
                    except Exception as e:
                        logging.error(f"Failed to convert row: {row}\nError: {e}")
                        session_rows.append({k: str(v) for k, v in dict(row).items()})
        except Exception as e:
            logging.error(f"Failed to load Parquet file: {self.path}\nError: {e}")
            return []
        # Defensive: ensure all fields in all rows are serializable
        def force_str(obj):
            import json
            try:
                json.dumps(obj)
                return obj
            except Exception:
                if isinstance(obj, dict):
                    return {k: force_str(v) for k, v in obj.items()}
                if isinstance(obj, (list, tuple)):
                    return [force_str(x) for x in obj]
                return str(obj)
        session_rows = [force_str(row) for row in session_rows]
        # DEBUG: Print type and content of every row
        for idx, row in enumerate(session_rows):
            print(f"[DEBUG] Session row {idx}: type={type(row)}, content={row}")
        return [self._row_to_session(row) for row in session_rows]

    @staticmethod
    def _to_py(obj):
        """Recursively convert pyarrow/numpy objects to python lists/dicts/primitives."""
        import numpy as np
        import pyarrow as pa
        # Handle None
        if obj is None:
            return None
        # Handle pyarrow scalars
        if hasattr(pa, 'Scalar') and isinstance(obj, pa.Scalar):
            return obj.as_py()
        # Handle chunked arrays and arrays
        if hasattr(pa, 'ChunkedArray') and isinstance(obj, pa.ChunkedArray):
            return [ParquetStorage._to_py(x) for x in obj.to_pylist()]
        if hasattr(pa, 'Array') and isinstance(obj, pa.Array):
            return [ParquetStorage._to_py(x) for x in obj.to_pylist()]
        if hasattr(obj, 'to_pylist') and callable(obj.to_pylist):
            return [ParquetStorage._to_py(x) for x in obj.to_pylist()]
        # Handle numpy arrays
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        # Handle numpy scalars
        if isinstance(obj, np.generic):
            return obj.item()
        # Handle pandas Series
        try:
            import pandas as pd
            if isinstance(obj, pd.Series):
                return {k: ParquetStorage._to_py(v) for k, v in obj.items()}
        except ImportError:
            pass
        # Handle dicts, lists, tuples
        if isinstance(obj, dict):
            return {k: ParquetStorage._to_py(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [ParquetStorage._to_py(x) for x in obj]
        # Fallback: try to convert to string if not serializable
        try:
            import json
            json.dumps(obj)
            return obj
        except Exception:
            return str(obj)

    @staticmethod
    def _session_to_row(session: TestSession) -> dict:
        d = session.to_dict()
        # Serialize nested fields as JSON
        d["test_results"] = json.dumps(d["test_results"])
        d["rerun_test_groups"] = json.dumps(d["rerun_test_groups"])
        d["session_tags"] = json.dumps(d["session_tags"])
        d["testing_system"] = json.dumps(d["testing_system"])
        return d

    @staticmethod
    def _row_to_session(row) -> TestSession:
        # Convert row (Series or dict) back to TestSession
        d = dict(row)
        d["test_results"] = json.loads(d["test_results"])
        d["rerun_test_groups"] = json.loads(d["rerun_test_groups"])
        d["session_tags"] = json.loads(d["session_tags"])
        d["testing_system"] = json.loads(d["testing_system"])
        return TestSession.from_dict(d)
