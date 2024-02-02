# Battery charging management

## About Task

<img align="right" width="300" src="Screenshot.png" /> The aim of this assignment is to understand how to optimize battery management when developing mobility services.

The client is given control of a simulated EV charging station, provided as a REST API and written in Python (see *server* foder). The charging station can deliver 7.4 kW.

Using the API, the client is required to:

1. Get the price information for grid area (in this case area 3, Stockholm).
2. Get the information on household energy consumprion over 24h.
3. Send commands to start and stop charging of EV battery. The battery charge shall be read and converted to percent SOC.
4. Charged the battery from 20% to 80%.
5. Show time, total energy usage and how it has optimized charging.

### Part 1

The battery should be charged when the household is using the least amount of energy. 
Total energy consumption < 11kW.

### Part 2

The battery should be charged when the price of electricity is at its lowest.
Total energy consumption < 11kW.

## The Clilent

The client is written in Python and has a Tk UI. Four graphs are presented in the following order:

* Energy price per hour over 24h.
* Hourly base load of simulated household over 24h.
* Simulation results, one plot for EV battery SOC % and one for tota load % reative to max load of 11kW.
* Charging schedule specifying on/of state for each hour of the day.

There is a list of optimization choices for the simulation:

* Optimize for minimum load
* Optimize for minimum price


## Usage

Make sure you're in repository root:
```
cd <repo-root>
```

Start the server that will listen on **127.0.0.1:5000**:

```
python chargingwebserver-v0-7.py
```

Start the client:

```
python main.py
```

