# -*- coding: utf-8 -*-
#
# MU22 battery client simulator class that calls API and does some calculations.
#
# Copyright 2024, Ben Bright <nooc@users.noreply.github.com>
#
import time
from threading import Lock, Thread
from typing import Callable, Literal

import requests as req
from matplotlib.axes import Axes
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from mu22client.models import ChargingError, ChargingInfo, FloatList

BASE_URL = 'http://127.0.0.1:5000'
SLEEP_TIME = 0.2

MAX_LOAD_KW = 11
CHARGING_POWER_KW = 7.4
EV_TARGET_CHARGE_RATIO = 0.79
EV_MAX_CAPACITY = 46.3

class Simulation:
    lock = Lock()
    worker:Thread = None
    running:bool
    soc_graph:Axes
    state_graph:Axes
    canvas:FigureCanvasTkAgg
    fig:Figure

    base_load_residential_kwh:FloatList
    energy_price:FloatList
    sim_type:Literal['price','load']

    x_hour:list[float]
    y_soc:list[float]
    y_load:list[float]

    end_callback:Callable

    def __init__(self, canvas:FigureCanvasTkAgg, end_callback:Callable=None):
        self.end_callback = end_callback
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
        self.x_hour = []
        self.y_soc = []
        # start update 
        self.worker = Thread(target=self.do_timer)
        self.worker.start()

    def abort(self):
        # stop timer
        with self.lock:
            self.running = False
        while self.worker:
            time.sleep(SLEEP_TIME)

    def __get_required_charging_time(self, current_capacity) -> int:
        """Return te time needed to charge battery at CHARGING_POWER_KW.

        Args:
            current_capacity (float): Current battery capacity.

        Returns:
            int: hours
        """
        return int((EV_MAX_CAPACITY - current_capacity) / CHARGING_POWER_KW)
    
    def __can_charge_less_than_max_power(self, hour_of_day:int) -> bool:
        """Return true if charging at CHARGING_POWER_KW is within allowed output capacity
        based on the base load profile.

        Args:
            hour_of_day (int): Hour (0-23)

        Returns:
            bool: true or false
        """
        return MAX_LOAD_KW > (self.base_load_residential_kwh[hour_of_day] + CHARGING_POWER_KW)
    
    def calculate_minimal_load_hours(self, info:ChargingInfo) -> list[bool]:
        """Get charging hours for minimizing load on system.

        Args:
            info (ChargingInfo): Current state

        Returns:
            list[bool]: Hours-of-day on/off schedule.
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
            hour_of_day,_ = sorted_load[i]
            hourly_state[hour_of_day] = self.__can_charge_less_than_max_power(hour_of_day)
        # Now we have our hourly charging states for the N minimal base load hours.
        return hourly_state

    def calculate_minimal_price_hours(self, info:ChargingInfo) -> list[bool]:
        """Get charging hours for minimizing charging price.

        Args:
            info (ChargingInfo): Current state

        Returns:
            list[bool]: Hours-of-day on/off schedule.
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
            hour_of_day,_ = sorted_price[i]
            hourly_state[hour_of_day] = self.__can_charge_less_than_max_power(hour_of_day)
        # Now we have our hourly charging states for the N minimal base load hours.
        return hourly_state

    def do_timer(self):
        """Simulation thread function.
        Gets data, does calculations and updated graph.
        """
        self.running = True
        # setup
        target_kWh = EV_MAX_CAPACITY * EV_TARGET_CHARGE_RATIO
        # state
        charging = False
        last_sim_hour = 0
        #initial value: 20%
        self.x_hour = [0]
        self.y_soc = [20]
        # reset
        self.__post('/discharge',{'discharging':'on'})
        info:ChargingInfo = self.__get('/info',ChargingInfo)
        self.y_load = [100*info.base_current_load/MAX_LOAD_KW]
        # charging schedule based on simulation type
        if self.sim_type=='price':
            self.state_graph.set_title("Schedule optimized based on price.")
            charging_hours=self.calculate_minimal_price_hours(info)
        else:
            self.state_graph.set_title("Schedule optimized based on load.")
            charging_hours=self.calculate_minimal_load_hours(info)
        self.state_graph.stairs(charging_hours)
        # loop
        while True:
            with self.lock:
                if not self.running: break
            # get state
            info = self.__get('/info',ChargingInfo)

            # time to decimal hours
            if info.sim_time_hour < last_sim_hour:
                info.sim_time_hour = 24 # do this to plot last value
            else: last_sim_hour = info.sim_time_hour
            indexed_hour = info.sim_time_hour if info.sim_time_hour!=24 else 23

            # adjust charging based on soc and schedule
            if charging and (info.battery_capacity_kWh >= target_kWh or not charging_hours[indexed_hour]):
                charging = False
                self.__post('/charge',{'charging':'off'})
            elif not charging and info.battery_capacity_kWh < target_kWh and charging_hours[indexed_hour]:
                charging = True
                self.__post('/charge',{'charging':'on'})

            # append simulation data to graph
            self.x_hour.append(info.sim_time_hour + info.sim_time_min/60)

            curr_sock = 100*info.battery_capacity_kWh / EV_MAX_CAPACITY
            self.y_soc.append(curr_sock)

            curr_load = 100*(self.base_load_residential_kwh[indexed_hour] + 
                             (CHARGING_POWER_KW if charging else 0)) / MAX_LOAD_KW
            self.y_load.append(curr_load)

            # draw
            self.soc_graph.cla()
            self.soc_graph.plot(self.x_hour, self.y_soc, label=f'Current SOC: {int(curr_sock)} %')
            self.soc_graph.plot(self.x_hour, self.y_load, label=f'Current Load: {int(curr_load)} %')
            self.soc_graph.set_title("State")
            self.soc_graph.set_ylabel('Percent (%)')
            self.soc_graph.legend(loc='upper left')
            self.soc_graph.set_xlim(**self.x_lim)
            self.soc_graph.set_ylim(**self.y_lim_soc)
            self.canvas.draw()
            # end of sim?
            if info.sim_time_hour == 24: break
            else: time.sleep(SLEEP_TIME)
        # exit
        if charging:
            self.__post('/charge',{'charging':'off'})
        with self.lock:
            self.running = False
        self.worker = None
        if self.end_callback: self.end_callback()
