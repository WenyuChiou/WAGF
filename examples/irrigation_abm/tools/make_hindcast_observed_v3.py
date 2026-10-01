"""Build examples/irrigation_abm/data/hindcast_observed_v3.csv (one-off data generator, like build_v3_data.py).

Rows: calendar years 1999-2018. Reservoir columns are END-OF-DECEMBER values of that year, i.e. the
1 January state of the following year (the 1999 row is the 1 January 2000 initial state). Flow
columns are calendar-year volumes of that year.

Sources (full list, units and queries in hindcast_observed_v3_sources.csv):
  * Lake Mead end-of-December elevation: USBR Lower Colorado Region, "Lake Mead at Hoover Dam, End of
    Month Elevation (Feet)", https://www.usbr.gov/lc/region/g4000/hourly/mead-elv.html (December column).
  * Lake Mead reported live storage, Lake Powell elevation and live storage: USBR RISE daily values
    dated 31 December, items 6124, 508 and 509 (https://data.usbr.gov/rise/api/result).
  * Glen Canyon release: USGS 09380000 (Colorado River at Lees Ferry) calendar-year mean discharge,
    approved (https://api.waterdata.usgs.gov/statistics/v0/observationIntervals, interval_type=CY),
    x days x 86400 / 43560.
  * Natural flow at Lees Ferry, intervening natural flow to below Hoover, and the nine Upper Basin
    sub-basin flows Q_s and supplies A_s = c_s x Q_s: USBR NaturalFlows1906-2020_20221215.xlsx
    (sha256 b586fa1a...), sheet AnnualCYTotalNaturalFlow, computed with the SAME build_v3_data.py
    functions and rounding as the committed hydrology_v3.csv / ub_subbasin_supply_v3.csv.

The reservoir and release values were retrieved 2026-09-29 from the services above and are
embedded here verbatim, so this script documents and reproduces the CSV byte for byte; re-query the
services to refresh them.

Usage:
    python examples/irrigation_abm/tools/make_hindcast_observed_v3.py --source-xlsx <NaturalFlows xlsx> \
        --crss-db ref/CRSS_DB/CRSS_DB --out examples/irrigation_abm/data/hindcast_observed_v3.csv
"""
from __future__ import annotations

import argparse
import hashlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_v3_data as bvd  # noqa: E402  (same folder: examples/irrigation_abm/tools/)

YEARS = range(1999, 2019)
# year: (Mead EOM Dec elevation ft [LC table], Mead live af [RISE 6124], Powell elevation ft [RISE 508],
#        Powell live af [RISE 509])
RESERVOIR = {
    1999: (1213.94, 24996800, 3681.27, 21443600), 2000: (1196.12, 22358200, 3669.89, 19823200),
    2001: (1177.37, 19795500, 3656.17, 17996000), 2002: (1152.13, 16717700, 3620.10, 13773800),
    2003: (1139.12, 15299600, 3597.22, 11486800), 2004: (1130.01, 14355000, 3564.42, 8663620),
    2005: (1137.52, 15131100, 3598.17, 11576300), 2006: (1128.12, 14164100, 3603.39, 12076500),
    2007: (1114.81, 12859800, 3594.64, 11245800), 2008: (1110.97, 12496200, 3617.89, 13540900),
    2009: (1096.30, 11162400, 3626.22, 14433800), 2010: (1086.30, 10301200, 3626.54, 14469000),
    2011: (1132.83, 14643700, 3639.75, 15973600), 2012: (1120.36, 13636500, 3609.82, 12712500),
    2013: (1106.73, 12344400, 3584.43, 10323800), 2014: (1087.79, 10667000, 3597.75, 11536700),
    2015: (1080.91, 10086500, 3600.80, 11826600), 2016: (1080.82, 10079000, 3600.49, 11796900),
    2017: (1082.52, 10220900, 3622.85, 14067600), 2018: (1081.46, 10132300, 3581.85, 10098900),
}
# USGS 09380000 calendar-year mean discharge, ft^3/s (approved)
LEES_FERRY_CFS = {
    1999: 16401.918, 2000: 11923.224, 2001: 11175.562, 2002: 10928.493, 2003: 11554.767, 2004: 11789.18,
    2005: 11644.712, 2006: 11985.178, 2007: 11555.479, 2008: 12830.191, 2009: 11692.767, 2010: 11535.726,
    2011: 19125.753, 2012: 11362.377, 2013: 11058.904, 2014: 11142.685, 2015: 12319.342, 2016: 12864.645,
    2017: 12239.918, 2018: 12755.534,
}
AF_PER_CFS_DAY = 86400.0 / 43560.0


def _days(y: int) -> int:
    return 366 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 365


def build_csv(source_xlsx: Path, crss_db: Path) -> bytes:
    envelope, flow = bvd.compute_ub_subbasin_envelope(source_xlsx, crss_db)  # both files sha256-checked
    header = ["year", "mead_elev_ft_eoy", "mead_live_af_eoy_usbr", "powell_elev_ft_eoy", "powell_live_af_eoy",
              "lees_ferry_release_af", "lees_ferry_natural_af", "intervening_natural_af"]
    for s in bvd.UB_SUBBASINS:
        header += [f"q_{s}_af", f"a_{s}_af"]
    buf = io.StringIO()
    buf.write(",".join(header) + "\n")
    for y in YEARS:
        m_ft, m_af, p_ft, p_af = RESERVOIR[y]
        lf = int(round(float(flow.loc[y, "09380000"])))
        hv = int(round(float(flow.loc[y, "09421500"])))
        rel = int(round(LEES_FERRY_CFS[y] * _days(y) * AF_PER_CFS_DAY))
        row = [str(y), f"{m_ft:.2f}", str(m_af), f"{p_ft:.2f}", str(p_af), str(rel), str(lf), str(hv - lf)]
        for s in bvd.UB_SUBBASINS:
            q = bvd._subbasin_flow_af(flow, s, y)
            row += [str(int(round(q))), str(int(round(envelope[s]["c_s"] * q)))]
        buf.write(",".join(row) + "\n")
    return buf.getvalue().encode("utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source-xlsx", required=True, type=Path)
    ap.add_argument("--crss-db", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    data = build_csv(a.source_xlsx, a.crss_db)
    a.out.write_bytes(data)
    print(f"wrote {a.out} sha256 {hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
