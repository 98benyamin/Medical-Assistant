import json
import os
import shutil
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Any, Optional

class PersistentStorage:
    def __init__(self, filename="bot_data.json"):
        self.filename = filename
        self.data = self.load_data()

    def load_data(self) -> Dict[str, Any]:
        if os.path.exists(self.filename):
            with open(self.filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "users": {},
            "stats": {
                "total_users": 0,
                "daily_users": {},
                "total_queries": 0,
                "image_analyses": 0
            }
        }

    def save_data(self) -> None:
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    async def update_stats(self, stats) -> None:
        self.data["stats"] = stats.__dict__
        self.save_data()

class BackupManager:
    def __init__(self, backup_dir="backups"):
        self.backup_dir = backup_dir
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

    def create_backup(self, source_file: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(self.backup_dir, f"backup_{timestamp}.json")
        shutil.copy2(source_file, backup_file)
        return backup_file

class RateLimiter:
    def __init__(self, max_requests: int = 5, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.user_requests: Dict[int, List[datetime]] = {}

    async def check_limit(self, user_id: int) -> bool:
        current_time = datetime.now()
        if user_id not in self.user_requests:
            self.user_requests[user_id] = [current_time]
            return True

        # Remove old requests
        self.user_requests[user_id] = [
            time for time in self.user_requests[user_id]
            if current_time - time < timedelta(seconds=self.time_window)
        ]

        if len(self.user_requests[user_id]) >= self.max_requests:
            return False

        self.user_requests[user_id].append(current_time)
        return True

class ErrorReporter:
    def __init__(self, admin_id: str):
        self.admin_id = admin_id

    async def report_error(self, bot, error: Exception, context: str) -> None:
        error_message = f"""
⚠️ خطا در ربات پزشکی:
زمان: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
متن خطا: {str(error)}
مکان خطا: {context}
        """
        await bot.send_message(chat_id=self.admin_id, text=error_message)

class ReminderSystem:
    def __init__(self):
        self.reminders: Dict[int, List[Dict[str, Any]]] = {}

    async def add_reminder(self, user_id: int, message: str, time: datetime) -> None:
        if user_id not in self.reminders:
            self.reminders[user_id] = []
        self.reminders[user_id].append({
            "message": message,
            "time": time
        })

    async def check_reminders(self, bot) -> None:
        current_time = datetime.now()
        for user_id, user_reminders in self.reminders.items():
            for reminder in user_reminders[:]:
                if current_time >= reminder["time"]:
                    await bot.send_message(
                        chat_id=user_id,
                        text=f"⏰ یادآوری:\n{reminder['message']}"
                    )
                    user_reminders.remove(reminder)

class AutoReporter:
    def __init__(self, admin_id: str):
        self.admin_id = admin_id
        self.last_report_time: Optional[datetime] = None

    async def send_daily_report(self, bot, stats) -> None:
        if self.last_report_time is None or \
           datetime.now() - self.last_report_time > timedelta(days=1):
            report = await stats.get_dashboard_stats()
            await bot.send_message(
                chat_id=self.admin_id,
                text=f"📊 گزارش روزانه ربات:\n\n{report}"
            )
            self.last_report_time = datetime.now() 