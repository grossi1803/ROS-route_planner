from pymongo import MongoClient

client = MongoClient("mongodb://10.10.10.6:27017", serverSelectionTimeoutMS=5000)
try:
    client.admin.command("ping")
    print("MongoDB connection successful!")
except Exception as e:
    print("MongoDB connection failed:", e)
