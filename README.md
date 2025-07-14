![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-Private-important)

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

### 🔒 Jail Commands (File: `jail.py`)

- `-jail [user] [duration] [reason]`: Jail a user manually with optional duration and reason.
- `-unjail [user]`: Release a jailed user.
- `-jailed`: List all currently jailed members with their release times.
- `-how`: Check your remaining jail time and release information.

### 🏷️ Setup Commands (File: `setup.py`)

- `-set [role]`: Set the prisoner role for the server. Members with this role will have their channel access restricted automatically.
- `-mod [channel]`: Set the moderation log channel. If no channel is provided, uses the current channel.

### ⚔️ Ban Commands (File: `ban.py`)

- `-ban [user] [reason]`: Ban a user from the server.
- `-unban [user]`: Unban a user from the server using their ID.
- `-set_bc [channel]`: Set the ban release notification channel. If no channel is provided, it uses the current channel.

### 🚫 Offensive Words Commands (File: `badwords.py`)

- `-abad word1, word2, ...`: Add one or more words to the offensive words list.
- `-rbad word1, word2, ...`: Remove one or more words from the offensive words list.
- `-lbad`: List all offensive words currently in the database.
- `-badwords`: Show an interactive menu to manage offensive words.

### 📌 Exception Channels Commands (File: `exceptions.py`)

- `-add [channel]`: Add a channel to the exceptions list, allowing prisoners to view and access it. If no channel is provided, uses the current channel.
- `-rem [channel]`: Remove a channel from the exceptions list and hide it from prisoners. If no channel is provided, uses the current channel.
- `-list` or `-show_exp`: Show all channels currently in the exceptions list.

### ⚙️ Automatic System (File: `core.py`)

- Automatically detects spam and offensive words, and jails or times out users without manual commands.

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

Need help or have issues? Contact me on Discord: `1_i6`
