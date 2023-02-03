# stl-scraper - Short-Term Listings Scraper

Scrape short-term listings providers (Airbnb).

Given a search query, e.g. "San Diego, CA" or "Rome, Italy", search Airbnb inventory and collect data on listings. Save
results to a CSV file or Elasticsearch.

## Usage

```shell
# activate the virtual env
. .venv/bin/activate

# run the script
./stl.py search "Madrid, Spain"
```

## Options

```
Short-Term Listings (STL) Scraper

Usage:
    stl.py search <query> [--checkin=<checkin> --checkout=<checkout> 
                  [--priceMin=<priceMin>] [--priceMax=<priceMax>]] 
                  [--roomTypes=<roomTypes>] [--storage=<storage>] [-v|--verbose]
    stl.py calendar (<listingId> | --all)
    stl.py pricing <listingId> --checkin=<checkin> --checkout=<checkout>
    stl.py data <listingId>

Arguments:
    <query>          The query string to search (e.g. "San Diego, CA")
    <listingId>      The listing id

Options:
    --checkin=<checkin>    Check-in date, e.g. "2023-06-01"
    --checkout=<checkout>  Check-out date, e.g. "2023-06-30"
    --priceMin=<priceMin>  Minimum nightly or monthly price
    --priceMax=<priceMax>  Maximum nightly or monthly price
    --all                  Update calendar for all listings (requires Elasticsearch backend)

Global Options:
    --currency=<currency>  "USD", "EUR", etc. [default: USD]
    --source=<source>      Only allows "airbnb" for now. [default: airbnb]
```

## Requirements

- BSD | Linux | WSL
- Python >= 3.10

## Installation

Clone the repo, then:

```shell
# create the config file
cp stl.ini.dist stl.ini

# create the virtual env
python3 -m venv .venv

# activate the virtual env
. .venv/bin/activate

# install dependencies in virtual env
pip install -r requirements.txt
```
