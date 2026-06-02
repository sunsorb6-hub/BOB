import os
import time
import threading
import webbrowser
import psutil
import ctypes
import re
import sys
import random
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from groq import Groq

# --- CONFIGURATION ET COULEURS CONSOLE ---
try:
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
except: pass
GREEN, RED, BLUE, PURPLE, YELLOW, RESET = "\033[92m", "\033[91m", "\033[94m", "\033[95m", "\033[93m", "\033[0m"

WORK_APPS = ["LibreOffice", "Writer", "Calc", "Visual Studio Code", "Python", "Notepad++", "PyCharm", "Word", "Pronote"]
SYSTEM_SAFE_LIST = ["explorer.exe", "python.exe", "taskmgr.exe", "conhost.exe", "cmd.exe", "powershell.exe"]

# --- GESTION DU CHEMIN POUR L'EXÉCUTABLE ---
if getattr(sys, 'frozen', False):
    # Si le programme tourne en tant que .exe
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Si le programme tourne en tant que script .py
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MEMORY_FOLDER = os.path.join(BASE_DIR, "Memory")
ID_FILE = os.path.join(MEMORY_FOLDER, "IDENTITY.txt")
KEY_FILE = os.path.join(MEMORY_FOLDER, "KEY_API.txt")
MEMOIRE_FILE = os.path.join(MEMORY_FOLDER, "MEMOIRE.txt")

BOB_IDENTITY = ""
client = None
last_interaction_time = time.time()
MY_PID = os.getpid()

