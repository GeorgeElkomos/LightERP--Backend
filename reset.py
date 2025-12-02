import os
import glob
import time
import shutil
from pathlib import Path
from django.core.management import call_command
import django

# Path to your Django project root (same folder as manage.py)
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "db.sqlite3"
DUMP_FILE = BASE_DIR / "backup.json"

# Setup Django so we can call management commands directly
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "erp_project.settings"
)  # change if needed
django.setup()


def kill_django_servers():
    print("🛑 Killing running Django dev servers...")
    for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline")
            if not cmdline:
                continue
            cmdline_str = " ".join(cmdline)
            if "manage.py" in cmdline_str and "runserver" in cmdline_str:
                print(f"   ➜ Killing PID {proc.info['pid']} ({cmdline_str})")
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def backup_data():
    print("🔄 Backing up data to JSON...")
    with open(DUMP_FILE, "w", encoding="utf-8") as f:
        call_command(
            "dumpdata", "--natural-primary", "--natural-foreign", indent=2, stdout=f
        )


def delete_migrations():
    print("🗑️ Deleting migration files...")
    for app in os.listdir(BASE_DIR):
        app_path = BASE_DIR / app
        migrations_path = app_path / "migrations"
        if migrations_path.exists() and migrations_path.is_dir():
            for file in glob.glob(str(migrations_path / "[0-9]*.py")):
                os.remove(file)
            pycache = migrations_path / "__pycache__"
            if pycache.exists():
                for f in pycache.glob("*.pyc"):
                    f.unlink()


def delete_database():
    if DB_FILE.exists():
        print("🗑️ Deleting database file...")
        try:
            DB_FILE.unlink()
        except PermissionError:
            print("⚠️ Database file is locked, forcing delete...")
            tmp_name = str(DB_FILE) + ".old"
            try:
                shutil.move(str(DB_FILE), tmp_name)
                time.sleep(0.5)
                os.remove(tmp_name)
                print("✅ Forced delete succeeded.")
            except Exception as e:
                print(f"❌ Could not force delete DB: {e}")


def recreate_database():
    print("📦 Running fresh migrations...")
    call_command("makemigrations")
    call_command("migrate")


def restore_data():
    print("📥 Restoring data from JSON...")
    from django.db.models.signals import post_save, pre_save
    from django.core.signals import request_finished
    
    # Temporarily disable all signals during data restoration
    # This prevents post_save signals from firing before all related data is loaded
    saved_receivers = []
    for signal in [post_save, pre_save, request_finished]:
        saved_receivers.append((signal, signal.receivers))
        signal.receivers = []
    
    try:
        call_command("loaddata", DUMP_FILE)
    finally:
        # Restore signals
        for signal, receivers in saved_receivers:
            signal.receivers = receivers
        print("✅ Signals restored")


if __name__ == "__main__":
    backup_data()
    delete_migrations()
    kill_django_servers()
    
    # 👇 Add this
    from django import db
    db.connections.close_all()  # Close all DB connections so SQLite file can be deleted

    delete_database()
    recreate_database()
    restore_data()
    print("✅ Database reset complete and data restored!")
