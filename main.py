import os
import sqlite3
import urllib.request
import datetime
import requests
from zipfile import ZipFile, ZIP_DEFLATED
import time
import socket

# Set base directory (relative path)
base_directory = 'pathofexile_patches'

# Specify the time interval (in seconds) for running the code
time_interval = 60  # Change this value as needed

# Get the absolute path of the current working directory
cwd = os.getcwd()
base_path = os.path.join(cwd, base_directory)

# Create base directory if it doesn't exist
os.makedirs(base_path, exist_ok=True)

# Set storage and download directories (relative paths)
storage_directory = os.path.join(base_directory, 'stored')
download_directory = os.path.join(base_directory, 'download')

# Get the absolute paths of storage and download directories
storage_path = os.path.join(cwd, storage_directory)
download_path = os.path.join(cwd, download_directory)

# Create storage and download directories if they don't exist
os.makedirs(storage_path, exist_ok=True)
os.makedirs(download_path, exist_ok=True)

# Create connection and cursor to SQLite database
conn = sqlite3.connect(os.path.join(base_path, 'patchdatabase.db'))
c = conn.cursor()

# Create table if not exists
c.execute('''CREATE TABLE IF NOT EXISTS patch
             (version text, exe_name text, date_time text)''')

# Print startup message
print(f"{datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')} - Patch downloader started.")

# Configuration variables
fetch_directly = True  # Set to True for fetching directly from GGG servers, False for fetching from GitHub
log_only_new_versions = True  # Set to True to log only when a new version is downloaded

def fetch_patch():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(("patch.pathofexile.com", 12995))
            s.sendall(bytes([1, 6]))
            data = s.recv(1024)
            patch = data[35:35 + data[34] * 2].decode('utf-16le').split("/")[-2]
            return patch
    except Exception as e:
        print(f"An error occurred: {e}")

while True:
    try:
        # Get latest version number
        if fetch_directly:
            version = fetch_patch()
        else:
            response = urllib.request.urlopen('https://raw.githubusercontent.com/poe-tool-dev/latest-patch-version/main/latest.txt')
            version = response.read().decode()

        # Check if version already exists in the database
        c.execute("SELECT * FROM patch WHERE version=?", (version,))
        result = c.fetchone()

        if result:
            if not log_only_new_versions:
                print(f"{datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')} - Version {version} already exists in the database.")
        else:
            # Construct the exe URL using the version
            exe_url = f"https://patch.poecdn.com/{version}/PathOfExile.exe"
            exe_name = f"PathOfExile_{version}.exe"
            zip_name = f"{version}.zip"

            # Check if ZIP file already exists
            if os.path.exists(os.path.join(download_path, zip_name)):
                print(f"{datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')} - ZIP file already exists.")
            else:
                # Download the exe
                response = requests.get(exe_url)
                exe_path = os.path.join(download_path, exe_name)
                with open(exe_path, 'wb') as f:
                    f.write(response.content)

                # Insert data into SQLite
                c.execute("INSERT INTO patch VALUES (?, ?, ?)",
                          (version, exe_name, datetime.datetime.now()))

                # Save (commit) the changes
                conn.commit()

                # Compress the downloaded exe into a ZIP file
                zip_path = os.path.join(download_path, zip_name)
                with ZipFile(zip_path, 'w', ZIP_DEFLATED, compresslevel=9) as zipf:
                    zipf.write(exe_path, arcname=os.path.basename(exe_path))

                # Check the file size
                if os.path.getsize(zip_path) > 50 * 1024 * 1024:  # 50 MB
                    print(f"{datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')} - Compressed file {zip_name} is larger than 50MB.")

                # Move the ZIP file to the storage directory
                storage_zip_path = os.path.join(storage_path, zip_name)
                os.replace(zip_path, storage_zip_path)

                print(f"{datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')} - New version {version} downloaded and stored.")

        # Clear the download folder
        for file_name in os.listdir(download_path):
            file_path = os.path.join(download_path, file_name)
            if os.path.isfile(file_path):
                os.remove(file_path)

    except urllib.error.URLError as e:
        print(f"{datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')} - Error: Failed to connect to the URL.")

    except requests.exceptions.RequestException as e:
        print(f"{datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')} - Error: Failed to download the file.")

    except Exception as e:
        print(f"{datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')} - Error: {str(e)}")

    # Calculate the next scheduled check time
    next_check_time = datetime.datetime.now() + datetime.timedelta(seconds=time_interval)

    # Print the next scheduled check time
    if not log_only_new_versions:
        print(f"{datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')} - Next check scheduled at: {next_check_time.strftime('%Y-%m-%d %I:%M:%S %p')}")

    # Wait for the specified time interval before the next iteration
    time.sleep(time_interval)
