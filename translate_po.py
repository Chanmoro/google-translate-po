import argparse
import functools
import json
import os
import sys

from time import sleep

from google.cloud import translate

_cache_home = "."
_cache_filename = "translation-cache.json"
_translated_text_length = 0
_api_call_count = 0

translate_client = translate.Client()


def calculate_fee(text_len, dollar_per_currency=None):
    """
    https://cloud.google.com/translate/pricing?hl=en

    * Google charges on per character basis, even if the character is multiple bytes,
      where a character corresponds to a (code-point).
    * Google does not charge extra for language detection when you do not specify
      the source language for the translate method.
    """
    if dollar_per_currency is None:
        dollar_per_currency = 1  # dollar
    dollar = text_len / (10 ** 6) * 20
    return dollar_per_currency * dollar


def cache_translation(callback):
    @functools.wraps(callback)
    def decorated(*args, **kwargs):
        file_path = os.path.join(_cache_home, _cache_filename)
        key = f"{args[0]}:{args[1]}"
        cache = {}
        try:
            with open(file_path) as f:
                cache = json.load(f)
        except FileNotFoundError:
            pass
        cached = cache.get(key)
        if cached:
            return cached
        result = callback(*args, **kwargs)
        cache[key] = result
        with open(file_path, "w") as f:
            json.dump(cache, f, indent=4)
        return result

    return decorated


@cache_translation
def translate(text, target_lang):
    if text == "":
        return ""
    global _translated_text_length, _api_call_count
    _translated_text_length += len(text)

    if _api_call_count % 10 == 0:
        sleep(1)

    translation = translate_client.translate(text, target_language=target_lang)
    _api_call_count += 1

    return translation.get('translatedText')


def parse_po(filepath, target_lang):
    """Parse and process po file.

    Input example is below:

    #: ../../source/index.rst:16
    msgid "Introduction"
    msgstr ""

    #: ../../source/index.rst:5
    msgid ""
    "This is an example of multiple lines"
    "Hello"
    "World"
    msgstr ""
    "これは複数行の例です。"
    "こんにちは"
    "世界"
    """
    with open(filepath) as f:
        processing_msgid = False
        processing_msgstr = False
        msgid = ""

        for line in f:
            cleaned = line.strip(" \n")
            if processing_msgstr:
                if cleaned.startswith('"') and cleaned.endswith('"'):
                    # msgstr might be multiple lines
                    continue
                else:
                    processing_msgstr = False
                    translated = translate(msgid, target_lang)
                    print(f'msgstr "{translated}"')
                    msgid = ""

            if processing_msgid:
                if cleaned.startswith('"') and cleaned.endswith('"'):
                    msgid += cleaned.strip('"')
                else:
                    processing_msgid = False

            if line.startswith("msgstr "):
                processing_msgstr = True
                continue

            print(line, end="")

            if cleaned.startswith("msgid"):
                processing_msgid = True
                text = cleaned[len("msgid"):].lstrip(' ').strip('"')
                msgid += text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filepath")
    parser.add_argument('--lang', default="ja", type=str,
                        help='target language (default: "ja")')
    parser.add_argument('--currency', default=111.90, type=float,
                        help='dollar per your currency. (default currency is yen: 111.90)')
    args = parser.parse_args()
    parse_po(args.filepath, args.lang)

    fee = calculate_fee(_translated_text_length, dollar_per_currency=args.currency)
    print("Cost: {} yen".format(fee), file=sys.stderr)


if __name__ == '__main__':
    main()
