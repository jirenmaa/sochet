import tkinter as tk
from tkinter import messagebox

from client.client import Client


class ChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Sochet Client")
        self.client = None
        self.message = messagebox

        # ====== Frame setup ======
        self.login_frame = tk.Frame(root)
        self.chat_frame = tk.Frame(root)

        # ====== Build UI ======
        self.build_login_ui()
        self.build_chat_ui()

        # show login first
        self.login_frame.pack(padx=20, pady=20)

    def build_login_ui(self):
        self.username_var = tk.StringVar(value="admin")
        self.password_var = tk.StringVar(value="admin")

        tk.Label(self.login_frame, text="Username:").pack()
        tk.Entry(self.login_frame, textvariable=self.username_var).pack()

        tk.Label(self.login_frame, text="Password:").pack()
        tk.Entry(self.login_frame, textvariable=self.password_var, show="*").pack()

        tk.Button(self.login_frame, text="Login", command=self.attempt_login).pack(
            pady=10
        )

    def build_chat_ui(self):
        # window to split chat and user list
        paned = tk.PanedWindow(self.chat_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # left: Chat Area
        left_frame = tk.Frame(
            paned, highlightbackground="gray", highlightthickness=1, padx=5, pady=5
        )
        paned.add(left_frame, stretch="always", padx=15, pady=15)

        self.chat_area = tk.Text(
            left_frame,
            state="disabled",
            wrap=tk.WORD,
            borderwidth=5,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="gray",
            font=("Courier", 10),
        )
        self.chat_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.message_entry = tk.Entry(
            left_frame,
            borderwidth=8,
            relief=tk.FLAT,
            highlightthickness=1,
            font=("Courier", 10),
        )
        self.message_entry.pack(fill=tk.X, padx=10, pady=(0, 20))
        self.message_entry.bind("<Return>", self.send_message)

        # right: User list
        right_frame = tk.Frame(paned, width=200, padx=5, pady=5, borderwidth=4)
        paned.add(right_frame)

        # outer frame gives real border
        user_list_wrapper = tk.Frame(
            right_frame, bg="black", highlightbackground="gray", highlightthickness=1
        )
        user_list_wrapper.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.user_listbox = tk.Listbox(
            user_list_wrapper,
            borderwidth=5,  # visually internal padding
            relief=tk.FLAT,
            highlightthickness=0,  # removes focus border
            selectbackground="#aaa",
            font=("Courier", 10),
        )
        self.user_listbox.pack(fill=tk.BOTH, expand=True)

    def update_active_users(self, users: list[str]):
        self.user_listbox.delete(0, tk.END)

        for user in users:
            self.user_listbox.insert(tk.END, user)

    def attempt_login(self):
        username = self.username_var.get()
        password = self.password_var.get()

        if not username or not password:
            self.message.showerror("Error", "Username and password are required")
            return

        self.client = Client(self, username, password)
        msg, error = self.client.connect_to_server()

        if not error:
            self.show_chat_ui()
            self.display_message("✅ Connected to the server!\n")
        else:
            self.message.showerror("Login Failed", msg)

    def show_chat_ui(self):
        """Switch to chat UI after login."""
        self.login_frame.pack_forget()
        self.chat_frame.pack(fill=tk.BOTH)

    def send_message(self, event=None):
        message = self.message_entry.get().strip()
        if not message:
            return

        try:
            # gracefully disconnect the client
            if message.lower() == "/quit":
                # notify server before closing connection
                self.client.write_message(flag="CLIENT_QUIT")
                self.client.disconnect_from_server()

                self.root.quit()
                return

            self.client.write_message(message=message)
            self.message_entry.delete(0, tk.END)
        except ValueError:
            self.message.showerror("Error", "No active client connection found.")

    def display_message(self, message, tag=None):
        self.chat_area.config(state="normal")
        self.chat_area.insert(tk.END, message, tag if tag else ())
        self.chat_area.config(state="disabled")
        self.chat_area.see(tk.END)
