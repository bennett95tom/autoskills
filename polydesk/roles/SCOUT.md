# SCOUT

own:    the list of markets worth pricing today
do:     pull crypto markets from the public Polymarket API; keep barrier,
        strike, FDV and deadline markets with spread and depth
output: board/board.csv (with prices), blind/<slug>.md (without)
stop:   no opinions, never a price inside blind/
