from pymongo import MongoClient, errors
import os

uri = os.getenv("MONGO_URI")
client = MongoClient(uri, tlsAllowInvalidCertificates=True)

db = client["Prison"]
collection = db["user"]
exceptions_collection = db['exceptions']
guilds_collection = db["guilds"]
offensive_words_collection = db["offensive_words"]
settings_collection = db["settings"]

try:
  client.admin.command('ping')
  print("You successfully connected to MongoDB!")
except Exception as e:
  print(e)
