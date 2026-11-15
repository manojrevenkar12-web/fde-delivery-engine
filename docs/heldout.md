# The held-out year

`config/heldout.json` was written before it was run: seed `heldout-2027`, more opportunities (1.1 a week), half of
them public sector, half of the public-sector work air-gapped, more blockers and scope creep, larger overruns, more
planted pipeline defects and a thinner advisory bench (two people instead of three). It ran once, with the code and
settings dev ended on. `config/heldout.lock` records the date and the hash of every config file. The numbers are in
`reports/heldout.json` and in the README.

## What happened

The gate failed on three of its eight lines.

```
FAIL milestones on plan                           0.5682 >= 0.8
pass milestone gain over the baseline, points     49.3 >= 10
pass surprise slips vs the baseline               0.306 <= 0.5
pass weeks above 90% load vs the baseline         0.403 <= 0.5
pass production incidents                         1 <= 1
FAIL utilization at least                         0.6016 >= 0.65
pass utilization at most                          0.6016 <= 0.88
FAIL margin share beats the baseline              -0.1925 > -0.0681
GATE FAILED
```

The engine still beat planning by hand by 49 points of milestones on plan, with a third of the surprise slips, 1
production incident against 8 and no sick weeks against 80. But it declined 35 of 60 opportunities, left 9,536 hours
idle, and with fewer engagements than the by-hand team it still slipped 38 of 88 milestones. Revenue fell below the
cost of the team, so its margin was worse than the baseline's.

Three things went wrong together, all in the planner and intake rather than in the escalation agent or the gate.

1. **Advisory and operating people sat idle while builds slipped.** The planner judged whether someone could do a
   piece of work on this week's expected rate, including the ramp-up of someone new to the engagement. An operating
   engineer covering a build runs at 0.6 of a builder, and 0.42 in their first week, below the 0.6 minimum. So cover
   from an adjacent profile could never start, except in the last week before a date, when it was too late.
2. **Specialists were spent on work anyone could do.** With one German-speaking advisor and one German-speaking
   operating engineer, the planner could put them on work that needed no German while German work waited.
3. **Intake declined on a forecast that the planner could not meet.** Because of 1 and 2, the team delivered less
   than its capacity, the forecast filled up, and intake said no to work the team could have done.
