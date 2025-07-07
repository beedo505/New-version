# Discord Jail Bot – by badr

## 💡 Features
- Jail members manually or automatically (auto jail for offensive words or spam)
- Auto-release after a specific duration
- Offensive word detection and automatic punishment
- Full MongoDB data persistence for roles and jail info
- Interactive bad words manager (with buttons)
- Ban system for users inside or outside the server

## ⚙️ Setup Instructions

### 1️⃣ Install requirements
```bash
pip install -r requirements.txt
```
2. Create `.env` file:
```env
DISCORD_TOKEN=your_token
MONGODB_URI=your_mongodb_url
```
3. Run the bot:
```bash
python bot.py
```
