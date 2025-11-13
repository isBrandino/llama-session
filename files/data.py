#!/usr/bin/env python3
from datetime import datetime
import sqlite3
import json
import os
import subprocess
import signal
import json
import sys
import ollama
import re

# ANSI COLORS 
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
BRED = "\033[91m"
BGREEN = "\033[92m"
BYELLOW = "\033[93m"
BCYAN = "\033[96m"

#  CONFIG 
DB_PATH = "ollama_memory.db"
CONFIG_FILE = "config.json"
MAX_CONTEXT = 5
PAGE_SIZE = 10


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                return data.get('model', 'No Model Loaded')
        except:
            return 'No Model Loaded'
    return 'No Model Loaded'

def save_config(model):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({'model': model}, f, indent=2)

MODEL = load_config()

if os.name == 'nt':
    os.system('')

def is_exit(cmd):
    return cmd.strip().lower() in ['exit', 'quit', 'q', 'bye']

def stop_ollama_model(model_name):
    try:
        print(f"{BYELLOW}Stopping model '{model_name}'...{RESET}")
        result = subprocess.run(['ollama', 'stop', model_name], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"{BGREEN}Model stopped.{RESET}")
        else:
            print(f"{BRED}Stop failed: {result.stderr.strip()}{RESET}")
    except Exception as e:
        print(f"{BRED}Error stopping model: {e}{RESET}")

def safe_input(prompt):
    try:
        user_input = input(prompt).strip()
        if is_exit(user_input):
            print(f"{BYELLOW}Stopping model and exiting...{RESET}")
            stop_ollama_model(MODEL)
            print(f"{BYELLOW}Goodbye!{RESET}")
            sys.exit(0)
        return user_input
    except (EOFError, KeyboardInterrupt):
        print(f"\n{BYELLOW}Stopping model and exiting...{RESET}")
        stop_ollama_model(MODEL)
        print(f"{BYELLOW}Goodbye!{RESET}")
        sys.exit(0)

signal.signal(signal.SIGINT, lambda sig, frame: safe_input(''))

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            model TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_session ON chats(session_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_content ON chats(content)')

    # New table for session names
    cur.execute('''
        CREATE TABLE IF NOT EXISTS session_names (
            session_id TEXT PRIMARY KEY,
            name TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_session_name(session_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT name FROM session_names WHERE session_id = ?', (session_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def set_session_name(session_id, name):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT OR REPLACE INTO session_names (session_id, name) VALUES (?, ?)', (session_id, name))
    conn.commit()
    conn.close()

def delete_session_name(session_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('DELETE FROM session_names WHERE session_id = ?', (session_id,))
    conn.commit()
    conn.close()
    
def log_message(session_id, role, content, model=MODEL):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO chats (session_id, role, content, model)
        VALUES (?, ?, ?, ?)
    ''', (session_id, role, content, model))
    conn.commit()
    conn.close()

def get_context(session_id, limit=MAX_CONTEXT):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        SELECT role, content FROM chats
        WHERE session_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (session_id, limit * 2))
    rows = cur.fetchall()[::-1]
    conn.close()
    return [{'role': r, 'content': c} for r, c in rows]

def chat_with_memory(prompt, session_id):
    context = get_context(session_id)
    context.append({'role': 'user', 'content': prompt})
    try:
        response = ollama.chat(model=MODEL, messages=context)
        answer = response['message']['content']
    except Exception as e:
        return f"{BRED}[Error] {e}{RESET}", session_id

    log_message(session_id, 'user', prompt)
    log_message(session_id, 'assistant', answer)
    return answer, session_id

