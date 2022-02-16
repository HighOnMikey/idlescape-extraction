import argparse
import json
import platform

import requests
import logging
import regex
import subprocess
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)8s][%(filename)s:%(lineno)s - %(funcName)s()] %(message)s",
)
idlescape_site = "https://www.idlescape.com"
default_main_chunk = "https://www.idlescape.com/static/js/main.eb1cd48b.chunk.js"
output_dir = Path(__file__).resolve().parent.joinpath("data")
skill_names = ["combat", "fishing", "foraging", "mining", "smithing"]
template_loader = FileSystemLoader("templates")
template_env = Environment(loader=template_loader)


def debug_enabled():
    return logging.root.level == logging.DEBUG


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    parser.add_argument("--format", action="store_true")
    parser.add_argument("--debug", action="store_true")
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
        template = template_env.get_template("data_type.js")
        object_re = r"Object\(([a-zA-Z.]+)\)"
        obj = regex.search(object_re, data)
        if obj is not None and len(obj) > 1:
            obj = obj[1].split(".")
        else:
            obj = None
        with open(js_file, "w", newline="\n") as file:
            file.write(template.render(data_type=name, object_var=obj, data=data, json_file=json_file.as_posix()))
        logging.info(f"wrote {js_file}")
    except Exception as e:
        logging.error(f"unable to compile {name}: {e}", exc_info=debug_enabled())
    try:
        subprocess.call(["node", js_file])
        logging.info(f"converted {js_file.name} to JSON")
    except Exception as e:
        logging.error(f"unable to convert {name}: {e}", exc_info=debug_enabled())

    return json_file


def minimize_json(data, search_keys: list, search_skills: bool = True):
    json_minimized_data = {}
    for key in data:
        json_minimized_data[key] = {}
        for min_key in search_keys:
            if min_key in data[key].keys():
                json_minimized_data[key][min_key] = data[key][min_key]
        if not search_skills:
            continue
        for skill_key in skill_names:
            if skill_key in data[key].keys():
                for min_key in search_keys:
                    if min_key in data[key][skill_key].keys():
                        json_minimized_data[key][min_key] = data[key][skill_key][min_key]

    return json_minimized_data


def minimize_names_only(data, search_skills: bool = True, name_field: str = "name"):
    return {x: v[name_field] for x, v in minimize_json(data, [name_field], search_skills).items()}


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
    item_search_re = r'([a-zA-Z0-9_$]+)(?=\=\{1:\{id:1,name:"Gold").+?([a-zA-Z0-9_$]+)(?=\=function\([a-zA-Z0-9_$]+\))'
    item_search = regex.search(item_search_re, data)

    if len(item_search.groups()) == 2:
        logging.info(
            f"suitable look around terms found (between '{item_search.group(1)}' and '{item_search.group(2)}')"
        )
        item_re = rf"(?<={item_search.group(1)}\=)([\s\S]*?)(?=,{item_search.group(2)}\=)"
    else:
        logging.error(
            "could not find suitable terms to search between for item definitions, skipping item extraction...",
            exc_info=debug_enabled()
        )
        return

    items = regex.search(item_re, data)
    data_string = f"let items = {items.group(0)}\n"
    return data_string


def extract_abilities(data):
    ability_search_re = r'(?=\{1:\{id:1,abilityName:"Auto Attack").+?(?=,[a-zA-Z0-9_$]+\=)'
    ability_search = regex.search(ability_search_re, data)
    data_string = f"let abilities={ability_search[0]}\n"
    return data_string


def format_json(json_file):
    try:
        prettier = "prettier.cmd" if platform.system() == "Windows" else "prettier"
        formatted_file = json_file.with_stem(f"{json_file.stem}.formatted")
        with open(formatted_file, "w", newline="\n") as file:
            subprocess.run([prettier, "--parser", "json", json_file], stdout=file)
    except Exception as e:
        logging.error(f"unable to format {json_file}: {e}", exc_info=debug_enabled())


def main():
    args = parse_args()
    if args.debug:
        logging.root.setLevel(logging.DEBUG)
    if not output_dir.exists():
        logging.info(f"creating output directory: {output_dir}")
        Path.mkdir(output_dir)

    data = fetch_data(args.url)

    if args.format:
        logging.info("formatting json after extraction")

    logging.info("extracting locations")
    locations = extract_locations(data)
    if locations:
        json_file = build_json("locations", locations)
        json_data = json.load(open(json_file, "r"))
        name_data = minimize_names_only(json_data)
        json.dump(name_data, open(json_file.with_stem(f"{json_file.stem}.names"), "w"), separators=(",", ":"))

        if args.format:
            logging.info(f"formatting {json_file.name}")
            format_json(json_file)

    logging.info("extracting enchantments")
    enchantments = extract_enchantments(data)
    if enchantments:
        json_file = build_json("enchantments", enchantments)
        json_data = json.load(open(json_file, "r"))
        name_data = minimize_names_only(json_data, False)
        json.dump(name_data, open(json_file.with_stem(f"{json_file.stem}.names"), "w"), separators=(",", ":"))

        if args.format:
            logging.info(f"formatting {json_file.name}")
            format_json(json_file)

    logging.info("extracting abilities")
    abilities = extract_abilities(data)
    if abilities:
        json_file = build_json("abilities", abilities)
        json_data = json.load(open(json_file, "r"))
        name_data = minimize_names_only(json_data, search_skills=False, name_field="abilityName")
        json.dump(name_data, open(json_file.with_stem(f"{json_file.stem}.names"), "w"), separators=(",", ":"))

        if args.format:
            logging.info("formatting {json_file.name}")
            format_json(json_file)

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
            search_skills=False,
        )
        json.dump(min_data, open(json_file.with_stem(f"{json_file.stem}.min"), "w"), separators=(",", ":"))
        name_data = minimize_names_only(json_data)
        json.dump(name_data, open(json_file.with_stem(f"{json_file.stem}.names"), "w"), separators=(",", ":"))

        if args.format:
            logging.info(f"formatting {json_file.name}")
            format_json(json_file)


if __name__ == "__main__":
    main()
