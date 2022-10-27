# stl-scraper - Short-Term Listings Scraper

Scrape short-term listings providers (Airbnb).

Given a search query, e.g. "San Diego, CA" or "Rome, Italy", search Airbnb inventory and collect data on listings. Save
results to a CSV file.

## Usage

```shell
# activate the virtual env
. env/bin/activate

# run the script
./stl.py search "Madrid, Spain"
```

## Options

```shell
Short-Term Listings (STL) Scraper

Usage:
    stl.py search <query> [--currency=<currency>] [--roomTypes=<roomTypes>] [--source=<source>]
    stl.py calendar <listingSource> [--currency=<currency>] [--source=<source>]
    stl.py pricing <listingId> <checkin> <checkout> [--currency=<currency>] [--source=<source>]
    stl.py data <listingId> [--source=<source>]

Arguments:
    <query>         - The query string to search (e.g. "San Diego, CA").
    <currency>      - "USD", "EUR", etc. (default: USD)
    <listingId>     - The listing id.
    <roomTypes>     - e.g. "Entire home/apt". Can include multiple separated by comma.
    <listingSource> - One of either: a. listing ID; or b. the special keyword "elasticsearch".
    <source>        - Only allows "airbnb" for now. (default: "airbnb")
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
python3 -m venv env

# activate the virtual env
. env/bin/activate

# install dependencies in virtual env
pip install -r requirements.txt
```
