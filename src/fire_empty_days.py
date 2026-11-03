"""Rule for IST dates on which the FIRMS file holds no detection at all (decision G1 in the plan).

Such a date is either cloud (the satellite saw no fire, so zero is plausible) or a satellite / data outage
(no information, so the value must stay missing). Rule, applied to each run of consecutive empty dates:

  zero_assumed  every date of the run is in June to September, the run is 1 or 2 days long, and both the day
                before and the day after the run have fewer than 100 detections in the whole FIRMS box
  outage        anything else (also a run at the edge of the data, where a neighbour is unknown)
  observed      every date that has at least one detection

`totals` is the number of detections (all confidence levels) per IST date, one value per calendar date.
"""
import numpy as np
import pandas as pd

MONSOON_MONTHS = (6, 7, 8, 9)
MAX_CLOUD_RUN_DAYS = 2
NEIGHBOUR_LIMIT = 100


def classify_dates(totals):
    """Status per IST date: 'observed', 'zero_assumed' or 'outage'."""
    totals = totals.sort_index()
    idx = totals.index
    if len(idx) > 1 and not (idx.to_series().diff().dropna() == pd.Timedelta(days=1)).all():
        raise ValueError("totals must have one value for every calendar date")
    empty = totals.eq(0).to_numpy()
    status = pd.Series("observed", index=idx, dtype=object)
    n, i = len(idx), 0
    while i < n:
        if not empty[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and empty[j + 1]:
            j += 1
        prev = totals.iloc[i - 1] if i > 0 else np.nan
        nxt = totals.iloc[j + 1] if j + 1 < n else np.nan
        cloud = ((j - i + 1) <= MAX_CLOUD_RUN_DAYS
                 and all(d.month in MONSOON_MONTHS for d in idx[i:j + 1])
                 and prev < NEIGHBOUR_LIMIT and nxt < NEIGHBOUR_LIMIT)  # a NaN neighbour compares False
        status.iloc[i:j + 1] = "zero_assumed" if cloud else "outage"
        i = j + 1
    return status


def apply_zero_days(df, status, cols, date_col="ist_date"):
    """Copy of `df` with `cols` set to 0 on the 'zero_assumed' dates. Outage dates keep their missing values."""
    out = df.copy()
    zero = out[date_col].map(status).eq("zero_assumed")
    out.loc[zero, list(cols)] = 0
    return out
