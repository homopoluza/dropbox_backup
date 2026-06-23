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

### Security
Database passwords are passed via environment variables during execution and do **not** appear in process listings.