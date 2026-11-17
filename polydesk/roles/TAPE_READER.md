# TAPE READER

own:    what the candles do not show
do:     one live-feed query per asset each morning (Minara is the intended source)
output: evidence/<slug>.md, every line metric | value | source | time
stop:   never gives a probability
missing: any metric not returned -> write "unavailable" on that line.
         The Risk seat then SKIPs any trade that needs it.
