import argparse
import json
import requests
import logging
import regex
import subprocess
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)8s][%(filename)s:%(lineno)s - %(funcName)s()] %(message)s",
)
idlescape_site = "https://www.idlescape.com"
default_main_chunk = "https://www.idlescape.com/static/js/main.27754d83.chunk.js"
output_dir = Path(__file__).resolve().parent.joinpath("data")
skill_names = ["combat", "fishing", "foraging", "mining", "smithing"]

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    return parser.parse_args()


def fetch_data(url):
    main_script = url
    if not main_script:
        logging.info("Automatically detecting main.<hex>.chunk.js")
        main_script_re = r"main\.[a-zA-Z0-9]+\.chunk\.js"
        idlescape_site_text = requests.get(idlescape_site).text
        main_script_search = regex.search(main_script_re, idlescape_site_text)
        if main_script_search is not None:
            main_script = f"{idlescape_site}/static/js/{main_script_search.group(0)}"
            logging.info(f"Detected {main_script}")
        else:
            main_script = default_main_chunk
            logging.info("Main script not detected, using default fallback")

    return requests.get(main_script).text


def build_json(name, data):
    js_file = output_dir.joinpath(f"{name}.js")
    json_file = output_dir.joinpath(f"{name}.json")
    try:
        object_re = r"Object\(([a-zA-Z.]+)\)"
        obj = regex.search(object_re, data)
        with open(js_file, "w", newline="\n") as file:
            file.write('fs = require("fs")\n')
            if obj is not None and len(obj) > 1:
                objs = obj[1].split(".")
                file.write(f"let {objs[0]} = {{}}\n")
                file.write(f"{objs[0]}.{objs[1]} = function(self, key, val) {{ self[key] = val; }}\n")

            file.write(f"{data}\n")
            file.write(f'fs.writeFileSync("{json_file.as_posix()}", JSON.stringify({name}), "utf-8")\n')
        logging.info(f"wrote {js_file}")
    except Exception as e:
        logging.error(f"unable to compile locations: {e}")

    try:
        subprocess.call(["node", js_file])
        logging.info(f"converted {name}.js to JSON")
    except Exception as e:
        logging.error(f"unable to convert locations: {e}")

    return json_file


def minimize_json(data, search_keys: list, search_skills: bool = True):
    json_minimized_data = {}
    for key in data:
        json_minimized_data[key] = {}
        for min_key in set(data[key].keys()).intersection(search_keys):
            json_minimized_data[key][min_key] = data[key][min_key]
        if not search_skills:
            continue
        for skill_key in set(data[key].keys()).intersection(skill_names):
            for min_key in set(data[key][skill_key].keys()).intersection(search_keys):
                json_minimized_data[key][min_key] = data[key][skill_key][min_key]

    return json_minimized_data


def minimize_names_only(data, search_skills: bool = True):
    return {x:v["name"] for x, v in minimize_json(data, ["name"], search_skills).items()}


def extract_locations(data):
    location_re = r'\(([a-zA-Z0-9_$]+)\=(\{10\:\{name\:"Clay Pit").+(,\1\))'
    locations = regex.search(location_re, data)
    data_string = f"let locations={locations.group(0)}\n"
    return data_string


def extract_enchantments(data):
    enchant_re = r"(enchantments)[\s\S]*?(?=,e.exports)"
    enchantments = regex.search(enchant_re, data)
    data_string = f"let {enchantments.group(0)}\n"
    return data_string


def extract_items(data):
    item_look_between_re = r'([a-zA-Z0-9_$]+)(?=\=\{1:\{id:1,name:"Gold").+?([a-zA-Z0-9_$]+)(?=\=function\([a-zA-Z0-9_$]+\))'
    item_look_between = regex.search(item_look_between_re, data)

    if len(item_look_between.groups()) == 2:
        logging.info(f"suitable look around terms found (between '{item_look_between.group(1)}' and '{item_look_between.group(2)}')")
        item_re = fr"(?<={item_look_between.group(1)}\=)([\s\S]*?)(?=,{item_look_between.group(2)}\=)"
    else:
        logging.error("could not find suitable terms to search between for item definitions, skipping item extraction...")
        return

    items = regex.search(item_re, data)
    data_string = f"let items = {items.group(0)}\n"
    return data_string


def main():
    args = parse_args()

    if not output_dir.exists():
        logging.info(f"creating output directory: {output_dir}")
        Path.mkdir(output_dir)

    data = fetch_data(args.url)

    logging.info("extracting locations")
    locations = extract_locations(data)
    if locations:
        json_file = build_json("locations", locations)
        json_data = json.load(open(json_file, "r"))
        name_data = minimize_names_only(json_data)
        json.dump(name_data, open(json_file.with_stem(f"{json_file.stem}.names"), "w"), separators=(",", ":"))

    logging.info("extracting enchantments")
    enchantments = extract_enchantments(data)
    if enchantments:
        json_file = build_json("enchantments", enchantments)
        json_data = json.load(open(json_file, "r"))
        name_data = minimize_names_only(json_data, False)
        json.dump(name_data, open(json_file.with_stem(f"{json_file.stem}.names"), "w"), separators=(",", ":"))

    logging.info("extracting items")
    items = extract_items(data)
    if items:
        json_file = build_json("items", items)
        json_data = json.load(open(json_file, "r"))
        min_data = minimize_json(
            json_data,
            [
                "id",
                "name",
                "itemImage",
                "tags",
                "enchantmentTier",
                "augmentationStats",
                "augmentationCost",
            ],
            False
        )
        json.dump(min_data, open(json_file.with_stem(f"{json_file.stem}.min"), "w"), separators=(",", ":"))
        name_data = minimize_names_only(json_data)
        json.dump(name_data, open(json_file.with_stem(f"{json_file.stem}.names"), "w"), separators=(",", ":"))


if __name__ == "__main__":
    main()
