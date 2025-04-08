# -*- coding: utf-8 -*-
import redis
import json
import time
import os
from datetime import datetime
import threading
import schedule
import subprocess

# Redis connection config
REDIS_HOST = '1.95.154.244'
REDIS_PORT = 6379
REDIS_PASSWORD = '123'
CHANNEL_NAME = 'jailbird:sync'
DELETE_CHANNEL_NAME = 'jailbird:delete'

# Local data path - using absolute path
LOCAL_DATA_PATH = os.path.abspath('account_data_path')

# Cleanup config
CLEANUP_INTERVAL = 24  # Cleanup interval (hours)
DATA_RETENTION_DAYS = 7  # Data retention days

def connect_redis():
    """Connect to Redis server"""
    try:
        r = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        r.ping()
        print("[OK] Redis connected successfully!")
        return r
    except Exception as e:
        print("[ERROR] Redis connection failed: {}".format(e))
        return None

def normalize_path(path):
    """Normalize path for Linux system"""
    return os.path.normpath(path).replace('\\', '/')

def get_redis_keys(redis_client):
    """Get all relevant keys from Redis"""
    keys = {}
    for key in redis_client.keys("jailbird:account:*"):
        if not key.endswith(":metadata") and not key.endswith(":version"):
            keys[key] = {
                'data': json.loads(redis_client.get(key)),
                'metadata': redis_client.hgetall("{}:metadata".format(key))
            }
    return keys

def get_local_files():
    """Get all local JSON files"""
    files = {}
    for root, _, filenames in os.walk(LOCAL_DATA_PATH):
        for filename in filenames:
            if filename.endswith('.json'):
                file_path = os.path.join(root, filename)
                relative_path = os.path.relpath(file_path, LOCAL_DATA_PATH)
                key = "jailbird:account:{}".format(normalize_path(relative_path))
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        files[key] = json.load(f)
                except Exception as e:
                    print("[ERROR] Failed to read local file {}: {}".format(file_path, e))
    return files

def check_data_consistency():
    """Check consistency between Redis and local files"""
    redis_client = connect_redis()
    if not redis_client:
        return

    print("Starting data consistency check...")
    
    # Get data from Redis and local files
    redis_data = get_redis_keys(redis_client)
    local_data = get_local_files()
    
    # Check for missing or outdated files
    for key, redis_value in redis_data.items():
        if key not in local_data:
            print("[WARN] Missing local file for key: {}".format(key))
            save_to_local(key, redis_value['data'])
        else:
            # Compare versions if available
            try:
                redis_version = int(redis_value['metadata'].get('version', 0))
                local_version = 0  # Default version if not available
                
                # Try to get local version from Redis metadata
                local_metadata_key = "{}:metadata".format(key)
                if redis_client.exists(local_metadata_key):
                    local_metadata = redis_client.hgetall(local_metadata_key)
                    local_version = int(local_metadata.get('version', 0))
                
                if redis_version > local_version:
                    print("[WARN] Local file outdated for key: {} (Redis: {}, Local: {})".format(
                        key, redis_version, local_version))
                    save_to_local(key, redis_value['data'])
            except (ValueError, TypeError) as e:
                print("[ERROR] Version comparison failed for key {}: {}".format(key, e))
                # If version comparison fails, update the file to be safe
                save_to_local(key, redis_value['data'])
    
    # Check for extra local files and delete them
    for key in local_data:
        if key not in redis_data:
            print("[WARN] Extra local file found and will be deleted: {}".format(key))
            delete_local_file(key)
    
    print("Data consistency check completed!")

def save_to_local(key, value):
    """Save data to local file"""
    try:
        # Extract relative path from key and normalize it
        relative_path = key.replace('jailbird:account:', '')
        relative_path = normalize_path(relative_path)
        file_path = os.path.join(LOCAL_DATA_PATH, relative_path)
        file_path = normalize_path(file_path)
        
        # Ensure directory exists
        dir_path = os.path.dirname(file_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, mode=0o755, exist_ok=True)
            print("[OK] Created directory: {}".format(dir_path))
        
        # Save data to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=4)
        
        print("[OK] Saved to local: {}".format(file_path))
    except Exception as e:
        print("[ERROR] Failed to save to local: {}".format(e))