def get_session_size(session_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        SELECT SUM(LENGTH(content) + LENGTH(role) + LENGTH(model) + LENGTH(session_id))
        FROM chats WHERE session_id = ?
    ''', (session_id,))
    total = cur.fetchone()[0] or 0
    conn.close()
    return total

def format_size(bytes_size):
    if bytes_size >= 1024**3:
        return f"{bytes_size / (1024**3):.2f} GB"
    elif bytes_size >= 1024**2:
        return f"{bytes_size / (1024**2):.2f} MB"
    elif bytes_size >= 1024:
        return f"{bytes_size / 1024:.2f} KB"
    else:
        return f"{bytes_size} B"

# May need updates
def clean_reply(reply):
    reply = reply.strip()
    lines = reply.splitlines()
    cleaned_lines = []
    in_code_block = False
    for line in lines:
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            cleaned_lines.append(line)
            continue
        if in_code_block:
            cleaned_lines.append(line)
        else:
            stripped = line.rstrip()
            if stripped or (cleaned_lines and cleaned_lines[-1].strip()):
                cleaned_lines.append(stripped)
    while cleaned_lines and not cleaned_lines[0].strip():
        cleaned_lines.pop(0)
    while cleaned_lines and not cleaned_lines[-1].strip():
        cleaned_lines.pop()
    return '\n'.join(cleaned_lines)

def list_available_models():
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
        if result.returncode != 0:
            return []
        lines = result.stdout.strip().splitlines()[1:]
        return [line.split()[0] for line in lines if line.strip()]
    except:
        return []
    
    
def set_model_menu():
    global MODEL
    print(f"\n{BOLD}Available Models:{RESET}")
    models = list_available_models()
    if not models:
        print(f"{BRED}No models found. Run 'ollama pull <model>'{RESET}")
        input(f"{BCYAN}Press Enter...{RESET}")
        return

    for i, m in enumerate(models, 1):
        status = f"{BGREEN}active{RESET}" if m == MODEL else ""
        print(f"{BYELLOW}{i}. {MAGENTA}{m}{RESET} {status}")

    choice = safe_input(f"\n{BCYAN}Enter model name or # (or 'exit'): {RESET}").strip()
    if not choice:
        return

    selected = None
    if choice.isdigit() and 1 <= int(choice) <= len(models):
        selected = models[int(choice)-1]
    elif choice in models:
        selected = choice
    else:
        print(f"{BRED}Invalid model.{RESET}")
        input(f"{BCYAN}Press Enter...{RESET}")
        return

    if selected == MODEL:
        print(f"{BYELLOW}Already using '{MODEL}'.{RESET}")
    else:
        print(f"{BYELLOW}Switching to '{selected}'...{RESET}")
        stop_ollama_model(MODEL)
        save_config(selected)
        os.execl(sys.executable, sys.executable, *sys.argv)
    input(f"{BCYAN}Press Enter...{RESET}")
    
def set_model_menu():
    global MODEL
    print(f"\n{BOLD}Available Models:{RESET}")
    models = list_available_models()
    if not models:
        print(f"{BRED}No models found. Run 'ollama pull <model>'{RESET}")
        input(f"{BCYAN}Press Enter...{RESET}")
        return

    for i, m in enumerate(models, 1):
        status = f"{BGREEN}active{RESET}" if m == MODEL else ""
        print(f"{BYELLOW}{i}. {MAGENTA}{m}{RESET} {status}")

    choice = safe_input(f"\n{BCYAN}Enter model name or # (or 'exit'): {RESET}").strip()
    if not choice:
        return

    selected = None
    if choice.isdigit() and 1 <= int(choice) <= len(models):
        selected = models[int(choice)-1]
    elif choice in models:
        selected = choice
    else:
        print(f"{BRED}Invalid model.{RESET}")
        input(f"{BCYAN}Press Enter...{RESET}")
        return

    if selected == MODEL:
        print(f"{BYELLOW}Already using '{MODEL}'.{RESET}")
    else:
        print(f"{BYELLOW}Switching to '{selected}'...{RESET}")
        stop_ollama_model(MODEL)
        save_config(selected)
        os.execl(sys.executable, sys.executable, *sys.argv)
    input(f"{BCYAN}Press Enter...{RESET}")

def list_sessions():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        SELECT session_id, MAX(timestamp), COUNT(*) FROM chats
        GROUP BY session_id ORDER BY MAX(timestamp) DESC LIMIT 20
    ''')
    sessions = cur.fetchall()
    conn.close()

    if not sessions:
        print(f"{BRED}No sessions found.{RESET}")
        input(f"{BCYAN}Press Enter...{RESET}")
        return None

    print(f"\n{BOLD}List Sessions:{RESET}")
    for i, (sid, last, count) in enumerate(sessions, 1):
        name = get_session_name(sid)
        display_name = name or f"{sid[:8]}..."
        size_str = format_size(get_session_size(sid))
        print(f"{BYELLOW}{i}. {MAGENTA}{display_name}{RESET} | {last[5:16]} | {count} msg(s) | {size_str}")

    print(f"\n{BCYAN}Actions: 'rename #', 'delete #', '#' to resume, 'new' for new, 'back' to exit{RESET}")
    choice = safe_input(f"{BCYAN}Choose: {RESET}").lower().strip()

    if choice == "back":
        return None

    if choice == "new":
        # You must define create_new_session() elsewhere
        # Example: return create_new_session()
        print(f"{BYELLOW}New session not implemented.{RESET}")
        input(f"{BCYAN}Press Enter...{RESET}")
        return None

    parts = choice.split()
    if len(parts) == 2 and parts[1].isdigit():
        action, num = parts[0], int(parts[1]) - 1
        if not (0 <= num < len(sessions)):
            print(f"{BRED}Invalid number.{RESET}")
            input(f"{BCYAN}Press Enter...{RESET}")
            return None
        sid = sessions[num][0]

        if action == "rename":
            new_name = safe_input(f"{BCYAN}New name for '{sid[:8]}...': {RESET}")
            if new_name:
                set_session_name(sid, new_name)
                print(f"{BGREEN}Renamed to: {new_name}{RESET}")
            else:
                print(f"{BYELLOW}Name unchanged.{RESET}")
            input(f"{BCYAN}Press Enter...{RESET}")
            return None

        elif action == "delete":
            confirm = safe_input(f"{BRED}Delete session '{sid[:8]}...' forever? (yes/y, no/n): {RESET}").lower()
            if confirm in ['yes', 'y']:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute('DELETE FROM chats WHERE session_id = ?', (sid,))
                cur.execute('DELETE FROM session_names WHERE session_id = ?', (sid,))
                conn.commit()
                conn.close()
                print(f"{BGREEN}Session deleted.{RESET}")
            else:
                print(f"{BYELLOW}Canceled.{RESET}")
            input(f"{BCYAN}Press Enter...{RESET}")
            return None

        elif action == "resume":
            return sid

    elif choice.isdigit():
        num = int(choice) - 1
        if 0 <= num < len(sessions):
            return sessions[num][0]
        else:
            print(f"{BRED}Invalid number.{RESET}")
            input(f"{BCYAN}Press Enter...{RESET}")
            return None

    else:
        print(f"{BRED}Invalid input. Use: rename 1, delete 2, 3, new, back{RESET}")
        input(f"{BCYAN}Press Enter...{RESET}")
        return None

