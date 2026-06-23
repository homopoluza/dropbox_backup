import subprocess
import os
import dropbox
from dropbox.exceptions import ApiError
import shutil
import time
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
import concurrent.futures
from functools import partial
from dotenv import load_dotenv

class DropboxUploader:
    def __init__(self, CHUNK_SIZE, path, days, app_key, app_secret, refresh_token):
        self.CHUNK_SIZE = CHUNK_SIZE
        self.path = path
        self.days = days
        self.app_key = app_key
        self.app_secret = app_secret
        self.refresh_token = refresh_token
        self.dbx = dropbox.Dropbox(
            oauth2_refresh_token=refresh_token,
            app_key=app_key,
            app_secret=app_secret
        )

    def check_folder_exists(self):
        try:
            self.dbx.files_get_metadata(self.path)
            return True
        except ApiError as err:
            if isinstance(err.error, dropbox.files.GetMetadataError) and err.error.is_path() and err.error.get_path().is_not_found():
                return False
            else:
                raise

    def create_folder(self):
        self.dbx.files_create_folder_v2(self.path)

    def upload_file(self, file_name, file_size, max_retries=3, bitrix=False):
        retries = 0
        relative_path = os.path.basename(file_name)
        while retries < max_retries:
            try:
                if not self.check_folder_exists and not bitrix:
                    self.create_folder()
            
                with open(file_name, 'rb') as f:
                    if file_size <= self.CHUNK_SIZE:
                        self.dbx.files_upload(f.read(), f"{self.path}/{relative_path}")
                    else:
                        upload_session_start_result = self.dbx.files_upload_session_start(f.read(self.CHUNK_SIZE))
                        cursor = dropbox.files.UploadSessionCursor(session_id=upload_session_start_result.session_id, offset=f.tell())
                        commit = dropbox.files.CommitInfo(path=f"{self.path}/{relative_path}")

                        while f.tell() < file_size:
                            if ((file_size - f.tell()) <= self.CHUNK_SIZE):
                                self.dbx.files_upload_session_finish(f.read(self.CHUNK_SIZE), cursor, commit)
                            else:
                                self.dbx.files_upload_session_append_v2(f.read(self.CHUNK_SIZE), cursor)
                                cursor.offset = f.tell()
                return True
            except Exception as api_err:
                retries += 1
                if retries == max_retries:
                    self.send_email(site, api_err)
                    return False

    def upload_folder(self, folder_path, bitrix=True, max_workers=10):
        try:
            if bitrix and not self.check_folder_exists():
                self.create_folder()
            
            file_list = []
            for root, dirs, files in os.walk(folder_path):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    file_size = os.path.getsize(file_path)
                    file_list.append((file_path, file_size))
            
            upload_func = partial(self.upload_file, bitrix=bitrix)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                executor.map(lambda x: upload_func(*x), file_list)
            
            return True
        except Exception as err:
            self.send_email(site, err)
            return False

    def send_email(self, site, api_err):
        # Email settings
        smtp_server = os.getenv('SMTP_SERVER')
        smtp_port = int(os.getenv('SMTP_PORT'))
        email_login = os.getenv('EMAIL_LOGIN')
        email_password = os.getenv('EMAIL_PASS')
        email_to = os.getenv('EMAIL_TO')

        msg = MIMEText(f"The site {site} returned status code or error {api_err}.")
        msg['Subject'] = f"{site} - backup {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        msg['From'] = email_login
        msg['To'] = email_to

        s = smtplib.SMTP(smtp_server, smtp_port)
        s.starttls()
        s.login(email_login, email_password)
        s.send_message(msg)
        s.quit()

    def delete_old_files(self, max_workers=7):
        try:
            files = []
            result = self.dbx.files_list_folder(self.path)
            files.extend(result.entries)  

            # Handle pagination 
            while result.has_more: 
                result = self.dbx.files_list_folder_continue(result.cursor) 
                files.extend(result.entries)            

            # now = datetime.now(timezone.utc)
            now = datetime.now()

            def delete_if_old(file):
                try:
                    # Dropbox uses UTC time for file metadata
                    file_time = file.client_modified

                    # Check if the file is older than `days` days
                    if now - file_time > timedelta(days=self.days):
                        self.dbx.files_delete_v2(file.path_lower)
                        time.sleep(1) # Add a delay to avoid rate limiting
                except Exception as err:
                    self.send_email(site, err)

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                executor.map(delete_if_old, files)

        except Exception as err:
            self.send_email(site, err)

# Load environment variables from .env file
load_dotenv()

if __name__ == "__main__":
    # Script settings
    root_dir = os.getenv('ROOT_DIR')
    site = os.getenv('DROPBOX_FOLDER')
    days = int(os.getenv('DAYS')) # delete Dropbox files older than days
    bitrix_framework = os.getenv('BITRIX') =='True' # for bitrix CMS

    # Get DB settings
    db_type = os.getenv('DB_TYPE')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    database = os.getenv('DB_DATABASE')

    
    #Dropbox app key, secret, and refresh token
    CHUNK_SIZE = 8 * 1024 * 1024 # 8MB
    APP_KEY = os.getenv('APP_KEY')
    APP_SECRET = os.getenv('APP_SECRET')
    REFRESH_TOKEN = os.getenv('REFRESH_TOKEN')

    dropbox_path = "/" + site
    uploader = DropboxUploader(CHUNK_SIZE, dropbox_path, days, APP_KEY, APP_SECRET, REFRESH_TOKEN)
    archive_uploaded = False
    database_uploaded = False
    folder_uploaded = False

    if bitrix_framework:
        folder_uploaded = uploader.upload_folder(root_dir)
    else:
        archive_name = site + '_' + datetime.now().strftime("%Y%m%d_%H%M%S")
        database_dump_name = database + '_' + datetime.now().strftime("%Y%m%d_%H%M%S") + '.sql'
        archive_path = shutil.make_archive(archive_name, 'tar', root_dir)
        archive_name = os.path.basename(archive_path)
        if db_type == 'mysql':
            env = os.environ.copy()
            env['MYSQL_PWD'] = db_password
            command = f"mysqldump -h {db_host} -P {db_port} -u {db_user} {database}"
            with open(database_dump_name, 'wb') as f:
                subprocess.run(command, shell=True, stdout=f, env=env)
        elif db_type == 'postgres':
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password
            command = f"pg_dump -h {db_host} -p {db_port} -U {db_user} {database}"
            with open(database_dump_name, 'w') as f:
                subprocess.run(command, shell=True, stdout=f, env=env)
        else:
            raise ValueError(f"Unknown DB_TYPE: {db_type}")
        archive_size = os.path.getsize(f"./{archive_name}")
        database_dump_size = os.path.getsize(f"./{database_dump_name}")
        archive_uploaded = uploader.upload_file(archive_name, archive_size)
        database_uploaded = uploader.upload_file(database_dump_name, database_dump_size)
        os.remove(archive_name)
        os.remove(database_dump_name)

    if (archive_uploaded and database_uploaded) or folder_uploaded:
        uploader.delete_old_files()
