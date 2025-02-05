import os
import time
import json
import threading
import logging
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import pyperclip  # Ensure you install with 'pip install pyperclip'
from datetime import datetime

import requests  # Used to check internet connectivity

# --- Import LangChain and Supabase libraries ---
try:
    # from langchain.llms import Ollama
    from langchain_community.llms import Ollama
except ImportError:
    # If the above is not available, create a dummy model class for testing.
    class Ollama:
        def __init__(self, model):
            self.model = model

        def __call__(self, prompt):
            return f"Echo: {prompt}"

from supabase import create_client, Client  # Make sure you install supabase-py

# --- Configuration for Supabase ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://omkmgwdnfjqqjnofbhdt.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9ta21nd2RuZmpxcWpub2ZiaGR0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Mzg3Mzc2NzcsImV4cCI6MjA1NDMxMzY3N30.5943aPvwknpzzKKrHrL2PP6mQSlG8hqI08Z-6Kr-qHw")

try:
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    logging.error("Supabase client initialization error: %s", e)
    supabase_client = None

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    filename='chatbot.log',
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Utility Functions ---

def check_internet_connection() -> bool:
    """Simple check for internet connection by trying to reach a known URL."""
    try:
        requests.get("https://www.google.com", timeout=5)
        return True
    except Exception:
        return False

