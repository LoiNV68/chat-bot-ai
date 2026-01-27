import pdfplumber
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter

class PDFProcessor:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )

    def process(self, file_path: str) -> List[str]:
        """
        Process PDF file to extract text and tables with smart chunking.
        Returns a list of string chunks.
        """
        chunks = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    # 1. Extract and format tables
                    tables = page.extract_tables()
                    for table in tables:
                        # Convert table to Markdown format for better LLM understanding
                        if table:
                            table_md = self._table_to_markdown(table)
                            chunks.append(f"Table from page {page.page_number}:\n{table_md}")

                    # 2. Extract text (ignoring tables would be ideal but complex, 
                    # for now we extract text and chunk it)
                    text = page.extract_text()
                    if text:
                        # Split text into chunks
                        page_text_chunks = self.text_splitter.split_text(text)
                        chunks.extend(page_text_chunks)
                        
        except Exception as e:
            print(f"Error processing PDF {file_path}: {str(e)}")
            # Fallback or re-raise depending on requirements
            raise e

        return chunks

    def _table_to_markdown(self, table: List[List[str]]) -> str:
        """Helper to convert list of lists to Markdown table string"""
        if not table:
            return ""
        
        # Clean None values
        table = [[str(cell) if cell is not None else "" for cell in row] for row in table]
        
        # Determine number of columns
        if not table:
            return ""
        
        headers = table[0]
        # Create separator
        separator = ["---"] * len(headers)
        
        # Build Markdown table
        md_lines = []
        md_lines.append("| " + " | ".join(headers) + " |")
        md_lines.append("| " + " | ".join(separator) + " |")
        
        for row in table[1:]:
             md_lines.append("| " + " | ".join(row) + " |")
             
        return "\n".join(md_lines)