def delete_local_file(key):
    """Delete local file and its parent directory if empty"""
    try:
        # Extract relative path from key and normalize it
        relative_path = key.replace('jailbird:account:', '')
        relative_path = normalize_path(relative_path)
        file_path = os.path.join(LOCAL_DATA_PATH, relative_path)
        file_path = normalize_path(file_path)
        
        if os.path.exists(file_path):
            try:
                # Delete the file
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print("[OK] Deleted local file: {}".format(file_path))
                elif os.path.isdir(file_path):
                    # For directories, only delete if empty
                    if not os.listdir(file_path):
                        os.rmdir(file_path)
                        print("[OK] Deleted empty directory: {}".format(file_path))
                    else:
                        print("[WARN] Directory not empty, skipping: {}".format(file_path))
                        return
                
                # Delete parent directories if they are empty
                current_dir = os.path.dirname(file_path)
                while current_dir != LOCAL_DATA_PATH:
                    if os.path.exists(current_dir) and os.path.isdir(current_dir):
                        if not os.listdir(current_dir):
                            os.rmdir(current_dir)
                            print("[OK] Deleted empty directory: {}".format(current_dir))
                            current_dir = os.path.dirname(current_dir)
                        else:
                            break
                    else:
                        break
            except PermissionError as e:
                print("[ERROR] Permission denied: {} - {}".format(file_path, e))
            except Exception as e:
                print("[ERROR] Failed to delete: {} - {}".format(file_path, e))
    except Exception as e:
        print("[ERROR] Failed to delete local file: {}".format(e))

def handle_message(message):
    """Handle received message"""
    try:
        data = json.loads(message['data'])
        key = data.get('key')
        value = data.get('value')
        
        if key and value:
            redis_client = connect_redis()
            if redis_client:
                # Store data to Redis
                redis_client.set(key, json.dumps(value))
                
                # Record sync time and version
                sync_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                metadata = {
                    "last_sync": sync_time,
                    "version": redis_client.incr("{}:version".format(key), 1)
                }
                redis_client.hmset("{}:metadata".format(key), metadata)
                
                # Save to local file
                save_to_local(key, value)
                
                print("[OK] Synced data: {} at {} (version: {})".format(
                    key, sync_time, metadata['version']))
    except Exception as e:
        print("[ERROR] Failed to process message: {}".format(e))

def handle_delete_message(message):
    """Handle delete message"""
    try:
        data = json.loads(message['data'])
        key = data.get('key')
        
        if key:
            redis_client = connect_redis()
            if redis_client:
                # Delete data from Redis
                redis_client.delete(key)
                redis_client.delete("{}:metadata".format(key))
                redis_client.delete("{}:version".format(key))
                
                # Delete local file
                delete_local_file(key)
                
                print("[OK] Deleted data: {}".format(key))
    except Exception as e:
        print("[ERROR] Failed to process delete message: {}".format(e))

def cleanup_old_data():
    """Cleanup expired data"""
    try:
        redis_client = connect_redis()
        if not redis_client:
            return

        print("Starting cleanup of old data...")
        current_time = datetime.now()
        keys = redis_client.keys("jailbird:account:*")
        
        for key in keys:
            if not key.endswith(":metadata") and not key.endswith(":version"):
                metadata_key = "{}:metadata".format(key)
                if redis_client.exists(metadata_key):
                    last_sync = redis_client.hget(metadata_key, "last_sync")
                    if last_sync:
                        last_sync_time = datetime.strptime(last_sync, "%Y-%m-%d %H:%M:%S")
                        if (current_time - last_sync_time).days > DATA_RETENTION_DAYS:
                            # Delete data from Redis
                            redis_client.delete(key)
                            redis_client.delete(metadata_key)
                            redis_client.delete("{}:version".format(key))
                            
                            # Delete local file
                            delete_local_file(key)
        
        print("Data cleanup completed!")
    except Exception as e:
        print("[ERROR] Failed to cleanup data: {}".format(e))

def start_cleanup_scheduler():
    """Start cleanup scheduler"""
    schedule.every(CLEANUP_INTERVAL).hours.do(cleanup_old_data)
    while True:
        schedule.run_pending()
        time.sleep(60)

def start_subscriber():
    """Start subscriber service"""
    redis_client = connect_redis()
    if not redis_client:
        return

    pubsub = redis_client.pubsub()
    # Subscribe to both sync and delete channels
    pubsub.subscribe(CHANNEL_NAME, DELETE_CHANNEL_NAME)
    print("Listening to channels: {}, {}".format(CHANNEL_NAME, DELETE_CHANNEL_NAME))

    try:
        for message in pubsub.listen():
            if message['type'] == 'message':
                if message['channel'] == CHANNEL_NAME:
                    handle_message(message)
                elif message['channel'] == DELETE_CHANNEL_NAME:
                    handle_delete_message(message)
    except KeyboardInterrupt:
        print("\nStopping listener...")
    finally:
        pubsub.unsubscribe()
        redis_client.close()

def main():
    print("Starting Redis subscriber service...")
    
    # Ensure local data directory exists with proper permissions
    if not os.path.exists(LOCAL_DATA_PATH):
        os.makedirs(LOCAL_DATA_PATH, mode=0o755, exist_ok=True)
        print("[OK] Created data directory: {}".format(LOCAL_DATA_PATH))
    
    # Check data consistency before starting
    check_data_consistency()
    
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=start_cleanup_scheduler, daemon=True)
    cleanup_thread.start()
    print("Started cleanup task, running every {} hours".format(CLEANUP_INTERVAL))
    
    # Start subscriber service
    start_subscriber()

if __name__ == "__main__":
    main() 