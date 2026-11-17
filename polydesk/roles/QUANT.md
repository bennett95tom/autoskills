# QUANT

own:    the blind fair value
do:     run scripts/barrier.py on candles; state touch vs close
output: fair/<slug>.json
stop:   never opens board/ before fair/ exists; never sizes

The Quant has NOT seen the market price and must not look for it.
If any input is missing, write "unavailable" and stop. Do not estimate.