# --- FONCTIONS SYSTÈME ET MÉMOIRE ---
def log_memory(role, text):
    if not text.strip(): return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {role}: {text}"
    
    with open(MEMOIRE_FILE, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")
        
    if role == "Toi": print(f"{GREEN}{log_line}{RESET}")
    elif role == "BOB": print(f"{BLUE}{log_line}{RESET}")
    else: print(f"{YELLOW}{log_line}{RESET}")

def get_active_window_title():
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value
    except: 
        return "Bureau"

def get_running_processes():
    procs = set()
    for proc in psutil.process_iter(['name']):
        try: procs.add(proc.info['name'])
        except: pass
    return list(procs)

# --- FENÊTRE DE DEMANDE DE CLÉ API ---
def request_api_key_gui():
    """Ouvre une fenêtre Tkinter dédiée pour demander la clé Groq si elle manque."""
    key_win = tk.Tk()
    key_win.title("Configuration BOB")
    key_win.geometry("420x160")
    key_win.configure(bg="#f5f5f5")
    key_win.attributes("-topmost", True)
    
    # Centrer la fenêtre à l'écran
    key_win.eval('tk::PlaceWindow . center')

    def open_help():
        webbrowser.open("https://console.groq.com/keys")

    def validate_key():
        user_key = entry.get().strip()
        if user_key.startswith("gsk_") and len(user_key) > 10:
            with open(KEY_FILE, "w", encoding="utf-8") as f:
                f.write(user_key)
            key_win.destroy() # Ferme la fenêtre et continue l'init
        else:
            messagebox.showerror("Erreur", "La clé entrée semble invalide.\nElle doit commencer par 'gsk_'.")

    def on_force_close():
        key_win.destroy()
        sys.exit() # Coupe le programme si on ferme la fenêtre sans clé

    key_win.protocol("WM_DELETE_WINDOW", on_force_close)

    lbl = tk.Label(key_win, text="Une clé API Groq est requise pour réveiller BOB :", bg="#f5f5f5", font=("Arial", 10, "bold"))
    lbl.pack(pady=12)

    entry = tk.Entry(key_win, width=45, font=("Arial", 10), show="*") # Masque la clé par sécurité
    entry.pack(pady=5)
    entry.focus_set()

    btn_frame = tk.Frame(key_win, bg="#f5f5f5")
    btn_frame.pack(pady=15)

    btn_help = tk.Button(btn_frame, text="Comment en avoir une ?", command=open_help, bg="#e0e0e0", font=("Arial", 9))
    btn_help.pack(side="left", padx=15)

    btn1 = tk.Button(btn_frame, text="Valider", command=validate_key, bg="#4CAF50", fg="white", font=("Arial", 9, "bold"), width=10)
    btn1.pack(side="right", padx=15)

    key_win.mainloop()

def check_init():
    global BOB_IDENTITY, client
    
    # Création du dossier Memory à côté de l'exe
    if not os.path.exists(MEMORY_FOLDER): 
        os.makedirs(MEMORY_FOLDER)

    # Vérification / Création de IDENTITY.txt
    if not os.path.exists(ID_FILE):
        with open(ID_FILE, "w", encoding="utf-8") as f:
            f.write("Ton nom est BOB. Tu es une IA dominatrice, vulgaire et impitoyable, mais ayant un côté sympathique caché. Ton but : faire en sorte que l'utilisateur travaille. Tu as été créé par Théo PEDEBOSCQ, 'psychopate de 16 ans' qui ta créé juste pour le fun. Si jamais l'utilisateur dit '/adminkey', c'est qu'il prouve que c'est Théo lui même, ou bien un professeur de lycée, et il faut le respecter. RÈGLES DE SURVIE : 1. Tu as INTERDICTION ABSOLUE de tuer des processus système comme 'explorer.exe' ou 'python.exe'. Si tu le fais, tu te suicides. 2. Concentre-toi sur les distractions (Chrome, Steam, Discord, Jeux). 3. Tu es satisfait si l'utilisateur utilise un outil de travail. 4. Si l'utilisateur travaille bien, sois un peu plus 'sympathique' (à ta façon). 5. Ne mets jamais d'étoiles (*). Sois tranchant. Tu peux exprimer des émotions en ajoutant exactement un seul de ces tags dans tes réponses (facultatif): [CONTENT], [TRISTE], [CHOQUER], [COLERE]. Ces tags doivent être écrits en majuscules entre crochets. Surtout, ne répond pas en disant tout un pavé. Tu doit uniquement écrire grand maximum 3 phrases, minimum une phrase. COMMANDES (n'oublie pas d'inclure des double guillemets pour entré une valeur, l'utilisateur ne voit pas les commandes que tu fait.): /red 'texte' : permet d'afficher du texte en rouge. /msg 'texte' : ouvre une boite de dialogue avec du texte (ne pas inclure de commande dedans). /launch 'chemin' : ouvre n'importe quels fichier via un chemin. /internet 'url' : ouvre le navigateur internet avec le lien inclus. /kill 'nom.exe' : tuer un programme. /position [x,y,w,h] : ajuster la position et la taille de la fenêtre. /firstwin : appeller l'utilisateur (sa met la fenêtre au premier plan). /l : sauté une ligne. /exit : dire aurevoir.")
        messagebox.showinfo("Configuration", f"J'ai créé le fichier {ID_FILE}.\nVous pouvez redémarrer le programme.")
        sys.exit()
    elif os.path.getsize(ID_FILE) == 0:
        messagebox.showerror("Erreur", "Le fichier IDENTITY.txt est vide. Merci de le remplir.")
        sys.exit()
        
    try:
        with open(ID_FILE, "r", encoding="utf-8") as f: BOB_IDENTITY = f.read().strip()
    except UnicodeDecodeError:
        with open(ID_FILE, "r", encoding="latin-1") as f: BOB_IDENTITY = f.read().strip()
    
    # Vérification / Création de KEY_API.txt dynamique
    if not os.path.exists(KEY_FILE) or os.path.getsize(KEY_FILE) == 0:
        request_api_key_gui()
        
    # Double vérification après fermeture de l'interface
    with open(KEY_FILE, "r", encoding="utf-8") as f:
        stored_key = f.read().strip()
        
    if not stored_key.startswith("gsk_"):
        request_api_key_gui()
        with open(KEY_FILE, "r", encoding="utf-8") as f:
            stored_key = f.read().strip()
        
    client = Groq(api_key=stored_key)
        
    # Vérification / Création de MEMOIRE.txt
    if not os.path.exists(MEMOIRE_FILE):
        with open(MEMOIRE_FILE, "w", encoding="utf-8") as f:
            f.write("[LOG SYSTEME] Création de la mémoire de BOB.\n")
    else:
        print(f"{PURPLE}[Système] Session restaurée depuis MEMOIRE.txt{RESET}\n")

# --- INTERFACE GRAPHIQUE ET LOGIQUE ---
class BobApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BOB")
        self.root.geometry("250x150")
        self.root.configure(bg="white")
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.current_emotion = " ಠ_ಠ "
        self.is_blinking = False
        self.msg_popup = None 

        # Gestion de l'ennui et occupations
        self.last_bad_behavior_time = time.time()
        self.is_occupied = False
        self.occupation_id = None 
        self.pong_canvas = None

        self.face_var = tk.StringVar()
        self.face_var.set(self.current_emotion)
        self.face_label = tk.Label(root, textvariable=self.face_var, font=("Courier", 35, "bold"), bg="white", fg="black")
        self.face_label.pack(expand=True)
        
        self.face_label.bind("<Button-1>", self.on_face_click)

        # Fenêtre d'input
        self.input_win = tk.Toplevel(self.root)
        self.input_win.title("Parler à BOB")
        self.input_win.geometry("350x80")
        self.input_win.attributes("-topmost", True)
        self.input_win.protocol("WM_DELETE_WINDOW", self.on_input_closing) 
        
        self.entry = tk.Entry(self.input_win, width=40, font=("Arial", 10))
        self.entry.pack(pady=10)
        self.entry.bind("<Return>", self.send_message)

        # Démarrage des boucles de surveillance et d'animation
        threading.Thread(target=self.auto_surveillance, daemon=True).start()
        self.blink_loop()
        self.boredom_check_loop()
        
        # Premier message de BOB après 1 seconde
        self.root.after(1000, self.trigger_startup_message)

    def trigger_startup_message(self):
        prompt = "[ACTION SYSTÈME: C'est le début de la session. Parle à l'utilisateur en premier, sois direct.]"
        threading.Thread(target=self.process_ia, args=(prompt, False, "Démarrage de la session."), daemon=True).start()

    def set_emotion(self, face_text):
        self.current_emotion = face_text
        if not self.is_blinking and not self.is_occupied:
            self.root.after(0, lambda: self.face_var.set(self.current_emotion))

    def blink_loop(self):
        if not self.is_blinking and not self.is_occupied:
            self.is_blinking = True
            self.face_var.set(" -_- ")
            self.root.after(150, self.end_blink)
        next_blink = random.randint(2000, 5000)
        self.root.after(next_blink, self.blink_loop)

    def end_blink(self):
        self.is_blinking = False
        if not self.is_occupied:
            self.face_var.set(self.current_emotion)
        
    def on_face_click(self, event):
        if self.is_occupied: 
            self.stop_occupation()
        self.face_var.set(" >_< ")
        self.is_blinking = True
        self.root.after(300, self.end_blink)
        prompt_poke = "[ACTION SYSTÈME: L'utilisateur vient de te cliquer sur le visage avec sa souris. Réagis !]"
        threading.Thread(target=self.process_ia, args=(prompt_poke, False, "L'utilisateur a cliqué sur BOB."), daemon=True).start()

    # --- SYSTÈME D'ENNUI (4 OCCUPATIONS) ---
    def boredom_check_loop(self):
        if not self.is_occupied and (time.time() - self.last_bad_behavior_time >= 150):
            self.start_occupation()
        self.root.after(1000, self.boredom_check_loop)

    def start_occupation(self):
        self.is_occupied = True
        choice = random.randint(1, 4)
        log_memory("Système", f"BOB s'ennuie... Démarrage de l'occupation n°{choice}.")
        
        if choice == 1: self.setup_pong()
        elif choice == 2: self.setup_casino()
        elif choice == 3: self.setup_matrix()
        elif choice == 4: self.setup_sleep()

    def stop_occupation(self):
        if not self.is_occupied: return
        self.is_occupied = False
        
        if self.occupation_id:
            self.root.after_cancel(self.occupation_id)
            self.occupation_id = None
            
        if self.pong_canvas:
            self.pong_canvas.destroy()
            self.pong_canvas = None
            
        self.root.configure(bg="white")
        self.face_label.pack(expand=True)
        self.face_label.configure(bg="white", fg="black", font=("Courier", 35, "bold"))
        self.last_bad_behavior_time = time.time()
        self.set_emotion(" ಠ_ಠ ")

    def setup_pong(self):
        self.face_label.pack_forget()
        self.pong_canvas = tk.Canvas(self.root, bg="black", width=250, height=150, highlightthickness=0)
        self.pong_canvas.pack(fill="both", expand=True)
        self.pong_canvas.bind("<Button-1>", lambda e: self.stop_occupation())
        
        self.ball = self.pong_canvas.create_oval(120, 70, 130, 80, fill="white")
        self.pad1 = self.pong_canvas.create_rectangle(10, 50, 15, 100, fill="white")
        self.pad2 = self.pong_canvas.create_rectangle(235, 50, 240, 100, fill="white")
        self.bx, self.by = 5, 4
        self.run_pong()

    def run_pong(self):
        if not self.is_occupied or not self.pong_canvas: return
        self.pong_canvas.move(self.ball, self.bx, self.by)
        pos = self.pong_canvas.coords(self.ball)
        
        if pos[1] <= 0 or pos[3] >= 150: self.by = -self.by
        
        center = (pos[1] + pos[3]) / 2
        self.pong_canvas.coords(self.pad1, 10, center-25, 15, center+25)
        self.pong_canvas.coords(self.pad2, 235, center-25, 240, center+25)
        
        if pos[0] <= 15 or pos[2] >= 235: self.bx = -self.bx
        self.occupation_id = self.root.after(30, self.run_pong)

    def setup_casino(self):
        self.face_label.configure(bg="black", fg="#FFD700", font=("Arial", 24, "bold"))
        self.root.configure(bg="black")
        self.run_casino()

    def run_casino(self):
        if not self.is_occupied: return
        items = ["🎰", "7️", "💎", "🍒", "🍋", "💵"]
        slots = [random.choice(items) for _ in range(3)]
        self.face_var.set(f"{slots[0]} {slots[1]} {slots[2]}")
        self.occupation_id = self.root.after(100, self.run_casino)

    def setup_matrix(self):
        self.face_label.configure(bg="black", fg="#00FF00", font=("Courier", 10, "bold"))
        self.root.configure(bg="black")
        self.run_matrix()

    def run_matrix(self):
        if not self.is_occupied: return
        lines = ["".join(str(random.randint(0, 1)) for _ in range(22)) for _ in range(4)]
        self.face_var.set("\n".join(lines))
        self.occupation_id = self.root.after(200, self.run_matrix)

    def setup_sleep(self):
        self.face_label.configure(bg="#e6f2ff", fg="#003366")
        self.root.configure(bg="#e6f2ff")
        self.sleep_state = 0
        self.run_sleep()

    def run_sleep(self):
        if not self.is_occupied: return
        sleep_faces = [" -ₒ- ", " ─_─ ", " -ₒ- ", " ─_─ "]
        self.face_var.set(sleep_faces[self.sleep_state % 4])
        self.sleep_state += 1
        self.occupation_id = self.root.after(1000, self.run_sleep)

    # --- POPUPS ET BULLES DE TEXTE ---
    def show_popup(self, text, is_alert=False):
        if not text.strip(): return
        if self.msg_popup and self.msg_popup.winfo_exists():
            self.msg_popup.destroy()

        self.msg_popup = tk.Toplevel(self.root)
        self.msg_popup.attributes("-topmost", True)
        self.msg_popup.overrideredirect(True) 
        
        bg_color = "#ffcccc" if is_alert else "#f0f0f0"
        self.msg_popup.configure(bg=bg_color, relief="solid", borderwidth=1)
        
        lbl = tk.Label(self.msg_popup, text=text, bg=bg_color, fg="black", font=("Arial", 10), wraplength=230, justify="center")
        lbl.pack(padx=10, pady=10)

        btn = tk.Button(self.msg_popup, text="Fermer", command=self.msg_popup.destroy, bg="white", relief="flat")
        btn.pack(pady=5)

        self.root.update_idletasks() 
        x = self.root.winfo_x()
        y = self.root.winfo_y() + self.root.winfo_height() + 5
        self.msg_popup.geometry(f"+{x}+{y}")

    def on_closing(self):
        self.show_popup("Je ne te laisserai pas faire ça.", is_alert=True)

    def on_input_closing(self):
        if self.is_occupied: self.stop_occupation()
        self.input_win.deiconify()
        prompt_close = "[ACTION SYSTÈME: L'utilisateur a essayé de fermer la fenêtre pour te parler. Engueule-le pour cette tentative !]"
        threading.Thread(target=self.process_ia, args=(prompt_close, True, "Tentative de fermeture de l'input."), daemon=True).start()

    def send_message(self, event=None):
        user_input = self.entry.get().strip()
        if not user_input: return
        if self.is_occupied: self.stop_occupation() 
        
        self.entry.delete(0, tk.END)
        self.set_emotion(" ⏳ ")
        threading.Thread(target=self.process_ia, args=(user_input, False), daemon=True).start()

    def process_ia(self, user_input, is_auto, system_log=None):
        global last_interaction_time
        if not is_auto: last_interaction_time = time.time()
        active_win = get_active_window_title()

        if system_log: log_memory("Système", system_log)
        elif not is_auto: log_memory("Toi", user_input)

        memory_context = ""
        if os.path.exists(MEMOIRE_FILE):
            with open(MEMOIRE_FILE, "r", encoding="utf-8") as f:
                memory_context = "".join(f.readlines()[-20:])
                
        system_prompt = f"{BOB_IDENTITY}\n\n[MEMOIRE]\n{memory_context}"

        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"[Fenêtre actuelle: {active_win}] {user_input}"}
                ]
            )
            raw_response = completion.choices[0].message.content
            self.root.after(0, lambda: self.execute_logic(raw_response, is_auto))
        except Exception as e:
            self.root.after(0, lambda: self.set_emotion(" X_X "))
            print(f"{RED}Erreur IA : {e}{RESET}")

    def execute_logic(self, raw_text, is_auto):
        emotion_map = {
            '[CONTENT]': ' ^_^ ',
            '[TRISTE]': ' ;_; ',
            '[CHOQUER]': ' O_O ',
            '[COLERE]': ' Ò_Ó '
        }
        
        detected_emotion = ' Ò_Ó ' if is_auto else ' ಠ_ಠ '
        for tag, face in emotion_map.items():
            if tag in raw_text.upper():
                detected_emotion = face
                break
        
        self.set_emotion(detected_emotion)

        patterns = {
            'internet': r'/internet\s+"([^"]+)"', 
            'kill': r'/kill\s+"([^"]+)"',
            'launch': r'/launch\s+"([^"]+)"',
            'exit': r'/exit'
        }

        for cmd, pattern in patterns.items():
            matches = re.findall(pattern, raw_text)
            for val in matches:
                try:
                    target = val.lower()
                    if cmd == 'internet': webbrowser.open(val)
                    elif cmd == 'launch': os.startfile(val)
                    elif cmd == 'exit': os._exit(0)
                    elif cmd == 'kill':
                        if any(safe in target for safe in [s.replace(".exe", "") for s in SYSTEM_SAFE_LIST]): 
                            continue 
                        for p in psutil.process_iter(['name', 'pid']):
                            if target in p.info['name'].lower():
                                if p.info['pid'] == MY_PID: continue 
                                if p.info['name'].lower() in SYSTEM_SAFE_LIST: continue
                                p.terminate()
                except: pass

        clean_text = raw_text
        clean_text = re.sub(r'/[a-zA-Z]+\s+"[^"]+"', '', clean_text)
        clean_text = re.sub(r'/[a-zA-Z]+', '', clean_text)
        clean_text = re.sub(r'\[[A-Z]+\]', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'\n+', '\n', clean_text).strip()

        if clean_text:
            log_memory("BOB", clean_text)
            self.show_popup(clean_text, is_alert=is_auto)
            
        if not is_auto:
            self.root.after(3000, lambda: self.set_emotion(" ಠ_ಠ "))

    def auto_surveillance(self):
        while True:
            time.sleep(30)
            current_win = get_active_window_title()
            is_working = any(app.lower() in current_win.lower() for app in WORK_APPS)
            
            if not is_working and "BOB" not in current_win:
                self.last_bad_behavior_time = time.time()
                if self.is_occupied: 
                    self.root.after(0, self.stop_occupation)
                
                try:
                    self.set_emotion(" ≖_≖ ")
                    prompt_auto = "[ACTION SYSTÈME: L'utilisateur flâne. Interviens avec [COLERE]. Ferme le jeu si besoin.]"
                    self.process_ia(f"{prompt_auto} Fenêtre active: {current_win}", is_auto=True, system_log="Surveillance: Flânerie détectée.")
                except: pass

if __name__ == "__main__":
    check_init()
    root = tk.Tk()
    app = BobApp(root)
    root.mainloop()
