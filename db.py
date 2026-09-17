from pymongo import MongoClient, errors
import os

uri = os.getenv("MONGO_URI")
db_name = os.getenv("DB_NAME", "Prison")

client = MongoClient(uri, tlsAllowInvalidCertificates=True)

db = client[db_name]
collection = db["user"]
exceptions_collection = db['exceptions']
guilds_collection = db["guilds"]
offensive_words_collection = db["offensive_words"]
settings_collection = db["settings"]

try:
  client.admin.command("ping")
  print(f"✅ You successfully connected to MongoDB! Database: {db_name}")
except Exception as e:
  print(e)
