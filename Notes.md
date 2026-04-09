This file contains some notes on how to improve the metric calculation.

There is a "problem" as the example: 
F[0,2](x>0) vs F[0,2](x>0 || y>0)
scores lower than
F[0,2](x>0) vs F[0,2](x>0 && y>0)

This is due to how the volumes are created. 
As of right now the volumes for the OR contains basically two major directions that will end up in this condition:
x>0 && !y>0
!x>0 && y>0 

Maybe we could drop the negated condition and substitute it in a undefined one. 
