import asyncio
from qdrant_client import QdrantClient
from qdrant_client.http import models

async def reset_qdrant_collection():
    print("Connecting to Qdrant...")
    # Adjust host/port if needed, assuming default 6333
    client = QdrantClient(url="http://localhost:6333")
    
    collection_name = "unimind_docs"
    
    print(f"Checking collection '{collection_name}'...")
    try:
        client.delete_collection(collection_name=collection_name)
        print(f"Deleted existing collection '{collection_name}'.")
    except Exception as e:
        print(f"Deletion warning (maybe didn't exist): {e}")
    
    print(f"Recreating collection '{collection_name}' with size 768...")
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=768,  # Matches nomic-embed-text
            distance=models.Distance.COSINE
        )
    )
    print("✅ Collection 'unimind_docs' reset successfully to 768 dimensions.")

if __name__ == "__main__":
    asyncio.run(reset_qdrant_collection())