def append_to_cache(chat_entry: dict, cache_file: str = "chat_cache.json"):
    """Append a chat entry to the local cache (JSON file)."""
    data = []
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
        except Exception as e:
            logging.error("Failed to read cache file: %s", e)
    data.append(chat_entry)
    try:
        with open(cache_file, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logging.error("Failed to write to cache file: %s", e)

def sync_cached_data(cache_file: str = "chat_cache.json"):
    """Attempt to sync cached chat entries to Supabase and clear cache on success."""
    if not os.path.exists(cache_file):
        return
    try:
        with open(cache_file, "r") as f:
            data = json.load(f)
    except Exception as e:
        logging.error("Failed to read cache file: %s", e)
        return

    if not data:
        return

    if check_internet_connection() and supabase_client is not None:
        try:
            for chat in data:
                res = supabase_client.table("chats").insert(chat).execute()
                logging.info("Synced chat: %s", chat)
                logging.info("Supabase response: %s", res)
            # Clear the cache after successful syncing.
            os.remove(cache_file)
        except Exception as e:
            logging.error("Error syncing to Supabase: %s", e)
    else:
        logging.info("Internet not available or Supabase client not initialized; sync deferred.")

# --- Main Application Class ---

class ChatbotApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chatbot Desktop App")
        self.geometry("600x700")
        # Dark mode background for the main window.
        self.configure(bg="#1e1e1e")

        # Initialize UI components.
        self.create_widgets()

        # Initialize the local model via LangChain.
        self.init_local_model()

        # Start a background thread that periodically syncs cached data.
        self.sync_thread = threading.Thread(target=self.periodic_sync, daemon=True)
        self.sync_thread.start()

    def create_widgets(self):
        """Create and layout the widgets."""
        # --- Menu Bar ---
        menubar = tk.Menu(self, bg="#2e2e2e", fg="#ffffff")
        file_menu = tk.Menu(menubar, tearoff=0, bg="#2e2e2e", fg="#ffffff")
        file_menu.add_command(label="Upload PDF/Excel", command=self.upload_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)

        # --- Chat Display Area ---
        self.chat_display = scrolledtext.ScrolledText(
            self, wrap=tk.WORD, state='disabled', font=("Helvetica", 12),
            bg="#2e2e2e", fg="#f8f8f2", insertbackground="#f8f8f2"
        )
        self.chat_display.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Configure tags for formatting text
        self.chat_display.tag_config("user_prefix", font=("Helvetica", 12, "bold"), foreground="#a6e22e")
        self.chat_display.tag_config("user", font=("Helvetica", 12), foreground="#f8f8f2")
        self.chat_display.tag_config("bot_prefix", font=("Helvetica", 12, "bold"), foreground="#66d9ef")
        self.chat_display.tag_config("heading", font=("Helvetica", 12, "bold"), foreground="#f92672")
        self.chat_display.tag_config("code", font=("Courier New", 12), background="#272822", foreground="#e6db74")
        self.chat_display.tag_config("normal", font=("Helvetica", 12), foreground="#f8f8f2")
        # Tags for alignment
        self.chat_display.tag_config("bot_msg", justify="left", lmargin1=10, lmargin2=10)
        self.chat_display.tag_config("user_msg", justify="right", rmargin=10)

        # --- Typing Indicator ---
        self.typing_indicator = tk.Label(self, text="", bg="#1e1e1e", fg="#00ff00",
                                         font=("Helvetica", 10, "italic"))
        self.typing_indicator.pack(pady=(0, 5))

        # --- Input Frame ---
        self.input_frame = ttk.Frame(self)
        self.input_frame.pack(padx=10, pady=10, fill=tk.X)

        # Apply dark theme to ttk widgets.
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", background="#3e3e3e", foreground="#ffffff")
        style.configure("TFrame", background="#1e1e1e")
        style.configure("TEntry", fieldbackground="#2e2e2e", foreground="#f8f8f2")

        # Text widget for multi-line user input.
        self.user_input = tk.Text(self.input_frame, height=3, font=("Helvetica", 12),
                                  bg="#2e2e2e", fg="#f8f8f2", insertbackground="#f8f8f2")
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        # Send button.
        self.send_button = ttk.Button(self.input_frame, text="Send", command=self.on_send)
        self.send_button.pack(side=tk.RIGHT)

    def init_local_model(self):
        """Initialize the local language model using LangChain."""
        try:
            # Adjust the model name and parameters as required.
            self.llm = Ollama(model="deepseek-r1:1.5b")
        except Exception as e:
            logging.error("Failed to initialize local model: %s", e)
            messagebox.showerror("Error", "Failed to initialize local model.")
            self.llm = None

    def periodic_sync(self):
        """Periodically check for an internet connection and sync cached data."""
        while True:
            if check_internet_connection():
                sync_cached_data()
            time.sleep(60)  # Sync every 60 seconds

    def show_typing_indicator(self):
        """Display the typing indicator."""
        self.typing_indicator.config(text="Personel AI is typing...")

    def hide_typing_indicator(self):
        """Hide the typing indicator."""
        self.typing_indicator.config(text="")

    def copy_to_clipboard(self, text):
        pyperclip.copy(text)
        print("Code copied to clipboard!")  # You can replace this with a UI notification

    def on_send(self):
        """Handle sending of a user message."""
        user_text = self.user_input.get("1.0", tk.END).strip()
        if not user_text:
            return
        # Display user's message as "Me" (aligned left)
        self.display_message("User", user_text)
        self.user_input.delete("1.0", tk.END)
        # Show typing indicator and process model response in a separate thread.
        self.show_typing_indicator()
        threading.Thread(target=self.get_bot_response, args=(user_text,), daemon=True).start()

    def parse_markdown(self, message: str):
        """
        Parse the message for simple markdown formatting.
        Splits the message by triple backticks (```) to separate code blocks.
        For non-code parts, each line starting with '#' is treated as a heading.
        Returns a list of segments as dictionaries with keys:
            - type: "text" or "code"
            - content: the text content
            - (for text segments) tag: "heading" or "normal"
        """
        segments = []
        parts = message.split("```")
        for i, part in enumerate(parts):
            if i % 2 == 0:  # Non-code text
                lines = part.splitlines(keepends=True)
                for line in lines:
                    if line.lstrip().startswith("#"):
                        segments.append({"type": "text", "tag": "heading", "content": line})
                    else:
                        segments.append({"type": "text", "tag": "normal", "content": line})
            else:
                # Code block
                segments.append({"type": "code", "content": part})
        return segments

    def display_message(self, sender: str, message: str):
        """Display a message in the chat display area with formatting and alignment."""
        self.chat_display.configure(state='normal')
        # Create a frame for the message bubble
        message_frame = tk.Frame(self.chat_display, padx=10, pady=5)
        if sender == "User":
            # Display as "Me" for user messages (aligned left)
            display_prefix = "Me"
            self.chat_display.insert(tk.END, f"{display_prefix}: ", ("user_prefix", "user_msg"))
            self.chat_display.insert(tk.END, f"{message}\n", ("user", "user_msg"))
            message_frame.configure(bg="#0078FF")  # Blue bubble for user
            anchor = "e"  # Align to the right
        elif sender == "Bot":
            # Display as "Personel AI" for bot messages (aligned right)
            display_prefix = "Personel AI"
            self.chat_display.insert(tk.END, f"{display_prefix}:\n", ("bot_prefix", "bot_msg"))
            message_frame.configure(bg="#E5E5EA")  # Light gray bubble for bot
            anchor = "w"
            # Process message for markdown formatting.
            segments = self.parse_markdown(message)
            for segment in segments:
                if segment["type"] == "text":
                    self.chat_display.insert(tk.END, segment["content"], (segment["tag"], "bot_msg"))
                elif segment["type"] == "code":
                    # Insert the code block with code styling.
                    self.chat_display.insert(tk.END, segment["content"] + "\n", ("code", "bot_msg"))
                    # Insert a copy button right after the code block.
                    copy_btn = tk.Button(self.chat_display, text="Copy",
                                         command=lambda code=segment["content"]: self.copy_to_clipboard(code),
                                         bg="#3e3e3e", fg="#ffffff", relief="flat", padx=5, pady=2)
                    self.chat_display.window_create(tk.END, window=copy_btn)
                    self.chat_display.insert(tk.END, "\n", "bot_msg")
        self.chat_display.insert(tk.END, "\n", "")  # Ensure a newline between messages
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)

    def get_bot_response(self, user_text: str):
        """Query the local model for a response and handle saving."""
        if self.llm is None:
            bot_response = "Local model not available."
        else:
            try:
                # Query the local model via LangChain.
                bot_response = self.llm(user_text)
            except Exception as e:
                logging.error("Error during model inference: %s", e)
                bot_response = "Error: Unable to get response from local model."

        # Update the UI with the bot's response on the main thread.
        self.after(0, lambda: self.display_message("Bot", bot_response))
        self.after(0, self.hide_typing_indicator)

        # Create a chat entry to be saved.
        timestamp = datetime.fromtimestamp(time.time()).isoformat()
        chat_entry = {
            "user_message": user_text,
            "bot_response": bot_response,
            "timestamp": timestamp,
        }
        print("printing", timestamp)

        # Attempt to save to Supabase if online; otherwise, append to local cache.
        if check_internet_connection() and supabase_client is not None:
            try:
                res = supabase_client.table("chats").insert(chat_entry).execute()
                logging.info("Chat saved to Supabase. Response: %s", res)
            except Exception as e:
                logging.error("Failed to save chat to Supabase: %s", e)
                append_to_cache(chat_entry)
        else:
            append_to_cache(chat_entry)

    def upload_file(self):
        """Open a file dialog to select a PDF or Excel file for processing."""
        file_path = filedialog.askopenfilename(
            filetypes=[("PDF files", "*.pdf"), ("Excel files", "*.xlsx;*.xls")]
        )
        if file_path:
            threading.Thread(target=self.process_file, args=(file_path,), daemon=True).start()

    def process_file(self, file_path: str):
        """
        Process the uploaded file (PDF/Excel) to extract text,
        compute embeddings, and store them in Supabase.
        (This is a placeholder function; integrate your parsing/embedding logic here.)
        """
        try:
            logging.info("Processing file: %s", file_path)
            # TODO: Implement text extraction from the file.
            # For example:
            #   text = extract_text_from_file(file_path)
            #   from langchain.embeddings import OpenAIEmbeddings
            #   embeddings = OpenAIEmbeddings()
            #   embedding_vector = embeddings.embed_query(text)
            #   Save embedding_vector to Supabase (e.g., in a "vectors" table).

            # For now, just show an info message.
            messagebox.showinfo("File Upload", "File processed and embeddings saved.")
        except Exception as e:
            logging.error("Error processing file: %s", e)
            messagebox.showerror("File Upload Error", f"Error processing file: {e}")

# --- Run the Application ---
if __name__ == "__main__":
    app = ChatbotApp()
    app.mainloop()
