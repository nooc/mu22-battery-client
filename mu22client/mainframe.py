"""
ClientFrame is the main window for the simulation app presenting a graph containing
simultaion state over 24h.
"""
import tkinter as tk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from mu22client.simulation import Simulation


class ClientFrame:
    """Main window class.
    """

    root:tk.Tk
    sim:Simulation

    def __init__(self):
        """Construct main window.
        """
        # Tk
        self.root = tk.Tk()
        self.root.wm_title("MU22 Battery Client")
        # Figure
        fig = Figure(figsize=(16, 4), dpi=72)
        sub = fig.add_subplot()
        # Tk Canvas
        canvas = FigureCanvasTkAgg(fig, master=self.root)
        canvas.get_tk_widget().grid(row = 0, column = 0, columnspan=3)
        # Buttons
        tk.Button(master=self.root, text="START", command=self.start_command).grid(row=1, column=0, pady=10)
        tk.Button(master=self.root, text="ABORT", command=self.abort_command).grid(row=1, column=1, pady=10)
        tk.Button(master=self.root, text="QUIT", command=self.quit_command).grid(row=1, column=2, pady=10)
        # Disable resize
        self.root.resizable(False,False)
        # Simulation instance
        self.sim = Simulation(sub, canvas)

    def start_command(self):
        self.sim.start()

    def abort_command(self):
        self.sim.abort()

    def quit_command(self):
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        """Run app
        """
        self.root.mainloop()
