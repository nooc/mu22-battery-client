# Battery charging management

## About

The aim of this assignment is to understand how to optimize battery management when developing mobility services.

The client is given control of a simulated EV charging station provided as a REST api written in Python (see *server* foder). The charging station can deliver 7.4 kW.

Using te provided API, the client is required to:

1. Get the price information for grid area 3,Stockholm.
2. Get the information on household energy consumprion over 24h.
3. Send commands to start and stop charging of EV battery. The battery charge shall be read and converted to percent SOC.
4. Charged the battery from 20% to 80% SOC.
5. Show time, total energy usage and how it has optimized charging.


### Part 1

The battery should be charged when the household is using the least amount of energy. 
Total energy consumption < 11kW (3-phase, 16A).

### Part 2

The battery should be charged when the price of electricity is at its lowest.
Total energy consumption < 11kW (3-phase, 16A).

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

