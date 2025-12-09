import pypdf
from typing import List

class PDFProcessor:
    @staticmethod
    def extract_text(file_path: str) -> str:
        text = ""
        with open(file_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
        # Simple word-based chunking
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
        return chunks

    def process(self, file_path: str) -> List[str]:
        text = self.extract_text(file_path)
        return self.chunk_text(text)
