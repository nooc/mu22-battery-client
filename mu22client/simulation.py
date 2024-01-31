"""
Simulator class that calls API and does some calculations.
"""
from threading import Timer

import numpy as np
import requests as req
from matplotlib.axes import Axes
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

BASE_URL = 'http://127.0.0.1:5000'
TIMER_INTERVAL = 4


class Simulation:
    timer:Timer
    ax:Axes
    canvas:FigureCanvasTkAgg

    def __init__(self, ax:Axes, canvas:FigureCanvasTkAgg):
        self.ax = ax
        self.canvas = canvas
        self.timer = Timer(TIMER_INTERVAL, self.do_timer)
    
    def __get(self, path):
        return req.get(f'{BASE_URL}/').json()
    
    def __post(self, path, data=None):
        return req.post(f'{BASE_URL}/',data=data).json()

    def start(self):
        # reset
        self.__post('/discharge',{'discharging':'on'})
        # get base load
        self.base_load_residential_kwh = self.__get('/baseload')
        # get prices
        self.energy_price = self.__get('/priceperhour')
        # start update 
        self.timer.start()

    def abort(self):
        # stop timer
        self.timer.stop()
        # stop charge
        self.__post('/charge',{'charging':'off'})

    def update(self):
        self.ax.clear()
        t = np.arange(0, 24, 1/15)
        self.ax.plot(t, 2 * np.sin(2 * np.pi * t))
        self.ax.plot(t, 2 * np.cos(2 * np.pi * t))
        self.canvas.draw()


    def do_timer(self):
        info = self.__get('/info')
        sim_min = info['sim_time_hour'] * 60 + info['sim_time_min']
        self.update()

