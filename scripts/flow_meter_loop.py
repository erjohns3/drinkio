flow_callback.reset_tally()
pi.set_PWM_dutycycle(PUMP_PIN, 50)
pump_start = False
elapsed = 0

while True:
    if await check_cancel(): return

    if flow_callback.tally() >= 4
        pump_start = time.time()

    if pump_start and time.time() >= pump_start + pump_time:
        break
    
    if elapsed > 16 or (elapsed > 2 and pump_start):
        if flow_callback.tally() < 5:
            print("ingredient empty")
            config_lock.acquire()
            ingredients[ingredient]["empty"] = True
            dump_ingredients_owned_to_file()
            config_lock.release()
            state_lock.acquire()
            await broadcast_config()
            state_lock.release()
            break
        flow_callback.reset_tally()
        elapsed = 0

    if elapsed > 16:
        if flow_tick - flow_prev <= 6:
            
        flow_prev = flow_tick
        elapsed = 8

    elapsed = elapsed + FLOW_PERIOD
    await asyncio.sleep(FLOW_PERIOD)