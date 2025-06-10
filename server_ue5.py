import os
import json
import time
import threading
from datetime import datetime

# Вместо asyncio и websockets.asyncio используем sync версию
import websockets.sync.server as ws_sync
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

CONFIG_FILE = r"C:\Users\User\Documents\Unreal Projects\RLS\Intermediate\PythonStub\reqwest.json"
connected_clients = []
clients_lock = threading.Lock()

def create_header():
    """Создаёт заголовок длиной 12 байт"""
    header = bytearray(12)
    header[0] = 0x00  # streamType
    header[1] = 0x01  # frameType
    header[2] = 0x00  # serializationFormat (JSON)
    header[3] = 0x00  # gzipCompression (False)

    now_ms = int(datetime.now().timestamp() * 1000)
    header[4:12] = now_ms.to_bytes(8, byteorder='big')
    return header


def load_config():
    """Читает JSON и оборачивает его в заголовок"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        return create_header() + json_data
    except Exception as e:
        print("❌ Ошибка чтения файла:", e)
        return None


def handler(websocket):
    print("🔌 Новое подключение")
    with clients_lock:
        connected_clients.append(websocket)

    try:
        initial_data = load_config()
        if initial_data:
            websocket.send(initial_data)
            print("📨 Начальные данные отправлены новому клиенту")

        for _ in websocket:
            pass  # игнорируем входящие сообщения

    except Exception as e:
        print("⚠️ Клиент отключён:", e)
    finally:
        with clients_lock:
            if websocket in connected_clients:
                connected_clients.remove(websocket)


class ConfigFileHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_modified = os.path.getmtime(CONFIG_FILE)

    def on_modified(self, event):
        if event.src_path.endswith(os.path.basename(CONFIG_FILE)):
            current_time = os.path.getmtime(CONFIG_FILE)
            if current_time != self.last_modified:
                print("🔄 Файл изменился, рассылаем обновления")
                update_data = load_config()
                if update_data:
                    notify_clients(update_data)
                self.last_modified = current_time


def notify_clients(data):
    with clients_lock:
        disconnected = []
        for client in connected_clients:
            try:
                client.send(data)
            except Exception:
                disconnected.append(client)

        for client in disconnected:
            connected_clients.remove(client)
        print(f"📨 Рассылка обновления {len(data)} байт")


def run_server():
    server = ws_sync.serve(handler, "127.0.0.1", 8765)
    print("📡 Сервер запущен на ws://127.0.0.1:8765")

    # Отправляем начальную конфигурацию
    initial_data = load_config()
    if initial_data:
        notify_clients(initial_data)

    # Наблюдение за файлом
    observer = Observer()
    event_handler = ConfigFileHandler()
    observer.schedule(event_handler, path=os.path.dirname(CONFIG_FILE) or '.', recursive=False)
    observer.start()
    print("👀 Слежу за изменениями reqwest.json...")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


# === Запуск в отдельном потоке ===
thread = threading.Thread(target=run_server, daemon=True)
thread.start()
print("🧵 Сервер запущен в отдельном потоке")