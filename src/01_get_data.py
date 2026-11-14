"""Step 1: download all raw data into data/raw.

Raw files are saved exactly as the APIs return them (no cleaning here).
Every download is recorded in data/raw/download_log.csv with the date,
the URL and the file size.

A file that already exists is NOT downloaded again. This keeps the raw
data fixed once collected, so results can be reproduced later even if the
IMF or World Bank revise their data. To refresh a file, delete it and run
this script again.

Two files cannot be downloaded by the script and must be saved by hand in
data/raw/manual (see MANUAL_FILES below).
"""

import csv
import datetime
import time

import requests

from common import CORE_COUNTRIES, MANUAL_DIR, PANEL_COUNTRIES, RAW_DIR

LOG_FILE = RAW_DIR / "download_log.csv"

IMF_BASE = "https://api.imf.org/external/sdmx/3.0"
WB_BASE = "https://api.worldbank.org/v2"
JSON_HEADER = {"Accept": "application/json"}

TIMEOUT_SECONDS = 180
MAX_ATTEMPTS = 5
SECONDS_BETWEEN_ATTEMPTS = 15   # waits 15, 30, 45, 60 seconds
RETRY_STATUS_CODES = [429, 500, 502, 503, 504]

WEO_LIVE_NOTE = "WEO live dataflow = October 2026 edition (checked 2026-11-13)"

# World Bank WDI indicators for the core countries.
WB_INDICATORS = [
    "BX.TRF.PWKR.CD.DT",     # Personal remittances, received (current US$)
    "BX.TRF.PWKR.DT.GD.ZS",  # Personal remittances, received (% of GDP)
    "PA.NUS.FCRF",           # Official exchange rate (LCU per US$)
    "DT.DOD.DPPG.CD",        # External debt stocks, PPG (current US$)
]

# GNI per capita, PPP (current international $), for ALL countries.
# Needed for the income adjustment in the remittance weights.
WB_GNI_PPP = "NY.GNP.PCAP.PP.CD"

# World Bank International Debt Statistics creditor codes (Stage 0).
IDS_CREDITORS = {"730": "china", "087": "russia"}

