import chromadb

# 1. Khởi tạo client (chạy local, không cần server ngoài)
client = chromadb.Client()

# 2. Tạo collection để lưu dữ liệu
collection = client.create_collection(name="study_info")

# 3. Thêm dữ liệu ví dụ
collection.add(
    documents=[
        "Lịch học môn Toán: thứ 2 và thứ 4.",
        "Lịch học môn Lập trình C#: thứ 3 và thứ 5.",
        "Giảng viên phụ trách môn AI là thầy Nguyễn Văn A."
    ],
    ids=["1", "2", "3"]
)

# 4. Thử truy vấn
query = "Học môn C# vào ngày nào?"
results = collection.query(
    query_texts=[query],
    n_results=4
)

print("Câu hỏi:", query)
print("Kết quả truy vấn:", results["documents"][0])
