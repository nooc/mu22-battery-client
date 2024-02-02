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

    __root:tk.Tk
    __start_btn:tk.Button
    __abort_btn:tk.Button
    __simtype_list:tk.Listbox
    __sim:Simulation = None

    def __init__(self):
        """Construct main window.
        """
        # Tk
        self.__root = tk.Tk()
        self.__root.wm_title("MU22 Battery Client")
        # Tk Canvas
        canvas = FigureCanvasTkAgg(Figure(figsize=(16, 10), dpi=72), master=self.__root)
        canvas.get_tk_widget().grid(row = 0, column = 0, columnspan=6)
        # Controls
        self.__simtype_list = tk.Listbox(master=self.__root, height=2)
        self.__simtype_list.grid(row=1, column=1, pady=10)
        self.__simtype_list.insert(0,'Load Optimization','Price Optimization')
        self.__simtype_list.activate(0)
        self.__start_btn = tk.Button(master=self.__root, text="START", command=self.__start_command)
        self.__start_btn.grid(row=1, column=2, pady=10)
        self.__abort_btn = tk.Button(master=self.__root, text="ABORT", command=self.__abort_command, state=tk.DISABLED)
        self.__abort_btn.grid(row=1, column=3, pady=10)
        tk.Button(master=self.__root, text="QUIT", command=self.__quit_command).grid(row=1, column=4, pady=10)
        # Disable resize
        self.__root.resizable(False,False)
        # Simulation instance
        try:
            self.__sim = Simulation(canvas, end_callback=self.__simulation_end_handler)
        except:
             showerror(title="Network error", message="Could not read data.")
             self.__quit_command()
        

    def __start_command(self):
        """Start simulation command
        """
        # Need selection from simuation type.
        sel=self.__simtype_list.curselection()
        if not sel: return
        self.__start_btn['state'] = tk.DISABLED
        self.__abort_btn['state'] = tk.NORMAL
        self.__sim.start('load' if sel[0]==0 else 'price')

    def __abort_command(self):
        """Abort simulation command
        """
        self.__sim.abort()
        self.__start_btn['state'] = tk.NORMAL
        self.__abort_btn['state'] = tk.DISABLED

    def __quit_command(self):
        """Quit app command
        """
        if self.__sim: self.__sim.abort()
        self.__root.quit()
        self.__root.destroy()
        exit()
    
    def __simulation_end_handler_func(self):
        """Delayed callback from main thread.
        """
        self.__start_btn['state'] = tk.NORMAL
        self.__abort_btn['state'] = tk.DISABLED
    
    def __simulation_end_handler(self):
        """Called from simulation thread.
        Schedule '__simulation_end_handler_func' on main thread.
        """
        self.__root.after(100,self.__simulation_end_handler_func)

    def run(self):
        """Run app
        """
        self.__root.mainloop()

__all__ = ('ClientFrame')