def search_logs():
    query = safe_input(f"{BCYAN}\nSearch query (or 'exit'): {RESET}")
    if not query:
        return None

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        SELECT session_id, role, content, timestamp FROM chats
        WHERE content LIKE ? ORDER BY timestamp DESC LIMIT ?
    ''', (f'%{query}%', PAGE_SIZE))
    results = cur.fetchall()
    conn.close()

    if not results:
        print(f"{BRED}No results.{RESET}")
        return None

    print(f"\n{BOLD}{len(results)} result(s) for '{query}':{RESET}\n")
    for i, (sid, role, content, ts) in enumerate(results, 1):
        short = (content[:100] + '...') if len(content) > 100 else content
        role_color = BCYAN if role == 'user' else BGREEN
        name = get_session_name(sid)
        display = name or f"{sid[:8]}..."
        print(f"{BYELLOW}{i}. [{ts[5:16]}]{RESET} {role_color}{role.upper()}: {short}{RESET}")
        print(f" {MAGENTA}Session: {display}{RESET}\n")

    choice = safe_input(f"{BCYAN}View #, 's#' to chat, or Enter: {RESET}").lower()
    if choice.startswith('s') and choice[1:].isdigit():
        idx = int(choice[1:]) - 1
        if 0 <= idx < len(results):
            return results[idx][0]
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(results):
            role, content, ts = results[idx][1], results[idx][2], results[idx][3]
            role_color = BCYAN if role == 'user' else BGREEN
            print(f"\n{BOLD}--- Full Message ---{RESET}")
            print(f"{BYELLOW}[{ts[5:16]}]{RESET} {role_color}{role.upper()}{RESET}")
            print(f"{role_color}{content}{RESET}\n")
            input(f"{BCYAN}Press Enter...{RESET}")
    return None



def sanitize_filename(name):
    # Remove invalid characters
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace spaces and multiple dashes with single underscore
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'_+', '_', name)
    # Trim and limit length
    name = name.strip('_')[:50]
    return name or "unnamed"

# Export chat data to markdown
def export_session():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        SELECT session_id, MAX(timestamp), COUNT(*) FROM chats
        GROUP BY session_id ORDER BY MAX(timestamp) DESC LIMIT 10
    ''')
    sessions = cur.fetchall()
    conn.close()

    if not sessions:
        print(f"{BRED}No sessions to export.{RESET}")
        return

    print(f"\n{BOLD}Recent Sessions (choose to export):{RESET}")
    for i, (sid, last, count) in enumerate(sessions, 1):
        name = get_session_name(sid)
        display = name or f"{sid[:8]}..."
        size_str = format_size(get_session_size(sid))
        print(f"{BYELLOW}{i}. {MAGENTA}{display}{RESET} | {last[5:16]} | {count} msg(s) | {size_str}")

    choice = safe_input(f"\n{BCYAN}Enter #, ID, or skip: {RESET}").lower()
    session_id = None

    if choice.isdigit() and 1 <= int(choice) <= len(sessions):
        session_id = sessions[int(choice)-1][0]
    elif len(choice) >= 8:
        matches = [s[0] for s in sessions if s[0].startswith(choice)]
        if len(matches) == 1:
            session_id = matches[0]
        elif len(matches) > 1:
            print(f"{BRED}Multiple matches. Pick a number above.{RESET}")
            return
        else:
            print(f"{BRED}Session not found.{RESET}")
            return
    else:
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT role, content, timestamp FROM chats WHERE session_id = ? ORDER BY timestamp', (session_id,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print(f"{BRED}No messages in session.{RESET}")
        return

    name = get_session_name(session_id) or session_id[:8]
    safe_name = sanitize_filename(name)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    filename = f"chat_{safe_name}_{timestamp}.md"
    filename = filename.replace(' ', '_')
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# Ollama Chat Export\n")
        f.write(f"**Session ID:** `{session_id}`\n")
        f.write(f"**Name:** {name}\n")
        f.write(f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for role, content, ts in rows:
            f.write(f"### {role.capitalize()} — {ts[5:16]}\n")
            f.write(f"{content}\n\n")
    print(f"{BGREEN}Exported: {filename}{RESET}")
