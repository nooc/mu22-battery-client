"""
Simulator class that calls API and does some calculations.
"""
from threading import Thread
import time
from matplotlib.figure import Figure

import numpy as np
import requests as req
from matplotlib.axes import Axes
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

BASE_URL = 'http://127.0.0.1:5000'
TIMER_INTERVAL = 4.0


class Simulation:
    worker:Thread
    running:bool
    ax:Axes
    canvas:FigureCanvasTkAgg
    fig:Figure

    x_val:list[float]
    y_val:list[float]

    def __init__(self, canvas:FigureCanvasTkAgg):
        self.worker = Thread(target=self.do_timer)
        self.running = False
        self.canvas = canvas
        self.fig = canvas.figure
        ax1:Axes = self.fig.add_subplot(311)
        ax2:Axes = self.fig.add_subplot(312)
        self.ax = self.fig.add_subplot(313)
        
        # get base load
        self.base_load_residential_kwh = self.__get('/baseload')
        # get prices
        self.energy_price = self.__get('/priceperhour')
        # update static graphs
        ax1.stairs(self.energy_price)
        ax1.set_title("Energy Price")
        ax2.stairs(self.base_load_residential_kwh)
        ax2.set_title("Residential Base Load in kWh")
        self.ax.set_title("Battery SOC")
        self.fig.tight_layout()
        self.canvas.draw()
    
    def __get(self, path):
        return req.get(f'{BASE_URL}/{path}').json()
    
    def __post(self, path, data=None):
        return req.post(f'{BASE_URL}/{path}',json=data).json()

    def start(self):
        self.x_val = []
        self.y_val = []
        # start update 
        self.worker.start()

    def abort(self):
        # stop timer
        self.running = False
        self.worker.join()
        # stop charge
        self.__post('/charge',{'charging':'off'})

    def do_timer(self):
        '''
        "sim_time_hour":sim_hour,
        "sim_time_min":sim_min,
        "base_current_load":base_current_load,
        "battery_capacity_kWh":ev_batt_capacity_kWh
        '''
        self.running = True
        # reset
        self.__post('/discharge',{'discharging':'on'})
        self.__post('/charge',{'charging':'on'})
        # loop
        t = time.time()
        while self.running:
            if time.time() >= t:
                t += TIMER_INTERVAL
                info = self.__get('/info')
                sim_min = info['sim_time_hour'] + info['sim_time_min']/60
                self.x_val.append(sim_min)
                self.y_val.append(info['battery_capacity_kWh'])
                self.ax.clear()
                self.ax.plot(self.x_val, self.y_val)
                self.canvas.draw()
                time.sleep(t-time.time())


