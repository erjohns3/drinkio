FLOW_FAST_MULT = 0.0163
FLOW_FAST_BIAS = 0.813

FLOW_SLOW_MULT = 0.0608
FLOW_SLOW_BIAS = -0.075

def amount_to_flow_ticks(oz_amount):
    if oz_amount >= 1.135:
        return (oz_amount - FLOW_FAST_BIAS) / FLOW_FAST_MULT
    else:
        return (oz_amount - FLOW_SLOW_BIAS) / FLOW_SLOW_MULT
