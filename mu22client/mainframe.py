# -*- coding: utf-8 -*-
#
# MU22 battery client main window UI for the simulation app presenting graphs containing
# simultaion data over 24h.
#
# Copyright 2024, Ben Bright <nooc@users.noreply.github.com>
#
import tkinter as tk
from tkinter.messagebox import showerror

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from mu22client.simulation import Simulation


class ClientFrame:
    """Main window class.
    """

    root:tk.Tk
    start_btn:tk.Button
    abort_btn:tk.Button
    simtype_list:tk.Listbox
    sim:Simulation = None

    def __init__(self):
        """Construct main window.
        """
        # Tk
        self.root = tk.Tk()
        self.root.wm_title("MU22 Battery Client")
        # Tk Canvas
        canvas = FigureCanvasTkAgg(Figure(figsize=(16, 10), dpi=72), master=self.root)
        canvas.get_tk_widget().grid(row = 0, column = 0, columnspan=6)
        # Controls
        self.simtype_list = tk.Listbox(master=self.root, height=2)
        self.simtype_list.grid(row=1, column=1, pady=10)
        self.simtype_list.insert(0,'Load Optimization','Price Optimization')
        self.simtype_list.activate(0)
        self.start_btn = tk.Button(master=self.root, text="START", command=self.start_command)
        self.start_btn.grid(row=1, column=2, pady=10)
        self.abort_btn = tk.Button(master=self.root, text="ABORT", command=self.abort_command, state=tk.DISABLED)
        self.abort_btn.grid(row=1, column=3, pady=10)
        tk.Button(master=self.root, text="QUIT", command=self.quit_command).grid(row=1, column=4, pady=10)
        # Disable resize
        self.root.resizable(False,False)
        # Simulation instance
        try:
            self.sim = Simulation(canvas, end_callback=self.simulation_end_handler)
        except:
             showerror(title="Network error", message="Could not read data.")
             self.quit_command()
        

    def start_command(self):
        sel=self.simtype_list.curselection()
        if not sel: return
        self.start_btn['state'] = tk.DISABLED
        self.abort_btn['state'] = tk.NORMAL
        sel=self.simtype_list.curselection()
        self.sim.start('load' if sel[0]==0 else 'price')

    def abort_command(self):
        self.sim.abort()
        self.start_btn['state'] = tk.NORMAL
        self.abort_btn['state'] = tk.DISABLED

    def quit_command(self):
        if self.sim: self.sim.abort()
        self.root.quit()
        self.root.destroy()
        exit()
    
    def run(self):
        """Run app
        """
        self.root.mainloop()

    def simulation_end_handler_func(self):
        self.start_btn['state'] = tk.NORMAL
        self.abort_btn['state'] = tk.DISABLED
    
    def simulation_end_handler(self):
        self.root.after(100,self.simulation_end_handler_func)
