import os

from pymongo import MongoClient, errors


# =========================
# Environment Variables
# =========================

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME", "Prison")


if not MONGO_URI:
    raise RuntimeError(
        "❌ MONGO_URI is missing. "
        "Please add it to your .env file or hosting environment variables."
    )


# =========================
# MongoDB Connection
# =========================

try:
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=10000
    )

    client.admin.command("ping")

    print(
        f"✅ You successfully connected to MongoDB! "
        f"Database: {DB_NAME}"
    )

except errors.PyMongoError as e:
    raise RuntimeError(
        f"❌ Failed to connect to MongoDB: {e}"
    ) from e


# =========================
# Database
# =========================

db = client[DB_NAME]


# =========================
# Collections
# =========================

collection = db["user"]
exceptions_collection = db["exceptions"]
guilds_collection = db["guilds"]
offensive_words_collection = db["offensive_words"]
settings_collection = db["settings"]
