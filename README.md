# Discord Jail Bot – by badr

## 💡 Features

- **Jail members manually or automatically**
  Jail members using commands or automatically detect and jail for specific actions.

- **Auto-release after a specific duration**
  Members will be automatically released from jail after a configured duration.

- **Offensive word detection and auto punishment**
  Detects bad words instantly and takes actions like jail or ban.

- **Interactive bad words manager**
  Use interactive buttons to add/remove/view offensive words list easily.

- **Full MongoDB persistence**
  Keeps all roles, settings, and jail states even after restarts.

- **Ban system**
  Ban users inside or even if they left the server.

  ## 🛠️ Commands Overview

- `/jail [user] [duration] [reason]`: Jail a user manually with optional duration and reason.
- `/unjail [user]`: Release a jailed user.
- `/badwords`: Manage offensive words list interactively.
- `/ban [user] [reason]`: Ban a user from the server.

## ⚙️ Setup Instructions

### 1️⃣ Install requirements
```bash
pip install -r requirements.txt
```
### 2️⃣ Create `.env` file:
```env
DISCORD_TOKEN=your_token
MONGODB_URI=your_mongodb_url
```
### 3️⃣ Run the bot:
```bash
python bot.py
```

## 💻 Requirements

- Python 3.8 or higher
- MongoDB database (local or cloud)
- Discord bot token

## 🆘 Support

For any issues or setup help, contact at discord: `1_i6`
