# Is 1 − G a metric?

Triangle inequality d(a,c) ≤ d(a,b) + d(b,c), d = 1 − G, on every ordered triple of distinct candidates within each RQ4 context: **43142 violations out of 62486772 triples (0.0690%)**.

| case | context | triples | violations |
|---|---|---|---|
| WaterTanks | TankEmptying_OpenValve | 91080 | 30 |
| Heater | threshold_heater_off | 210 | 0 |
| Heater | threshold_heateron | 60 | 0 |
| Gearbox | theta_increasing | 551286 | 320 |
| Gearbox | threshold_gear4 | 551286 | 142 |
| ControlledPU | Transmission gear 4 | 4410780 | 5104 |
| ControlledPU | speed increasing | 6229320 | 3390 |
| EngineTiming | EngineSpeed | 120 | 0 |
| FuelControl | EngineSpeed | 50652630 | 34156 |

Worst violation: d(a,c) = 0.4848 > d(a,b) + d(b,c) = 0.1818 + 0.1818 = 0.3636

- a = `F[0,0]((fuel >= 1.118445) && (fuel <= 1.533941)) && F[4,10]((map >= 0.549475) && (map <= 0.727315)) -> F[4,10]((air_fuel_ratio > 10.000000))`
- b = `F[0,0]((throttle >= 12.250000) && (throttle <= 12.950000)) && F[0,0]((ego == 1.000000)) -> F[4,10]((air_fuel_ratio > 10.000000))`
- c = `F[0,0]((map >= 0.514331) && (map <= 0.709944)) && F[4,10]((fuel >= 1.215924) && (fuel <= 1.409387)) -> F[4,10]((air_fuel_ratio > 10.000000))`

So G is a similarity measure whose complement is a semimetric (symmetric, zero exactly on equivalent formulas) but not a metric.
