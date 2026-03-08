import os
import hashlib
import threading
import time
import urllib.request
import sys
import shutil
import ctypes
import winreg
from io import BytesIO
import customtkinter as ctk
from PIL import Image
from tkinter import filedialog, messagebox

# Пытаемся импортировать внешнюю библиотеку
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

# --- КОНФИГУРАЦИЯ ---
APP_NAME = "ScenariumShield"
THREAT_DATABASE = {
    "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f": "EICAR Test Virus (Standard)",
    "44d88612fea8a8f36de82e1278abb02f": "EICAR Test Virus (MD5)",
    "fc0cb30e168661fc94d80a18413a96b9": "WannaCry Ransomware Component",
}

class RealTimeHandler(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    def __init__(self, app):
        self.app = app
    def on_created(self, event):
        if not event.is_directory: self.app.silent_check(event.src_path)
    def on_modified(self, event):
        if not event.is_directory: self.app.silent_check(event.src_path)

class ScenariumChecker(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Scenarium Shield Pro | Ultimate Security")
        self.geometry("1000x650")
        
        self.is_scanning = False
        self.realtime_active = False
        self.scanned_files_count = 0
        self.threats_found = 0
        self.observer = None
        
        self.optimize_for_gaming()
        self.setup_ui()
        self.check_autostart_status()

    def optimize_for_gaming(self):
        """Низкий приоритет CPU через системные вызовы Windows"""
        if sys.platform == 'win32':
            try:
                handle = ctypes.windll.kernel32.GetCurrentProcess()
                ctypes.windll.kernel32.SetPriorityClass(handle, 0x00004000)
            except:
                pass

    def check_autostart_status(self):
        """Проверка автозагрузки через winreg"""
        if sys.platform != 'win32': return
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, APP_NAME)
        except (FileNotFoundError, OSError):
            self.after(2000, self.prompt_installation)

    def prompt_installation(self):
        msg = "Активировать постоянную защиту Scenarium?\n\nПрограмма будет запускаться вместе с Windows в фоне."
        if messagebox.askyesno("Установка", msg):
            self.install_to_system()

    def install_to_system(self):
        if sys.platform != 'win32': return
        try:
            current_exe = sys.executable
            appdata_dir = os.path.join(os.environ["LOCALAPPDATA"], "Scenarium")
            if not os.path.exists(appdata_dir): os.makedirs(appdata_dir)
            
            dest_exe = os.path.join(appdata_dir, "sc_shield.exe")
            if os.path.normpath(current_exe) != os.path.normpath(dest_exe):
                shutil.copy2(current_exe, dest_exe)
            
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{dest_exe}" --minimized')
            self.log("✅ Успешно добавлено в автозагрузку.")
        except Exception as e:
            self.log(f"❌ Ошибка установки: {e}")

    def setup_ui(self):
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="...")
        self.logo_label.pack(pady=(20, 10))
        self.load_logo()
        
        self.app_name = ctk.CTkLabel(self.sidebar, text="SCENARIUM\nPRO SHIELD", font=ctk.CTkFont(size=22, weight="bold"), text_color="#FFC800")
        self.app_name.pack(pady=(0, 30))
        
        self.btn_quick = ctk.CTkButton(self.sidebar, text="Быстрый скан", command=self.quick_scan, height=45)
        self.btn_quick.pack(pady=10, padx=20, fill="x")

        self.btn_rt = ctk.CTkButton(self.sidebar, text="🛡️ Включить Щит", command=self.toggle_realtime, height=45, fg_color="#1a1a1a", border_width=2, border_color="#FFC800", text_color="#FFC800")
        self.btn_rt.pack(pady=10, padx=20, fill="x")

        self.btn_full = ctk.CTkButton(self.sidebar, text="Полный скан", command=self.full_scan, height=45, fg_color="#4d0000", hover_color="#800000")
        self.btn_full.pack(pady=10, padx=20, fill="x")

        self.shield_status = ctk.CTkLabel(self.sidebar, text="🛡️ ЩИТ ВЫКЛЮЧЕН", text_color="gray", font=ctk.CTkFont(size=11, weight="bold"))
        self.shield_status.pack(side="bottom", pady=20)

        self.main_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="#0d0d0d")
        self.main_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)
        
        self.status_title = ctk.CTkLabel(self.main_frame, text="СИСТЕМА ГОТОВА", font=ctk.CTkFont(size=26, weight="bold"), text_color="#2FA572")
        self.status_title.pack(pady=(20, 10))
        
        self.console = ctk.CTkTextbox(self.main_frame, corner_radius=12, font=ctk.CTkFont(family="Consolas", size=13))
        self.console.pack(fill="both", expand=True, pady=(0, 20), padx=20)
        self.console.configure(state="disabled")
        
        self.progress_bar = ctk.CTkProgressBar(self.main_frame, height=12, progress_color="#FFC800")
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 10))
        self.progress_bar.set(0)
        
        self.current_file_label = ctk.CTkLabel(self.main_frame, text="Ожидание...", text_color="#444")
        self.current_file_label.pack(anchor="w", padx=25)

    def log(self, text):
        self.console.configure(state="normal")
        self.console.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.console.see("end")
        self.console.configure(state="disabled")

    def silent_check(self, filepath):
        try:
            sha256_hash = hashlib.sha256()
            with open(filepath, "rb") as f:
                for byte_block in iter(lambda: f.read(65536), b""):
                    sha256_hash.update(byte_block)
            res = sha256_hash.hexdigest()
            if res in THREAT_DATABASE:
                self.after(0, lambda: self.report_threat(filepath, THREAT_DATABASE[res]))
        except: pass

    def report_threat(self, path, name):
        self.threats_found += 1
        self.log(f"⚠️ УГРОЗА: {name} | {path}")
        messagebox.showwarning("Угроза!", f"Обнаружен вирус: {name}\nФайл: {path}")

    def toggle_realtime(self):
        if not WATCHDOG_AVAILABLE:
            messagebox.showerror("Ошибка", "Библиотека watchdog не найдена.\nУстановите её командой: pip install watchdog")
            return

        if not self.realtime_active:
            self.realtime_active = True
            self.btn_rt.configure(text="🛡️ ЩИТ АКТИВЕН", fg_color="#FFC800", text_color="black")
            self.shield_status.configure(text="🛡️ ПОД ЗАЩИТОЙ", text_color="#2FA572")
            self.log("Мониторинг запущен.")
            
            self.observer = Observer()
            handler = RealTimeHandler(self)
            paths = [os.path.expanduser("~/Downloads"), os.path.expanduser("~/Desktop")]
            for p in paths:
                if os.path.exists(p): self.observer.schedule(handler, p, recursive=True)
            self.observer.start()
        else:
            self.realtime_active = False
            self.btn_rt.configure(text="🛡️ Включить Щит", fg_color="#1a1a1a", text_color="#FFC800")
            self.shield_status.configure(text="🛡️ ЩИТ ВЫКЛЮЧЕН", text_color="gray")
            if self.observer: self.observer.stop()
            self.log("Мониторинг остановлен.")

    def scan_engine(self, targets):
        self.is_scanning = True
        self.scanned_files_count = 0
        self.after(0, lambda: self.status_title.configure(text="СКАНИРОВАНИЕ...", text_color="#FFC800"))
        self.after(0, self.progress_bar.start)
        
        for folder in targets:
            for root, _, files in os.walk(folder):
                if not self.is_scanning: break
                for file in files:
                    fp = os.path.join(root, file)
                    self.scanned_files_count += 1
                    if self.scanned_files_count % 10 == 0:
                        self.after(0, lambda p=fp: self.current_file_label.configure(text=f"Файл: {p[-50:]}"))
                    self.silent_check(fp)
                    time.sleep(0.001)

        self.is_scanning = False
        self.after(0, self.progress_bar.stop)
        self.after(0, lambda: self.status_title.configure(text="ГОТОВО", text_color="#2FA572"))
        self.log(f"Завершено. Файлов: {self.scanned_files_count}. Угроз: {self.threats_found}")

    def quick_scan(self):
        t = [os.path.expanduser("~/Downloads"), os.path.expanduser("~/Desktop")]
        threading.Thread(target=self.scan_engine, args=(t,), daemon=True).start()

    def full_scan(self):
        t = ["C:\\"] if os.name == 'nt' else ["/"]
        threading.Thread(target=self.scan_engine, args=(t,), daemon=True).start()

    def load_logo(self):
        def fetch():
            try:
                url = "https://scenarium.netlify.app/Scenarium.png"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as res:
                    img = Image.open(BytesIO(res.read())).resize((90, 90), Image.LANCZOS)
                photo = ctk.CTkImage(light_image=img, dark_image=img, size=(90, 90))
                self.after(0, lambda: self.logo_label.configure(image=photo, text=""))
            except: self.after(0, lambda: self.logo_label.configure(text="SCENARIUM"))
        threading.Thread(target=fetch, daemon=True).start()

if __name__ == "__main__":
    app = ScenariumChecker()
    if "--minimized" in sys.argv:
        app.withdraw()
        if WATCHDOG_AVAILABLE: app.toggle_realtime() 
    app.mainloop()