# Dropbox Backup

## dropbox_backup.py

The `dropbox_backup.py` script automates database backups and `.tar` archives, storing them in Dropbox. Supports **MySQL/MariaDB** and **PostgreSQL**.

### Installation
```bash
pip3 install python-dotenv
pip3 install dropbox
```

### Configuration

Copy `.env.example` to `.env` and populate it with your settings according to the comments in the file.

**PostgreSQL requirement:** PostgreSQL must use **md5 password authentication** (not peer auth). Verify your `pg_hba.conf`:
```
local   database_name   db_user   md5
```

For Bitrix backups, set `BITRIX=True`.

### Optional: uv installation
An extremely fast Python package and project manager, written in Rust
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Cron usage
Add a crontab entry to run the script daily at 04:00 and log output. Replace `dropbox_backup.py` with `main.py` as requested:
```cron
0 4 * * * echo "$(date) Starting backup..." >> /root/dropbox_backup/backup.log && cd /root/dropbox_backup && /usr/bin/python3 /root/dropbox_backup/main.py >> /root/dropbox_backup/backup.log 2>&1 && echo "$(date) Backup finished." >> /root/dropbox_backup/backup.log
```
### Cron usage with uv
```cron
0 4 * * * echo "$(date) Starting backup..." >> /root/dropbox_backup/backup.log && cd /root/dropbox_backup && /root/.local/bin/uv run main.py >> /root/dropbox_backup/backup.log 2>&1 && echo "$(date) Backup finished." >> /root/dropbox_backup/backup.log
```

### Security
Database passwords are passed via environment variables during execution and do **not** appear in process listings.

**PostgreSQL grants (if backup user differs from schema owner):** If your backup user is different from the superuser and doesn't own the tables, grant SELECT permissions as superuser (`postgres`):
```sql
GRANT USAGE ON SCHEMA public TO user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO user;
```