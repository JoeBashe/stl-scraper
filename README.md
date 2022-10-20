# stl-scraper - Short-Term Listings Scraper

Scrape short-term listings providers (Airbnb).

Given a search query, e.g. "San Diego, CA" or "Rome, Italy", search Airbnb inventory and collect data on listings. Save results to a CSV file.

## Usage

```shell
# activate the virtual env
. env/bin/activate

# run the script
./stl.py "Madrid, Spain"
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
