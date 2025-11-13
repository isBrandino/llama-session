
from data import *


def main_menu():
    global MODEL
    init_db()
    current_session = None

    print(f"{BOLD}Llama for ollama{RESET}")
    print(f"{MAGENTA}Model: {MODEL}{RESET} | {YELLOW}DB: {os.path.abspath(DB_PATH)}{RESET}")
    print(f"{BCYAN}Type 'exit', 'quit', or 'q' anywhere to quit.\n{RESET}")

    while True:
        print("="*50)
        print("1. Chat (with memory)")
        print("2. Search logs")
        print("3. List sessions")  # ← REPLACED
        print("4. Export session")
        print("5. Set model")
        print("6. Exit")
        print("="*50)

        choice = safe_input("Choose (1-6): ").lower()

        if choice == '1':
            if not current_session:
                resume = safe_input(f"{BCYAN}Resume last? (y/n): {RESET}").lower()
                if resume == 'y':
                    current_session = list_sessions()  # Use edit menu to resume
                if not current_session:
                    current_session = str(uuid.uuid4())
                    print(f"{MAGENTA}New session: {current_session[:8]}...{RESET}")

            print(f"\n{MAGENTA}Session: {get_session_name(current_session) or current_session[:8]}...{RESET}")
            print(f"{BCYAN}Type 'menu' to return, 'new' for new session.\n{RESET}")

            while True:
                prompt = safe_input(f"{BCYAN}You: {RESET}")
                if prompt.lower() == 'menu':
                    break
                if prompt.lower() == 'new':
                    current_session = str(uuid.uuid4())
                    print(f"{MAGENTA}New session: {current_session[:8]}...{RESET}")
                    continue
                if not prompt:
                    continue

                reply, current_session = chat_with_memory(prompt, current_session)
                cleaned_reply = clean_reply(reply)
                print(f"{BGREEN}Ollama:{RESET}\n{cleaned_reply}\n")

        elif choice == '2':
            jumped = search_logs()
            if jumped:
                current_session = jumped
                name = get_session_name(jumped)
                print(f"{BGREEN}Jumped to: {name or jumped[:8]}...{RESET}")

        elif choice == '3':
            current_session = list_sessions() or current_session

        elif choice == '4':
            export_session()

        elif choice == '5':
            set_model_menu()
            
        elif choice == '6':
            print(f"{BYELLOW}Stopping model and exiting...{RESET}")
            stop_ollama_model(MODEL)
            print(f"{BYELLOW}Goodbye!{RESET}")
            sys.exit(0)

        else:
            print(f"{BRED}Invalid choice.{RESET}")

if __name__ == "__main__":
    try:
        ollama.list()
    except Exception as e:
        print(f"{BRED}Ollama not running: {e}{RESET}")
        print(f"{BCYAN}Run: ollama serve{RESET}")
        sys.exit(1)
    main_menu()