try:
    from app.services.pdf_processor import PDFProcessor
    print("Import successful")
except ImportError as e:
    print(f"Import failed: {e}")
    # Try debug imports
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        print("langchain.text_splitter found")
    except ImportError:
        print("langchain.text_splitter NOT found")
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            print("langchain_text_splitters found")
        except ImportError:
            print("langchain_text_splitters NOT found")