MANUAL_FILES = {
    "weohistorical.xlsx": (
        "IMF Historical WEO Forecasts Database. Download from "
        "https://www.imf.org/external/pubs/ft/weo/data/weohistorical.xlsx"),
    "undesa_pd_2024_ims_stock_by_sex_destination_and_origin.xlsx": (
        "UN DESA International Migrant Stock 2024, destination and origin. "
        "Download from https://www.un.org/development/desa/pd/content/"
        "international-migrant-stock"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_now():
    """Return the current UTC time as text."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%d %H:%M:%S")


def write_log_row(row):
    """Append one row to the download log (create it with a header)."""
    is_new_file = not LOG_FILE.exists()
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if is_new_file:
            writer.writerow(["downloaded_at_utc", "file", "url", "status",
                             "size_bytes", "note"])
        writer.writerow(row)


def fetch(url, params=None, headers=None):
    """GET a URL, retrying a few times on temporary errors.

    Returns the response if the status is 200, otherwise raises an error.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(url, params=params, headers=headers,
                                    timeout=TIMEOUT_SECONDS)
        except requests.RequestException as error:
            print("    attempt", attempt, "failed:", error)
        else:
            if response.status_code == 200:
                return response
            print("    attempt", attempt, "returned status",
                  response.status_code)
            if response.status_code not in RETRY_STATUS_CODES:
                break
        if attempt < MAX_ATTEMPTS:
            # Wait longer after each failure: server outages often last
            # a minute or two.
            wait = SECONDS_BETWEEN_ATTEMPTS * attempt
            print("    waiting", wait, "seconds before trying again")
            time.sleep(wait)
    raise RuntimeError("Download failed after " + str(MAX_ATTEMPTS)
                       + " attempts: " + url + ". The server may be down; "
                       "try again later. Files already downloaded are kept.")


def check_response(response, source):
    """Basic checks that the response holds data. Raises if it does not."""
    content = response.json()
    if source == "imf_data":
        series = content["data"]["dataSets"][0]["series"]
        assert len(series) > 0, "IMF response contains no series"
    elif source == "imf_structure":
        assert "data" in content, "IMF structure response has no 'data'"
    elif source == "wb_wdi":
        assert len(content) == 2, "World Bank response has wrong layout"
        assert content[1], "World Bank response contains no rows"
        assert content[0]["pages"] == 1, "World Bank response has >1 page"
    elif source == "wb_ids":
        assert len(content["source"]["data"]) > 0, "IDS response is empty"
        assert content.get("pages", 1) == 1, "IDS response has >1 page"
    else:
        raise ValueError("Unknown source type: " + source)


def download_file(relative_path, url, source, params=None, headers=None,
                  required=True, note=""):
    """Download one file into data/raw, unless it already exists.

    If required is False, a failed download prints a warning instead of
    stopping the script (used for nice-to-have files only).
    """
    path = RAW_DIR / relative_path
    if path.exists():
        print("Already downloaded, skipping:", relative_path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    print("Downloading:", relative_path)

    try:
        response = fetch(url, params=params, headers=headers)
        check_response(response, source)
    except (RuntimeError, ValueError, AssertionError, KeyError, IndexError,
            TypeError) as error:
        if required:
            raise
        print("    WARNING: optional download failed:", error)
        write_log_row([utc_now(), relative_path, url, "FAILED (optional)",
                       0, str(error)])
        return

    # Save the bytes exactly as received: this is the untouched raw file.
    path.write_bytes(response.content)
    write_log_row([utc_now(), relative_path, response.url,
                   response.status_code, len(response.content), note])


def imf_data_url(agency, dataflow, key):
    """Build an IMF SDMX 3.0 data URL (latest version of the dataflow)."""
    return (IMF_BASE + "/data/dataflow/" + agency + "/" + dataflow
            + "/+/" + key)


def check_manual_files():
    """Check that the hand-downloaded files exist. Raise if any is missing."""
    MANUAL_DIR.mkdir(parents=True, exist_ok=True)
    missing = []
    for file_name, instructions in MANUAL_FILES.items():
        path = MANUAL_DIR / file_name
        if path.exists():
            modified = datetime.datetime.fromtimestamp(path.stat().st_mtime)
            print("Manual file found:", file_name, "| saved on",
                  modified.strftime("%Y-%m-%d"))
        else:
            missing.append(file_name)
            print("MISSING manual file:", file_name)
            print("    " + instructions)
            print("    Save it in:", MANUAL_DIR)
    if missing:
        raise FileNotFoundError("Missing manual files: " + ", ".join(missing))


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------

def download_imf_weo():
    """WEO: all indicators for core countries, and growth for all countries."""
    for country in CORE_COUNTRIES:
        download_file("imf_weo/weo_live_" + country + ".json",
                      imf_data_url("IMF.RES", "WEO", country + ".*.A"),
                      "imf_data", headers=JSON_HEADER, note=WEO_LIVE_NOTE)

    # Real GDP growth for every country: needed for the partner indices.
    download_file("imf_weo/weo_live_all_countries_ngdp_rpch.json",
                  imf_data_url("IMF.RES", "WEO", "*.NGDP_RPCH.A"),
                  "imf_data", headers=JSON_HEADER, note=WEO_LIVE_NOTE)

    # April 2026 edition of the same series, to show forecast revisions.
    download_file("imf_weo/weo_2026apr_all_countries_ngdp_rpch.json",
                  imf_data_url("IMF.RES", "WEO_2026_APR_VINTAGE",
                               "*.NGDP_RPCH.A"),
                  "imf_data", headers=JSON_HEADER,
                  note="WEO April 2026 vintage dataflow")


def download_imf_trade():
    """IMTS: goods trade by partner country, annual, for panel countries."""
    for country in PANEL_COUNTRIES:
        download_file("imf_imts/imts_" + country + ".json",
                      imf_data_url("IMF.STA", "IMTS", country + ".*.*.A"),
                      "imf_data", headers=JSON_HEADER)


def download_imf_code_lists():
    """Optional: IMF code lists, to document what attribute codes mean."""
    structures = {"DSD_IMTS": "IMF.STA", "DSD_WEO": "IMF.RES"}
    for dsd, agency in structures.items():
        download_file("imf_structure/" + dsd.lower() + ".json",
                      IMF_BASE + "/structure/datastructure/" + agency + "/"
                      + dsd + "/+",
                      "imf_structure", params={"references": "descendants"},
                      headers=JSON_HEADER, required=False)


def download_world_bank():
    """World Bank WDI indicators, GNI per capita, and IDS debt by creditor."""
    countries = ";".join(CORE_COUNTRIES)
    for indicator in WB_INDICATORS:
        download_file("wb_wdi/" + indicator + ".json",
                      WB_BASE + "/country/" + countries + "/indicator/"
                      + indicator,
                      "wb_wdi",
                      params={"format": "json", "per_page": 1000,
                              "date": "1990:2026"})

    download_file("wb_wdi/" + WB_GNI_PPP + "_all_countries.json",
                  WB_BASE + "/country/all/indicator/" + WB_GNI_PPP,
                  "wb_wdi",
                  params={"format": "json", "per_page": 20000,
                          "date": "1990:2026"})

    for code, name in IDS_CREDITORS.items():
        download_file("wb_ids/tjk_bilateral_ppg_debt_" + name + ".json",
                      WB_BASE + "/sources/6/country/TJK/series/"
                      "DT.DOD.BLAT.CD/counterpart-area/" + code + "/time/all",
                      "wb_ids", params={"format": "json", "per_page": 500})


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("Raw data folder:", RAW_DIR)
    download_imf_weo()
    download_imf_trade()
    download_imf_code_lists()
    download_world_bank()
    check_manual_files()
    print("Download log:", LOG_FILE)


if __name__ == "__main__":
    main()
