# Idlescape Extraction

Using Python 3.9+ and NodeJS 14.17+ and some janktacular code, this will extract data from the Idlescape frontend JavaScript loaded 
on each client.

```shell
python3.9 extraction.py
```

If you have [Prettier](https://prettier.io/) installed you can pass the `--format` argument to generate formatted JSON files.

```shell
python3.9 extraction.py --format
```