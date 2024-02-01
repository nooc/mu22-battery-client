# -*- coding: utf-8 -*-
#
# MU22 battery client simulator class that calls API and does some calculations.
#
# Copyright 2024, Ben Bright <nooc@users.noreply.github.com>
#
from math import ceil
from threading import Thread
import time
import tkinter
from typing import Callable, Literal
from matplotlib.figure import Figure

import numpy as np
import requests as req
from matplotlib.axes import Axes
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from mu22client.models import ChargingError, ChargingInfo, FloatList

BASE_URL = 'http://127.0.0.1:5000'
UPDATE_INTERVAL = 1.5

CHARGING_POWER_KW = 7.4
EV_TARGET_CHARGE_RATIO = 0.8
EV_MAX_CAPACITY = 46.3

class Simulation:
    worker:Thread
    running:bool
    soc_graph:Axes
    state_graph:Axes
    canvas:FigureCanvasTkAgg
    fig:Figure

    base_load_residential_kwh:FloatList
    energy_price:FloatList
    sim_type:Literal['price','load']

    x_val:list[float]
    y_val:list[float]

    end_callback:Callable

    def __init__(self, canvas:FigureCanvasTkAgg, end_callback:Callable=None):
        self.end_callback = end_callback
        self.worker = Thread(target=self.do_timer)
        self.running = False
        self.canvas = canvas
        self.fig = canvas.figure
        self.fig.set(constrained_layout=True)
        ax1:Axes = self.fig.add_subplot(411)
        ax2:Axes = self.fig.add_subplot(412)
        self.soc_graph = self.fig.add_subplot(413)
        self.state_graph = self.fig.add_subplot(414)

        # config graphs
        self.x_lim = {'left':0, 'right':24} # 24h window
        self.y_lim_soc = {'bottom':0, 'top':110} # 0-100%
        x_range = range(0,25)
        x_tick = {
            'ticks': x_range,
            'labels': [f'{t}h' for t in x_range]
        }

        ax1.set_xlim(**self.x_lim)
        ax1.set_xticks(**x_tick)
        ax1.set_title("Energy Price")
        ax1.set_ylabel('1e-2 SEK/kWh')
        ax2.set_xlabel('Hour of day')
        
        ax2.set_xlim(**self.x_lim)
        ax2.set_xticks(**x_tick)
        ax2.set_title("Residential Base Load in kWh")
        ax2.set_ylabel('kWh')

        self.state_graph.set_xlim(**self.x_lim)
        self.state_graph.set_xticks(**x_tick)
        self.state_graph.set_title("Optimized charging schedule.")
        self.state_graph.set_ylabel('State')
        self.state_graph.set_yticks(ticks=[0,1], labels=['off','on'])

        self.soc_graph.set_xlim(**self.x_lim)
        self.soc_graph.set_ylim(**self.y_lim_soc)
        self.soc_graph.set_xticks(**x_tick)
        self.soc_graph.set_title("Charging")
        self.soc_graph.set_ylabel('SOC %')
        
        # get base load
        self.base_load_residential_kwh = self.__get('/baseload')
        ax2.stairs(self.base_load_residential_kwh)
        # get prices
        self.energy_price = self.__get('/priceperhour')
        ax1.stairs(self.energy_price)

        self.canvas.draw()
    
    def __get(self, path, return_type=None):
        return self.__parse(req.get(f'{BASE_URL}/{path}').json(),return_type)
    
    def __post(self, path, data, return_type=None):
        return self.__parse(req.post(f'{BASE_URL}/{path}',json=data).json(),return_type)
    
    def __parse(self, data, return_type):
        if return_type:
            try:
                return return_type(**data)
            except: pass
            try:
                return ChargingError(**data)
            except: pass
        return data

    def start(self, type:Literal['price','load']):
        self.sim_type = type
        if type=='price': self.soc_graph.set_title("Charging based on price.")
        elif type=='load': self.soc_graph.set_title("Charging based on load.")
        self.x_val = []
        self.y_val = []
        # start update 
        self.worker.start()

    def abort(self):
        # stop timer
        self.running = False
        if self.worker.is_alive(): self.worker.join()
        # stop charge
        self.__post('/charge',{'charging':'off'})

    def __get_required_charging_time(self, current_capacity) -> int:
        return int((EV_MAX_CAPACITY - current_capacity) / CHARGING_POWER_KW)
    
    def calculate_minimal_load_hours(self, info:ChargingInfo) -> list[bool]:
        """
        TODO: Get best hours for minimizing load on system.
        """
        # Hours needed to charge. Round up to even hours, N.
        hours_needed = self.__get_required_charging_time(info.battery_capacity_kWh)
        # Read base load into a list of (hour index,base load) tuples and sort over base load. 
        sorted_load = []
        for i in range(0,24):
            sorted_load.append((i,self.base_load_residential_kwh[i]))
        sorted_load.sort(key=lambda e: e[1])
        # Construct list of hours-of-day (based on index) and the charging state.
        # Pick the first N hours from the sorted list and enable those indexes. 
        hourly_state = [False]*24
        for i in range(0,hours_needed):
            hourly_state[sorted_load[i][0]] = True
        # Now we have our hourly charging states for the N minimal base load hours.
        return hourly_state

    def calculate_minimal_price_hours(self, info:ChargingInfo) -> list[bool]:
        """
        TODO: Get best hours for minimizing charging price.
        """
        # Hours needed to charge. Round up to even hours, N.
        hours_needed = self.__get_required_charging_time(info.battery_capacity_kWh)
        # Read prices into a list of (hour index,price) tuples and sort over price. 
        sorted_price = []
        for i in range(0,24):
            sorted_price.append((i,self.energy_price[i]))
        sorted_price.sort(key=lambda e: e[1])
        # Construct list of hours-of-day (based on index) and the charging state.
        # Pick the first N hours from the sorted list and enable those indexes. 
        hourly_state = [False]*24
        for i in range(0,hours_needed):
            hourly_state[sorted_price[i][0]] = True
        # Now we have our hourly charging states for the N minimal base load hours.
        return hourly_state

    def do_timer(self):
        # setup
        target_kWh = EV_MAX_CAPACITY * EV_TARGET_CHARGE_RATIO
        # state
        charging = False
        self.running = True
        last_sim_hour = 0.0
        # reset
        self.__post('/discharge',{'discharging':'on'})
        info:ChargingInfo = self.__get('/info',ChargingInfo)
        # charging hours based on simulation type
        if self.sim_type=='price':
            self.state_graph.set_title("Schedule optimized based on price.")
            charging_hours=self.calculate_minimal_price_hours(info)
        else:
            self.state_graph.set_title("Schedule optimized based on load.")
            charging_hours=self.calculate_minimal_load_hours(info)
        self.state_graph.stairs(charging_hours)
        # loop
        t = time.time()
        while self.running:
            if time.time() >= t:
                t += UPDATE_INTERVAL
                # get state
                info = self.__get('/info',ChargingInfo)
                # time to decimal hours
                sim_hour = info.sim_time_hour + info.sim_time_min/60
                if sim_hour > 24 or sim_hour < last_sim_hour:
                    sim_hour = 24 # do this to plot last value
                else: last_sim_hour = sim_hour
                # check soc
                if charging and (info.battery_capacity_kWh >= target_kWh or not charging_hours[info.sim_time_hour]):
                    charging = False
                    self.__post('/charge',{'charging':'off'})
                elif not charging and info.battery_capacity_kWh < target_kWh and charging_hours[info.sim_time_hour]:
                    charging = True
                    self.__post('/charge',{'charging':'on'})
                self.x_val.append(sim_hour)
                self.y_val.append(100*info.battery_capacity_kWh / EV_MAX_CAPACITY)
                self.soc_graph.cla()
                self.soc_graph.plot(self.x_val, self.y_val)
                self.soc_graph.set_xlim(**self.x_lim)
                self.soc_graph.set_ylim(**self.y_lim_soc)
                self.canvas.draw()
                if sim_hour >= 24: break
            sleep_time = t-time.time()
            if sleep_time>0: time.sleep(sleep_time)
        # while
        self.running = False
        if self.end_callback: self.end_callback()



