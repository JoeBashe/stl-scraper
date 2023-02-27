# stl-scraper - Short-Term Listings Scraper

Scrape short-term listings providers (Airbnb).

Given a search query, e.g. "San Diego, CA" or "Rome, Italy", search Airbnb inventory and collect data on listings. Save
results to a CSV file or Elasticsearch.

## Usage

### (basic installation)

```shell
# activate the virtual env
. .venv/bin/activate

# run the script
./stl.py search "Madrid, Spain"
```

### (advanced installation)
```shell
# spin up the containers
docker compose up -d

# ensure dependencies installed
docker compose exec jupyter-scipy-notebook conda install --yes --file work/requirements.txt

# run the script
docker compose exec jupyter-scipy-notebook /opt/conda/bin/python work/stl.py search -v "Madrid, Spain"
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

### Installation via pip (Option 1 - Basic)

This option assumes you have Python >= 3.10 installed, and that you will manage dependencies using the python `venv` 
module with `pip`. You can connect to your own instance of Elasticsearch. However, Elasticsearch is not required.

```shell
# create the config files
cp .env.dist .env

# create the virtual env
python3 -m venv .venv

# activate the virtual env
. .venv/bin/activate

# install dependencies in virtual env
pip install -r requirements.txt
```

### Installation via docker compose (Option 2 - Advanced)

This option uses docker compose to build:

- `jupyter-scipy-notebook`: jupyter scipy notebook, python, conda
- `setup` temporary container that configures elasticsearch & kibana security
- `es01`: elasticsearch container
- `kibana`: kibana container

```shell
# Create the containers
docker compose up -d

# Install project requirements
docker compose exec jupyter-scipy-notebook conda install --yes --file work/requirements.txt
```

## Using kibana

You can directly view records in Elasticsearch by using Kibana.

1. Scrape some listings using above commands
2. Browse to http://localhost:5601/app/management/kibana/dataViews (u: elastic / p: abc123)
3. Click "Create new data view" on top right
4. Use `short-term-listings` as name and index pattern
5. Click "Save data view to Kibana"
6. Click "Analytics > Discover" on the main menu, selecting the `short-term-listings` data view, and see JSON records

## Troubleshooting

- If using Elasticsearch, you may need to run `sudo sysctl -w vm.max_map_count=262144` on your host machine (see
  https://www.elastic.co/guide/en/elasticsearch/reference/current/vm-max-map-count.html)
