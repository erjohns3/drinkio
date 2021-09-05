FLOW_FAST_MULT = 0.0163
FLOW_FAST_BIAS = 0.813

FLOW_SLOW_MULT = 0.0608
FLOW_SLOW_BIAS = -0.075


# fill this in
LUT = [
    (-1, 1),
    (-1, 5),
    (-1, 10),
    (-1, 15),
    (-1, 20),
    (-1, 25),
    (-1, 30),
]


def amount_to_flow_ticks(oz_amount):
    if oz_amount >= 1.135:
        return (oz_amount - FLOW_FAST_BIAS) / FLOW_FAST_MULT
    else:
        return (oz_amount - FLOW_SLOW_BIAS) / FLOW_SLOW_MULT
    #for oz_pair, tick_pair in LUT:
    #    if oz_amount == -1:
    #        return max((oz_amount - FLOW_BIAS) / FLOW_MULT, 4)
    #    if oz_amount >= oz_pair:
    #        return tick_pair
    
