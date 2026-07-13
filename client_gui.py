import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import tkinter.ttk as ttk
from pathlib import Path
import os
import threading
import sys
import platform

# Import fungsi-fungsi jaringan dari client.py yang sudah di-refactor
from client import sync_folder, fetch_versions, restore_file

ctk.set_appearance_mode("System")  # Otomatis mengikuti tema OS (Dark/Light)
ctk.set_default_color_theme("blue")  # Tema warna biru

class TextRedirector:
    """Class kecil untuk membelokkan output terminal (print) ke dalam Textbox GUI."""
    def __init__(self, widget):
        self.widget = widget

    def write(self, str_data):
        self.widget.insert(tk.END, str_data)
        self.widget.see(tk.END) # Scroll ke bawah otomatis

    def flush(self):
        pass

class ClientGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("File Sync TCP - Modern Client")
        self.geometry("850x600")
        
        # Grid layout (1 Baris x 2 Kolom)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # ====================
        # AREA 1: SIDEBAR KIRI
        # ====================
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(8, weight=1) # Agar ruang kosong terdorong ke bawah
        
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="File Sync TCP\n☁️", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))
        
        # Variabel State Konfigurasi
        self.server_ip_var = tk.StringVar(value="127.0.0.1")
        self.server_port_var = tk.StringVar(value="5001")
        self.client_id_var = tk.StringVar(value=os.getenv("COMPUTERNAME") or os.getenv("HOSTNAME") or "laptop")
        
        ctk.CTkLabel(self.sidebar_frame, text="IP Server:").grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")
        self.server_ip_entry = ctk.CTkEntry(self.sidebar_frame, textvariable=self.server_ip_var)
        self.server_ip_entry.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")
        
        ctk.CTkLabel(self.sidebar_frame, text="Port Server:").grid(row=3, column=0, padx=20, pady=(10, 0), sticky="w")
        self.server_port_entry = ctk.CTkEntry(self.sidebar_frame, textvariable=self.server_port_var)
        self.server_port_entry.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="ew")
        
        ctk.CTkLabel(self.sidebar_frame, text="ID Client Anda:").grid(row=5, column=0, padx=20, pady=(10, 0), sticky="w")
        self.client_id_entry = ctk.CTkEntry(self.sidebar_frame, textvariable=self.client_id_var)
        self.client_id_entry.grid(row=6, column=0, padx=20, pady=(0, 20), sticky="ew")
        
        # Tema Toggle
        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Tema Tampilan:", anchor="w")
        self.appearance_mode_label.grid(row=9, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(
            self.sidebar_frame, values=["Light", "Dark", "System"], command=self.change_appearance_mode_event
        )
        self.appearance_mode_optionemenu.grid(row=10, column=0, padx=20, pady=(10, 20))
        self.appearance_mode_optionemenu.set("System")
        
        # ====================
        # AREA 2: KONTEN UTAMA
        # ====================
        self.tabview = ctk.CTkTabview(self, width=600)
        self.tabview.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        self.tabview.add("🔄 Dashboard Sinkronisasi")
        self.tabview.add("♻️ Pusat Restore File")
        
        self.setup_sync_tab()
        self.setup_restore_tab()
        
    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)
        
    def setup_sync_tab(self):
        tab = self.tabview.tab("🔄 Dashboard Sinkronisasi")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        
        self.btn_open_folder = ctk.CTkButton(
            tab, text="📂 Buka Folder Lokal\n(Copy-Paste File Di Sini)", 
            height=60, font=ctk.CTkFont(weight="bold"), 
            command=self.open_sync_folder
        )
        self.btn_open_folder.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        
        self.btn_sync = ctk.CTkButton(
            tab, text="🚀 Mulai Sinkronisasi\n(Kirim ke Server)", 
            height=60, fg_color="#10b981", hover_color="#059669", 
            font=ctk.CTkFont(weight="bold"), 
            command=self.run_sync
        )
        self.btn_sync.grid(row=0, column=1, padx=20, pady=20, sticky="ew")
        
        # Terminal Buatan di GUI
        self.console = ctk.CTkTextbox(tab, height=380, font=ctk.CTkFont(family="Consolas", size=12))
        self.console.grid(row=1, column=0, columnspan=2, padx=20, pady=10, sticky="nsew")
        
        # Membelokkan output terminal asli ke Textbox
        sys.stdout = TextRedirector(self.console)
        sys.stderr = TextRedirector(self.console)
        print("Selamat datang di File Sync TCP (Mode GUI)!")
        print("Silakan buka folder, masukkan file, lalu tekan 'Mulai Sinkronisasi'.")
        
    def setup_restore_tab(self):
        tab = self.tabview.tab("♻️ Pusat Restore File")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        
        top_frame = ctk.CTkFrame(tab, fg_color="transparent")
        top_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=10)
        
        self.btn_refresh = ctk.CTkButton(
            top_frame, text="Ambil Daftar dari Server", 
            command=self.refresh_restore_list
        )
        self.btn_refresh.pack(side="left")
        
        self.btn_restore = ctk.CTkButton(
            top_frame, text="⬇️ Restore File Terpilih", 
            fg_color="#3b82f6", hover_color="#2563eb", 
            command=self.do_restore
        )
        self.btn_restore.pack(side="right")
        
        # Tabel Treeview Bawaan Tkinter (Di-styling ulang)
        style = ttk.Style()
        style.theme_use("default")
        # Membuat tabel terlihat menyatu dengan mode gelap
        style.configure("Treeview", 
                        background="#2b2b2b", foreground="white", 
                        fieldbackground="#2b2b2b", borderwidth=0, rowheight=30)
        style.configure("Treeview.Heading", background="#1f538d", foreground="white", relief="flat", font=('Inter', 10, 'bold'))
        style.map("Treeview", background=[('selected', '#3b82f6')])
        
        # Container tabel dengan scrollbar
        tree_frame = ctk.CTkFrame(tab)
        tree_frame.grid(row=1, column=0, padx=20, pady=(0,20), sticky="nsew")
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)
        
        self.tree = ttk.Treeview(tree_frame, columns=("filename", "size", "mtime"), show="headings")
        self.tree.heading("filename", text="Nama File Cadangan di Server")
        self.tree.heading("size", text="Ukuran (KB)")
        self.tree.heading("mtime", text="Waktu Perubahan")
        self.tree.column("filename", width=280)
        self.tree.column("size", width=100, anchor="center")
        self.tree.column("mtime", width=160, anchor="center")
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
    def open_sync_folder(self):
        """Membuka folder client_files menggunakan OS Default File Explorer."""
        folder_path = Path("client_files")
        folder_path.mkdir(exist_ok=True)
        if platform.system() == "Windows":
            os.startfile(folder_path)
        elif platform.system() == "Darwin":
            os.system(f"open {folder_path}")
        else:
            os.system(f"xdg-open {folder_path}")
            
    def run_sync(self):
        self.btn_sync.configure(state="disabled", text="Sinkronisasi Berjalan...")
        self.console.delete("1.0", tk.END) # Bersihkan terminal
        
        host = self.server_ip_var.get()
        try:
            port = int(self.server_port_var.get())
        except ValueError:
            messagebox.showerror("Error", "Port harus berupa angka.")
            self.btn_sync.configure(state="normal", text="🚀 Mulai Sinkronisasi\n(Kirim ke Server)")
            return
            
        client_id = self.client_id_var.get()
        folder = Path("client_files")
        folder.mkdir(exist_ok=True)
        
        def sync_thread():
            try:
                sync_folder(host, port, folder, client_id, force=False, watch_mode=False)
            except Exception as e:
                print(f"Error saat sinkronisasi: {e}")
            finally:
                self.btn_sync.configure(state="normal", text="🚀 Mulai Sinkronisasi\n(Kirim ke Server)")
                
        # Harus berjalan di thread lain agar GUI tidak freeze
        threading.Thread(target=sync_thread, daemon=True).start()

    def refresh_restore_list(self):
        self.btn_refresh.configure(state="disabled", text="Loading...")
        
        host = self.server_ip_var.get()
        port = int(self.server_port_var.get())
        client_id = self.client_id_var.get()
        
        def fetch_thread():
            versions = fetch_versions(host, port, client_id)
            # Bersihkan tabel lama
            for row in self.tree.get_children():
                self.tree.delete(row)
                
            for v in versions:
                size_kb = v['size'] / 1024
                self.tree.insert("", tk.END, values=(v['filename'], f"{size_kb:.1f}", v['mtime']))
                
            self.btn_refresh.configure(state="normal", text="Ambil Daftar dari Server")
            
        threading.Thread(target=fetch_thread, daemon=True).start()
        
    def do_restore(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("Peringatan", "Pilih file yang ingin di-restore dari daftar.")
            return
            
        file_data = self.tree.item(selected_item, "values")
        filename = file_data[0]
        
        host = self.server_ip_var.get()
        port = int(self.server_port_var.get())
        client_id = self.client_id_var.get()
        folder = Path("client_files")
        
        def restore_t():
            self.btn_restore.configure(state="disabled", text="Mendownload...")
            
            # Pindah ke tab sync agar user bisa lihat log download
            self.tabview.set("🔄 Dashboard Sinkronisasi")
            print("="*40)
            print(f"Mulai me-restore: {filename}...")
            
            success = restore_file(host, port, client_id, filename, folder)
            if success:
                print(f"✅ Berhasil me-restore file!")
            else:
                print(f"❌ Gagal me-restore file.")
            print("="*40)
            self.btn_restore.configure(state="normal", text="⬇️ Restore File Terpilih")
            
        threading.Thread(target=restore_t, daemon=True).start()

if __name__ == "__main__":
    app = ClientGUI()
    app.mainloop()
