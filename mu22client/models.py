# -*- coding: utf-8 -*-
#
# MU22 battery client models.
#
# Copyright 2024, Ben Bright <nooc@users.noreply.github.com>
#
from typing import Literal

from pydantic import BaseModel


class ChargingInfo(BaseModel):
    
    sim_time_hour:int
    sim_time_min:int
    base_current_load:float
    battery_capacity_kWh:float

class FloatList(list[float]):
    pass

class ChargingState(BaseModel):
    charging:Literal['on','off']

class ChargingError(BaseModel):
    error:str


__all__ = ('ChargingInfo', 'FloatList', 'ChargingState', 'ChargingError')
