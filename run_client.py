import tkinter as tk

from client.gui import ChatGUI

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("900x550")
    gui = ChatGUI(root)
    root.mainloop()
