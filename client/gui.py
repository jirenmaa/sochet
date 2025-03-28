import tkinter as tk
from tkinter import messagebox
from client.client import Client

class ChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Chat Client")

        self.username = tk.StringVar()
        self.password = tk.StringVar()

        tk.Label(root, text="Username:").pack()
        tk.Entry(root, textvariable=self.username).pack()

        tk.Label(root, text="Password:").pack()
        tk.Entry(root, textvariable=self.password).pack()

        self.connect_button = tk.Button(root, text="Connect", command=self.connect)
        self.connect_button.pack(pady=5)

        self.chat_area = tk.Text(root, state='disabled')
        self.chat_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.message_entry = tk.Entry(root)
        self.message_entry.pack(fill=tk.X, padx=10, pady=10)
        self.message_entry.bind("<Return>", self.send_message)

        self.client = None

    def connect(self):
        username = self.username.get()
        password = self.password.get()

        if not username or not password:
            messagebox.showerror("Error", "Username and password are required")
            return

        self.client = Client(self, username, password)
        if self.client.connect():
            self.connect_button.config(state=tk.DISABLED)
            self.display_message("Connected to the server!")
        else:
            messagebox.showerror("Error", "Invalid username or password")

    def send_message(self, event=None):
        message = self.message_entry.get()
        if message:
            self.client.send_message(message)
            self.message_entry.delete(0, tk.END)

    def display_message(self, message):
        self.chat_area.config(state='normal')
        self.chat_area.insert(tk.END, message + "\n")
        self.chat_area.config(state='disabled')
        self.chat_area.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    gui = ChatGUI(root)
    root.mainloop()
