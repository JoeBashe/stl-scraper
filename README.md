# stl-scraper - Short-Term Listings Scraper

Scrape short-term listings providers (currently just Airbnb)

## Requirements

- Python 3.10+
- Linux

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

## Usage

```shell
# activate the virtual env
. env/bin/activate

# run the script
./stl.py "Madrid, Spain"
```
