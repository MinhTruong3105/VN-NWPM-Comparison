import re
import sys
from pathlib import Path


# --- Regex patterns ---

URL_PATTERN = re.compile(
    r'https?://\S+|www\.\S+|ftp://\S+'
)
IMAGE_TAG_PATTERN = re.compile(
    r'\[Hình ảnh\]|\[hình ảnh\]|\[image\]|\[img\]',
    re.IGNORECASE
)
SYSTEM_QUOTE_PATTERN = re.compile(
    r'>{1,}\s*.*'
)
USER_SIGNATURE_PATTERN = re.compile(
    r'-{2,}\s*$'
)

EMOTICON_PATTERN = re.compile(
    r'(?:=\)+|:\)+{2,}|:>+|;\)+|:D+|>\.<|T_T|:\|+|>_<|:v+|:\*+|<3+)'
)

EMPTY_PARENS_PATTERN = re.compile(
    r'\(\s*\)'
)
REPEATED_DOTS_PATTERN = re.compile(
    r'\.{2,}'
)

MULTI_SPACE_PATTERN = re.compile(
    r' {2,}'
)

MIN_LENGTH = 7


def remove_urls_and_system(text: str) -> str:
    text = URL_PATTERN.sub('', text)
    text = IMAGE_TAG_PATTERN.sub('', text)
    text = SYSTEM_QUOTE_PATTERN.sub('', text)
    text = USER_SIGNATURE_PATTERN.sub('', text)
    return text


def remove_emoticons(text: str) -> str:
    return EMOTICON_PATTERN.sub('', text)


def normalize_punctuation(text: str) -> str:
    text = EMPTY_PARENS_PATTERN.sub('', text)
    text = REPEATED_DOTS_PATTERN.sub('.', text)
    return text


def normalize_whitespace(text: str) -> str:
    text = MULTI_SPACE_PATTERN.sub(' ', text)
    return text.strip()


def clean_line(line: str) -> str:
    line = remove_urls_and_system(line)
    line = remove_emoticons(line)
    line = normalize_punctuation(line)
    line = normalize_whitespace(line)
    return line


def clean_file(input_path: str, output_path: str) -> dict:
    input_file = Path(input_path)
    output_file = Path(output_path)

    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with input_file.open(encoding='utf-8') as f:
        lines = f.readlines()

    total = len(lines)
    cleaned_lines = []
    dropped = 0

    for line in lines:
        line = line.rstrip('\n')
        cleaned = clean_line(line)
        if len(cleaned) < MIN_LENGTH:
            dropped += 1
            continue
        cleaned_lines.append(cleaned)

    with output_file.open('w', encoding='utf-8') as f:
        f.write('\n'.join(cleaned_lines))

    return {
        'total_lines': total,
        'kept_lines': len(cleaned_lines),
        'dropped_lines': dropped,
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python clean_text.py <input.txt> <output.txt>")
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]

    try:
        stats = clean_file(input_path, output_path)
        print(f"Done: {stats['kept_lines']}/{stats['total_lines']} lines kept "
              f"({stats['dropped_lines']} dropped).")
        print(f"Output: {output_path}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
