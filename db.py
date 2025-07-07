from pymongo import MongoClient, errors
import os

uri = "mongodb+srv://user_b:v4DXWaubyWZmnk3T@cluster0.zriaf.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

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
