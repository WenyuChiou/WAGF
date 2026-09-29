"""Build the irrigation v3 water-system data files (WP1).

Regenerates two committed, checksum-pinned CSVs under
``examples/irrigation_abm/data/``:

1. ``hydrology_v3.csv`` -- USBR calendar-year naturalized flow at Lees
   Ferry (and the Lees-Ferry-to-below-Hoover intervening flow) for the
   1988-2015 / 1934-1947 resampled years, mapped to simulation years
   2019-2060 exactly as Hung and Yang (2021, p. 15 of 21) resample CRSS's
   default hydrology. Source: U.S. Bureau of Reclamation (2022), Colorado
   River Basin natural flow data,
   ``NaturalFlows1906-2020_20221215.xlsx``, sheet
   ``AnnualCYTotalNaturalFlow``, columns "Colorado R At Lees Ferry, AZ"
   and "Colorado River Below Hoover Dam, AZ-NV".
   https://www.usbr.gov/lc/region/g4000/NaturalFlow/current.html
   (retrieved 2026-09-28). The source file is NOT committed to this repo
   (a large USBR download, not framework or paper data); pass its path
   with ``--source-xlsx``. Its sha256 is verified against
   ``SOURCE_XLSX_SHA256`` before any row is read, and the output CSV's
   sha256 is verified against ``HYDROLOGY_V3_SHA256`` after it is
   written -- both raise on mismatch, so a stale or wrong download can
   never silently produce a different table than the one the spec, the
   tests and the paper cite.

2. ``mead_capacity_usbr2009_1ft.csv`` -- USBR Lake Mead Area and Capacity
   Tables (Tighi and Callejo, 2011, 2001/2009 surveys), available storage
   capacity above 895 ft at 1-ft steps from 895 to 1,229 ft. Source:
   https://www.usbr.gov/lc/region/g4000/LM_AreaCapacityTables2009.pdf
   (retrieved 2026-09-28). This table comes from a scanned/typeset PDF,
   not a machine-readable spreadsheet, so it is not re-derived from the
   PDF programmatically here; ``MEAD_CAPACITY_TABLE_KAF`` below is a
   literal transcription, cross-checked against the nine checkpoints
   quoted independently in both
   ``.research/design_specs/irrigation_v3_design_provenance_2026-09-28.md``
   (row E9) and
   ``.ai/irrigation_prerun_audit_2026-09-28/L2_water_system.md`` (Q3):
   950 ft 2,006; 1,000 ft 4,475; 1,025 ft 5,981; 1,050 ft 7,683;
   1,075 ft 9,601; 1,100 ft 11,735; 1,150 ft 16,733; 1,200 ft 23,144;
   1,220 ft 26,177 kaf -- all nine match exactly. Re-run with
   ``--target mead`` to REBUILD the checked-in CSV from
   ``MEAD_CAPACITY_TABLE_KAF`` and OVERWRITE it (this re-derives the file
   from the literal transcription above, then verifies the freshly
   written bytes against ``MEAD_CAPACITY_SHA256`` -- it does not merely
   check the existing file in place), without touching the hydrology
   table.

Usage::

    python examples/irrigation_abm/tools/build_v3_data.py --source-xlsx <path> [--target all|hydrology|mead]

Never imported by ``irrigation_env.py`` at runtime -- it is a one-off data
generator; the environment loads the checked-in CSVs directly (see
``_load_hydrology_table`` / ``_load_mead_capacity_table`` there) and
raises if either file's sha256 does not match, independent of whether
this script still runs.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
HYDROLOGY_CSV = DATA_DIR / "hydrology_v3.csv"
MEAD_CSV = DATA_DIR / "mead_capacity_usbr2009_1ft.csv"

# sha256 of NaturalFlows1906-2020_20221215.xlsx as retrieved 2026-09-28
# (spec irrigation_v3_spec_2026-09-28.md, WP1 item 1.1).
SOURCE_XLSX_SHA256 = "b586fa1aa4e6e82c7ba0a0dc0184f1b3ac5cfb53c30ef14b248127c12d7fc3cd"
# sha256 of the 42-row, 4-column derived table (this script's output),
# LF line endings (spec WP1 acceptance).
HYDROLOGY_V3_SHA256 = "9951f2224334a859a7adbc9d55914e6505bbce38ea0424f26f10f7c8d51a04b5"
# sha256 of the 335-row Mead capacity CSV this script writes.
MEAD_CAPACITY_SHA256 = "7f233bd8149cc9416612991c27ed130c22842e93bbbbdd121d7716d5f8d9c8d6"

LEES_FERRY_COL = "Colorado R At Lees Ferry, AZ"
BELOW_HOOVER_COL = "Colorado River Below Hoover Dam, AZ-NV"
SHEET_NAME = "AnnualCYTotalNaturalFlow"

# sim_year -> source calendar year (H&Y 2021 p. 15 of 21: 2019-2046 repeats
# 1988-2015, 2047-2060 repeats 1934-1947 -- CRSS's own default resample).
YEAR_MAP = {y: 1988 + (y - 2019) for y in range(2019, 2047)}
YEAR_MAP.update({y: 1934 + (y - 2047) for y in range(2047, 2061)})

# USBR Lake Mead Area and Capacity Tables (Tighi and Callejo, 2011):
# available capacity above 895 ft (kaf), 1-ft steps, 895-1229 ft. Literal
# transcription -- see the module docstring for the cross-check.
MEAD_CAPACITY_TABLE_KAF = {
    895: 0, 896: 30, 897: 61, 898: 91, 899: 122, 900: 153, 901: 185,
    902: 216, 903: 248, 904: 280, 905: 312, 906: 345, 907: 377, 908: 410,
    909: 443, 910: 477, 911: 511, 912: 544, 913: 579, 914: 613, 915: 648,
    916: 683, 917: 718, 918: 753, 919: 789, 920: 824, 921: 860, 922: 897,
    923: 933, 924: 970, 925: 1007, 926: 1044, 927: 1081, 928: 1119,
    929: 1157, 930: 1195, 931: 1233, 932: 1272, 933: 1311, 934: 1350,
    935: 1389, 936: 1428, 937: 1468, 938: 1508, 939: 1548, 940: 1589,
    941: 1629, 942: 1670, 943: 1711, 944: 1753, 945: 1794, 946: 1836,
    947: 1878, 948: 1920, 949: 1963, 950: 2006, 951: 2049, 952: 2092,
    953: 2135, 954: 2179, 955: 2223, 956: 2267, 957: 2312, 958: 2357,
    959: 2402, 960: 2447, 961: 2493, 962: 2539, 963: 2585, 964: 2631,
    965: 2678, 966: 2724, 967: 2771, 968: 2819, 969: 2866, 970: 2914,
    971: 2962, 972: 3010, 973: 3059, 974: 3107, 975: 3156, 976: 3206,
    977: 3255, 978: 3305, 979: 3355, 980: 3406, 981: 3456, 982: 3507,
    983: 3559, 984: 3610, 985: 3662, 986: 3714, 987: 3767, 988: 3819,
    989: 3872, 990: 3926, 991: 3980, 992: 4033, 993: 4088, 994: 4142,
    995: 4197, 996: 4252, 997: 4307, 998: 4363, 999: 4419, 1000: 4475,
    1001: 4532, 1002: 4589, 1003: 4646, 1004: 4703, 1005: 4761, 1006: 4819,
    1007: 4878, 1008: 4936, 1009: 4995, 1010: 5055, 1011: 5114, 1012: 5174,
    1013: 5234, 1014: 5295, 1015: 5356, 1016: 5417, 1017: 5478, 1018: 5540,
    1019: 5602, 1020: 5665, 1021: 5727, 1022: 5790, 1023: 5854, 1024: 5917,
    1025: 5981, 1026: 6045, 1027: 6110, 1028: 6175, 1029: 6240, 1030: 6305,
    1031: 6371, 1032: 6437, 1033: 6504, 1034: 6570, 1035: 6638, 1036: 6705,
    1037: 6773, 1038: 6841, 1039: 6909, 1040: 6978, 1041: 7047, 1042: 7116,
    1043: 7186, 1044: 7256, 1045: 7326, 1046: 7397, 1047: 7468, 1048: 7539,
    1049: 7611, 1050: 7683, 1051: 7755, 1052: 7828, 1053: 7901, 1054: 7975,
    1055: 8048, 1056: 8123, 1057: 8197, 1058: 8272, 1059: 8347, 1060: 8423,
    1061: 8499, 1062: 8575, 1063: 8652, 1064: 8729, 1065: 8807, 1066: 8885,
    1067: 8963, 1068: 9041, 1069: 9120, 1070: 9200, 1071: 9279, 1072: 9359,
    1073: 9439, 1074: 9520, 1075: 9601, 1076: 9682, 1077: 9764, 1078: 9846,
    1079: 9928, 1080: 10011, 1081: 10094, 1082: 10177, 1083: 10261,
    1084: 10345, 1085: 10430, 1086: 10514, 1087: 10600, 1088: 10685,
    1089: 10771, 1090: 10857, 1091: 10944, 1092: 11030, 1093: 11118,
    1094: 11205, 1095: 11293, 1096: 11381, 1097: 11469, 1098: 11557,
    1099: 11646, 1100: 11735, 1101: 11825, 1102: 11914, 1103: 12005,
    1104: 12095, 1105: 12186, 1106: 12277, 1107: 12369, 1108: 12461,
    1109: 12554, 1110: 12647, 1111: 12741, 1112: 12835, 1113: 12929,
    1114: 13024, 1115: 13119, 1116: 13215, 1117: 13311, 1118: 13408,
    1119: 13504, 1120: 13601, 1121: 13699, 1122: 13797, 1123: 13895,
    1124: 13993, 1125: 14092, 1126: 14192, 1127: 14292, 1128: 14392,
    1129: 14493, 1130: 14594, 1131: 14696, 1132: 14798, 1133: 14901,
    1134: 15004, 1135: 15107, 1136: 15211, 1137: 15316, 1138: 15422,
    1139: 15529, 1140: 15635, 1141: 15743, 1142: 15851, 1143: 15959,
    1144: 16068, 1145: 16178, 1146: 16288, 1147: 16398, 1148: 16509,
    1149: 16621, 1150: 16733, 1151: 16845, 1152: 16959, 1153: 17072,
    1154: 17187, 1155: 17302, 1156: 17417, 1157: 17533, 1158: 17649,
    1159: 17766, 1160: 17884, 1161: 18002, 1162: 18121, 1163: 18241,
    1164: 18361, 1165: 18482, 1166: 18603, 1167: 18725, 1168: 18848,
    1169: 18971, 1170: 19096, 1171: 19221, 1172: 19346, 1173: 19473,
    1174: 19600, 1175: 19728, 1176: 19857, 1177: 19986, 1178: 20117,
    1179: 20247, 1180: 20379, 1181: 20511, 1182: 20644, 1183: 20777,
    1184: 20911, 1185: 21046, 1186: 21181, 1187: 21317, 1188: 21453,
    1189: 21591, 1190: 21728, 1191: 21867, 1192: 22006, 1193: 22146,
    1194: 22287, 1195: 22428, 1196: 22570, 1197: 22712, 1198: 22855,
    1199: 22999, 1200: 23144, 1201: 23289, 1202: 23435, 1203: 23581,
    1204: 23729, 1205: 23877, 1206: 24026, 1207: 24175, 1208: 24326,
    1209: 24477, 1210: 24628, 1211: 24781, 1212: 24934, 1213: 25087,
    1214: 25241, 1215: 25396, 1216: 25551, 1217: 25707, 1218: 25863,
    1219: 26020, 1220: 26177, 1221: 26335, 1222: 26494, 1223: 26653,
    1224: 26813, 1225: 26973, 1226: 27134, 1227: 27296, 1228: 27458,
    1229: 27620,
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_hydrology_csv(source_xlsx: Path) -> bytes:
    """Read the USBR natural-flow workbook and return the 43-line (header
    + 42 rows) hydrology_v3.csv content as bytes (LF endings)."""
    import pandas as pd  # local import: this tool is not on the runtime path

    xlsx_bytes = source_xlsx.read_bytes()
    actual = _sha256_bytes(xlsx_bytes)
    if actual != SOURCE_XLSX_SHA256:
        raise ValueError(
            f"{source_xlsx} sha256 {actual} does not match the expected "
            f"{SOURCE_XLSX_SHA256} (NaturalFlows1906-2020_20221215.xlsx as "
            "retrieved 2026-09-28); refusing to build the hydrology table "
            "from an unverified or different source file."
        )

    xl = pd.ExcelFile(source_xlsx)
    raw = xl.parse(SHEET_NAME, header=None)
    names = raw.iloc[3, 3:].tolist()
    body = raw.iloc[6:, 2:].copy()
    body.columns = ["year"] + names
    body = body[pd.to_numeric(body["year"], errors="coerce").notna()]
    body["year"] = body["year"].astype(int)
    body = body.set_index("year").apply(pd.to_numeric, errors="coerce")

    buf = io.StringIO()
    buf.write(
        "sim_year,source_calendar_year,lees_ferry_cy_natural_flow_af,"
        "lees_ferry_to_below_hoover_cy_intervening_af\n"
    )
    for sim_year in range(2019, 2061):
        cal_year = YEAR_MAP[sim_year]
        if cal_year not in body.index:
            raise ValueError(
                f"{source_xlsx} sheet {SHEET_NAME!r} has no row for calendar "
                f"year {cal_year} (mapped from sim year {sim_year})."
            )
        lf = int(round(body.loc[cal_year, LEES_FERRY_COL]))
        hoover = int(round(body.loc[cal_year, BELOW_HOOVER_COL]))
        buf.write(f"{sim_year},{cal_year},{lf},{hoover - lf}\n")
    return buf.getvalue().encode("utf-8")


def build_mead_capacity_csv() -> bytes:
    """Return the 336-line (header + 335 rows) mead_capacity_usbr2009_1ft.csv
    content as bytes (LF endings), converting the literal kaf table above
    to whole acre-feet."""
    buf = io.StringIO()
    buf.write("elevation_ft,available_capacity_above_895ft_af\n")
    for ft in range(895, 1230):
        buf.write(f"{ft},{MEAD_CAPACITY_TABLE_KAF[ft] * 1000}\n")
    return buf.getvalue().encode("utf-8")


def _write_checked(path: Path, data: bytes, expected_sha256: str, label: str) -> None:
    actual = _sha256_bytes(data)
    if actual != expected_sha256:
        raise ValueError(
            f"{label}: freshly built content hashes to {actual}, expected "
            f"{expected_sha256}. Not writing {path} -- either the source "
            "data changed or the expected constant in this script is stale; "
            "resolve the discrepancy before committing a new checksum."
        )
    path.write_bytes(data)
    print(f"wrote {path} ({len(data)} bytes, sha256={actual})")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source-xlsx", type=Path, default=None,
        help="Path to NaturalFlows1906-2020_20221215.xlsx (required for "
             "--target hydrology/all)",
    )
    parser.add_argument(
        "--target", choices=("all", "hydrology", "mead"), default="all",
    )
    args = parser.parse_args(argv)

    if args.target in ("all", "mead"):
        _write_checked(MEAD_CSV, build_mead_capacity_csv(), MEAD_CAPACITY_SHA256,
                        "mead_capacity_usbr2009_1ft.csv")

    if args.target in ("all", "hydrology"):
        if args.source_xlsx is None:
            print(
                "--source-xlsx is required to (re)build hydrology_v3.csv "
                "(the raw USBR workbook is not committed to this repo); "
                "skipping. Download it from "
                "https://www.usbr.gov/lc/region/g4000/NaturalFlow/current.html",
                file=sys.stderr,
            )
            if args.target == "hydrology":
                return 2
        else:
            _write_checked(HYDROLOGY_CSV, build_hydrology_csv(args.source_xlsx),
                            HYDROLOGY_V3_SHA256, "hydrology_v3.csv")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
