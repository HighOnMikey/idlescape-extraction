import argparse
import requests
import logging
import regex
import subprocess
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)8s][%(filename)s:%(lineno)s - %(funcName)s()] %(message)s")
idlescape_site = "https://www.idlescape.com"
default_main_chunk = "https://www.idlescape.com/static/js/main.27754d83.chunk.js"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    return parser.parse_args()


def fetch_data(args):
    main_script = args.url
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


def compile_js(output_file, name, data):
    object_re = r"Object\(([a-zA-Z.]+)\)"
    obj = regex.search(object_re, data)
    with open(output_file, "w", newline="\n") as file:
        file.write('fs = require("fs")\n')
        if obj is not None and len(obj) > 1:
            objs = obj[1].split(".")
            file.write(f"let {objs[0]} = {{}}\n")
            file.write(f"{objs[0]}.{objs[1]} = function(self, key, val) {{ self[key] = val; }}\n")

        file.write(f"{data}\n")
        file.write(f'fs.writeFileSync("data/{name}.json", JSON.stringify({name}), "utf-8")\n')


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
    output_dir = Path(__file__).resolve().parent.joinpath("data")
    if not output_dir.exists():
        logging.info(f"creating output directory: {output_dir}")
        Path.mkdir(output_dir)

    data = fetch_data(args)

    logging.info("extracting locations")
    locations = extract_locations(data)
    if locations:
        output_file = output_dir.joinpath("locations.js")
        try:
            compile_js(output_file, "locations", locations)
            logging.info(f"wrote {output_file}")
        except Exception:
            logging.error(f"unable to compile locations: {Exception}")
        try:
            subprocess.call(["node", output_file], shell=True)
            logging.info("converted locations.js to JSON")
        except Exception:
            logging.error(f"unable to convert locations: {Exception}")

    logging.info("extracting enchantments")
    enchantments = extract_enchantments(data)
    if enchantments:
        output_file = output_dir.joinpath("enchantments.js")
        try:
            compile_js(output_file, "enchantments", enchantments)
            logging.info(f"wrote {output_file}")
        except Exception:
            logging.error(f"unable to compile enchantments: {Exception}")
        try:
            subprocess.call(["node", output_file], shell=True)
            logging.info("converted enchantments.js to JSON")
        except Exception:
            logging.error(f"unable to convert enchantments: {Exception}")

    logging.info("extracting items")
    items = extract_items(data)
    if items:
        output_file = output_dir.joinpath("items.js")
        try:
            compile_js(output_file, "items", items)
            logging.info(f"wrote {output_file}")
        except Exception:
            logging.error(f"unable to compile items: {Exception}")
        try:
            subprocess.call(["node", output_file], shell=True)
            logging.info("converted items.js to JSON")
        except Exception:
            logging.error(f"unable to convert items: {Exception}")


if __name__ == "__main__":
    main()
