# -*- coding: utf-8 -*-
#
# MU22 battery client simulator class that calls API and does some calculations.
#
# Copyright 2024, Ben Bright <nooc@users.noreply.github.com>
#
import time
from threading import Thread
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
EV_TARGET_SOC = 0.799
EV_MAX_CAPACITY = 46.3
EV_START_SOC = 0.2

class Simulation:
    __worker:Thread = None
    __do_abort:bool
    __soc_graph:Axes
    __canvas:FigureCanvasTkAgg
    __fig:Figure
    __base_load_residential_kwh:FloatList
    __energy_price:FloatList
    __sim_type:Literal['price','load']
    __end_callback:Callable

    def __init__(self, canvas:FigureCanvasTkAgg, end_callback:Callable=None):
        self.__end_callback = end_callback
        self.__do_abort = False
        self.__canvas = canvas
        self.__fig = canvas.figure
        self.__fig.set(constrained_layout=True)
        ax1:Axes = self.__fig.add_subplot(311)
        ax2:Axes = self.__fig.add_subplot(312)
        self.__soc_graph = self.__fig.add_subplot(313)

        # config graphs
        self.__x_lim = {'left':0, 'right':24} # 24h window
        self.__y_lim_soc = {'bottom':0, 'top':110} # 0-100%
        x_range = range(0,25)
        self.__x_tick = {
            'ticks': x_range,
            'labels': [f'{t}h' for t in x_range]
        }

        ax1.set_xlim(**self.__x_lim)
        ax1.set_xticks(**self.__x_tick)
        ax1.set_title("Energy Price")
        ax1.set_ylabel('1e-2 SEK/kWh')
        ax2.set_xlabel('Hour of day')
        
        ax2.set_xlim(**self.__x_lim)
        ax2.set_xticks(**self.__x_tick)
        ax2.set_title("Residential Base Load in kWh")
        ax2.set_ylabel('kWh')

        self.__soc_graph.set_xlim(**self.__x_lim)
        self.__soc_graph.set_ylim(**self.__y_lim_soc)
        self.__soc_graph.set_xticks(**self.__x_tick)
        
        # get base load
        self.__base_load_residential_kwh = self.__get('/baseload')
        ax2.stairs(self.__base_load_residential_kwh)
        # get prices
        self.__energy_price = self.__get('/priceperhour')
        ax1.stairs(self.__energy_price)

        self.__canvas.draw()
    
    def __get(self, path, return_type=None) -> None:
        return self.__parse(req.get(f'{BASE_URL}/{path}').json(),return_type)
    
    def __post(self, path, data, return_type=None):
        return self.__parse(req.post(f'{BASE_URL}/{path}',json=data).json(),return_type)
    
    def __parse(self, data, return_type) -> None:
        if return_type:
            try:
                return return_type(**data)
            except: pass
            try:
                return ChargingError(**data)
            except: pass
        return data

    def start(self, type:Literal['price','load']) -> None:
        self.__do_abort = False
        self.__sim_type = type
        if type=='price': self.__soc_graph.set_title("Charging based on price.")
        elif type=='load': self.__soc_graph.set_title("Charging based on load.")
        # start update 
        self.__worker = Thread(target=self.__do_simuate)
        self.__worker.start()

    def abort(self) -> None:
        # stop
        self.__do_abort = True

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
        return MAX_LOAD_KW > (self.__base_load_residential_kwh[hour_of_day] + CHARGING_POWER_KW)
    
    def __calculate_minimal_load_hours(self, info:ChargingInfo) -> list[bool]:
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
            sorted_load.append((i,self.__base_load_residential_kwh[i]))
        sorted_load.sort(key=lambda e: e[1])
        # Construct list of hours-of-day (based on index) and the charging state.
        # Pick the first N hours from the sorted list and enable those indexes. 
        hourly_state = [False]*24
        for i in range(0,hours_needed):
            hour_of_day,_ = sorted_load[i]
            hourly_state[hour_of_day] = self.__can_charge_less_than_max_power(hour_of_day)
        # Now we have our hourly charging states for the N minimal base load hours.
        return hourly_state

    def __calculate_minimal_price_hours(self, info:ChargingInfo) -> list[bool]:
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
            sorted_price.append((i,self.__energy_price[i]))
        sorted_price.sort(key=lambda e: e[1])
        # Construct list of hours-of-day (based on index) and the charging state.
        # Pick the first N hours from the sorted list and enable those indexes. 
        hourly_state = [False]*24
        for i in range(0,hours_needed):
            hour_of_day,_ = sorted_price[i]
            hourly_state[hour_of_day] = self.__can_charge_less_than_max_power(hour_of_day)
        # Now we have our hourly charging states for the N minimal base load hours.
        return hourly_state

    def __do_simuate(self):
        """Simulation thread function.
        Gets data, does calculations and updated graph.
        """
        # setup
        target_kWh = EV_MAX_CAPACITY * EV_TARGET_SOC
        # state
        charging = False
        last_sim_hour = 0
        #initial value: 20%
        x_hour = [0]
        y_soc = [20]
        # reset
        self.__post('/discharge',{'discharging':'on'})
        info:ChargingInfo = self.__get('/info',ChargingInfo)
        y_load = [100*info.base_current_load/MAX_LOAD_KW]
        # charging schedule based on simulation type
        if self.__sim_type=='price':
            opt_label = "Price optimized schedule."
            charging_hours=self.__calculate_minimal_price_hours(info)
        else:
            opt_label = "Load optimized schedule."
            charging_hours=self.__calculate_minimal_load_hours(info)

        # charging hours states to plot values
        charging_hours_y = [5 if i else 0 for i in charging_hours]
        charging_hours_x = range(0,24)

        start_energy = EV_MAX_CAPACITY*EV_START_SOC

        # loop
        while True:
            if self.__do_abort: break
            # get state
            info = self.__get('/info',ChargingInfo)

            # time
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

            # energy
            total_energy_used = info.battery_capacity_kWh - start_energy
            for i in range(0,info.sim_time_hour):
                total_energy_used += self.__base_load_residential_kwh[i]
            if info.sim_time_hour<24:
                total_energy_used += self.__base_load_residential_kwh[info.sim_time_hour] * (info.sim_time_min/60)

            # append simulation data to graph
            x_hour.append(info.sim_time_hour + info.sim_time_min/60)

            curr_sock = 100*info.battery_capacity_kWh / EV_MAX_CAPACITY
            y_soc.append(curr_sock)

            curr_load = 100*(self.__base_load_residential_kwh[indexed_hour] + 
                             (CHARGING_POWER_KW if charging else 0)) / MAX_LOAD_KW
            y_load.append(curr_load)

            # draw
            if not self.__do_abort:
                try:
                    self.__soc_graph.cla()

                    self.__soc_graph.plot(x_hour, y_soc, label=f'Current SOC: {int(curr_sock)} %')
                    self.__soc_graph.plot(x_hour, y_load, label=f'Current Load: {int(curr_load)} %')
                    self.__soc_graph.bar(charging_hours_x, charging_hours_y, width=1, align='edge', color='g', label=opt_label)

                    self.__soc_graph.set_title("SOC/Load")
                    self.__soc_graph.set_ylabel('Percent (%)')
                    self.__soc_graph.set_xlim(**self.__x_lim)
                    self.__soc_graph.set_ylim(**self.__y_lim_soc)
                    self.__soc_graph.set_xticks(**self.__x_tick)
                    self.__soc_graph.legend(loc='upper left', fancybox=True, framealpha=0.3)
                    self.__soc_graph.text(10, 80, f'Total Energy Used: {int(total_energy_used)} kWh')
                    self.__canvas.draw()
                except:
                    return
            # end of sim?
            if info.sim_time_hour == 24: break
            else: time.sleep(SLEEP_TIME)
        # exit
        if charging:
            self.__post('/charge',{'charging':'off'})
        self.__worker = None
        if self.__end_callback: self.__end_callback()

__all__ = ('Simulation')
