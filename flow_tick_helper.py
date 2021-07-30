FLOW_BIAS = 0.849
FLOW_MULT = 0.0161


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
    if oz_amount >= 1.4:
        return max((oz_amount - FLOW_BIAS) / FLOW_MULT, 4)
    for oz_pair, tick_pair in LUT:
        if oz_amount == -1:
            return max((oz_amount - FLOW_BIAS) / FLOW_MULT, 4)
        if oz_amount >= oz_pair:
            return tick_pair
    