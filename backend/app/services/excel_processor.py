import pandas as pd
from typing import List

class ExcelProcessor:
    @staticmethod
    def process(file_path: str) -> List[str]:
        # Read Excel file, handle merged cells by default via pandas
        df = pd.read_excel(file_path)
        
        # Convert each row to a string representation
        chunks = []
        for _, row in df.iterrows():
            # Filter out NaNs and convert to "Column: Value" format
            row_str = ", ".join([f"{col}: {val}" for col, val in row.items() if pd.notna(val)])
            if row_str.strip():
                chunks.append(row_str)
        return chunks
