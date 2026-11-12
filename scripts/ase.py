#!/usr/bin/env python3
"""Write a CharmTone Adobe Swatch Exchange file from charmtone.go.

The palette is parsed from the Go source so the .ase cannot drift from it.
"""

import argparse
import re
import struct
import subprocess
import sys
from pathlib import Path

# ASE block kinds. Color type 2 is a normal (process) swatch.
GROUP_START = 0xC001
GROUP_END = 0xC002
COLOR_ENTRY = 0x0001
COLOR_NORMAL = 2

# IsPrimary lists the saturated row, then the light row.
PRIMARY = ("Charple", "Dolly", "Julep", "Zest")
PRIMARY_LIGHT = ("Hazy", "Blush", "Bok", "Butter")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "charmtone.go"


def die(message):
    print(f"ase: {message}", file=sys.stderr)
    raise SystemExit(1)


def strip_line_comment(line):
    in_string = False
    i = 0
    while i < len(line):
        char = line[i]
        if char == '"':
            in_string = not in_string
        elif not in_string and line.startswith("//", i):
            return line[:i]
        i += 1
    return line


def strip_comments(text):
    return "\n".join(strip_line_comment(line) for line in text.splitlines())


def matching_block(text, start, open_ch, close_ch):
    if text[start] != open_ch:
        die(f"expected {open_ch}")
    depth = 0
    i = start
    in_string = False
    while i < len(text):
        char = text[i]
        if in_string:
            if char == "\\":
                i += 2
                continue
            if char == '"':
                in_string = False
            i += 1
            continue
        if char == '"':
            in_string = True
        elif text.startswith("//", i):
            newline = text.find("\n", i)
            i = len(text) if newline < 0 else newline
            continue
        elif char == open_ch:
            depth += 1
        elif char == close_ch:
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
        i += 1
    die(f"unbalanced {open_ch}")


def block_after(text, marker, open_ch, close_ch):
    at = text.find(marker)
    if at < 0:
        die(f"missing {marker}")
    open_at = text.find(open_ch, at)
    if open_at < 0:
        die(f"missing body for {marker}")
    return matching_block(text, open_at, open_ch, close_ch)


def parse_iota(text):
    body = block_after(text, "const (", "(", ")")
    if "iota" not in body:
        die("key const block is not an iota list")
    keys = []
    for line in body.splitlines():
        code = strip_line_comment(line).strip()
        if not code:
            continue
        match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\b", code)
        if not match:
            die(f"unreadable key line: {code}")
        keys.append(match.group(1))
    if not keys:
        die("no color keys found")
    return keys


def parse_names(text):
    body = block_after(text, "var names =", "{", "}")
    names = {}
    for match in re.finditer(r'([A-Za-z_][A-Za-z0-9_]*)\s*:\s*"([^"]*)"', body):
        key, name = match.group(1), match.group(2)
        if key in names:
            die(f"duplicate name entry for {key}")
        names[key] = name
    if not names:
        die("no names found")
    return names


def parse_colors(text):
    body = block_after(text, "var colors =", "{", "}")
    pattern = re.compile(
        r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*"
        r"\{\s*R:\s*(0x[0-9A-Fa-f]+)\s*,\s*"
        r"G:\s*(0x[0-9A-Fa-f]+)\s*,\s*"
        r"B:\s*(0x[0-9A-Fa-f]+)\s*,\s*"
        r"A:\s*(0x[0-9A-Fa-f]+)\s*\}"
        r'(?:\s*,)?(?:\s*//\s*"#([0-9A-Fa-f]{6})")?'
    )
    colors = {}
    for match in pattern.finditer(body):
        key = match.group(1)
        channels = tuple(int(match.group(i), 16) for i in range(2, 6))
        if key in colors:
            die(f"duplicate color entry for {key}")
        if any(channel > 255 for channel in channels):
            die(f"{key} channel out of range")
        red, green, blue, alpha = channels
        if alpha != 0xFF:
            die(f"{key} is not opaque; ASE has no alpha")
        comment = match.group(6)
        if comment is not None:
            hex_color = f"{red:02X}{green:02X}{blue:02X}"
            if comment.upper() != hex_color:
                die(f"{key} hex comment #{comment} != #{hex_color}")
        colors[key] = (red, green, blue)
    if not colors:
        die("no colors found")
    return colors


def parse_aliases(text):
    return re.findall(
        r"(?m)^const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*$",
        text,
    )


def func_body(text, name):
    match = re.search(
        rf"func\s+(?:\(\s*\w+\s+Key\s*\)\s+)?{name}\s*\(",
        text,
    )
    if not match:
        die(f"missing func {name}")
    open_at = text.find("{", match.end())
    if open_at < 0:
        die(f"missing body for {name}")
    return strip_comments(matching_block(text, open_at, "{", "}"))


def slice_keys(body):
    match = re.search(r"\[\]Key\s*\{([^}]*)\}", body)
    if not match:
        return None
    return re.findall(r"\b([A-Z][A-Za-z0-9_]*)\b", match.group(1))


def eval_appends(body, order):
    index = {key: i for i, key in enumerate(order)}
    loops = []
    for match in re.finditer(
        r"for\s+(\w+)\s*:=\s*(\w+)\s*;\s*\1\s*<=\s*(\w+)\s*;\s*\1\+\+\s*\{([^}]*)\}",
        body,
        re.S,
    ):
        var, start, end = match.group(1), match.group(2), match.group(3)
        if start not in index or end not in index:
            die(f"bad key range {start}..{end}")
        if index[end] < index[start]:
            die(f"empty key range {start}..{end}")
        loops.append(
            (match.start(), match.end(), var, order[index[start] : index[end] + 1])
        )

    found = []
    for match in re.finditer(r"append\(\s*\w+\s*,\s*([^)]*)\)", body):
        args = [part.strip() for part in match.group(1).split(",") if part.strip()]
        loop = next((item for item in loops if item[0] <= match.start() < item[1]), None)
        if loop:
            var, keys = loop[2], loop[3]
            if args != [var]:
                die(f"unsupported loop append: {', '.join(args)}")
            found.extend(keys)
            continue
        for arg in args:
            if arg not in index:
                die(f"unknown key {arg}")
            found.append(arg)
    if not found:
        die("group builder produced no keys")
    return found


def parse_group(text, name, order):
    body = func_body(text, name)
    keys = slice_keys(body)
    if keys is None:
        keys = eval_appends(body, order)
    unknown = [key for key in keys if key not in order]
    if unknown:
        die(f"{name} references unknown keys: {', '.join(unknown)}")
    if len(keys) != len(set(keys)):
        die(f"{name} lists a key more than once")
    return keys


def load_palette(text):
    keys = parse_iota(text)
    names = parse_names(text)
    colors = parse_colors(text)
    if len(keys) != len(set(keys)):
        die("duplicate key in iota list")
    if set(keys) != set(names) or set(keys) != set(colors):
        die(
            "iota, names, and colors disagree: "
            f"{len(keys)} keys, {len(names)} names, {len(colors)} colors"
        )
    if len(set(names.values())) != len(names):
        die("two keys share a display name")
    for alias, target in parse_aliases(text):
        if alias in keys:
            die(f"{alias} aliases {target} and must not be its own swatch")
        if target not in keys:
            die(f"{alias} aliases unknown key {target}")
    return keys, names, colors


def spectrum_columns(spectrum):
    # Spectrum() is rows of three: dark, mid, light.
    if len(spectrum) % 3 != 0:
        die(f"spectrum length {len(spectrum)} is not rows of three")
    return spectrum[0::3], spectrum[1::3], spectrum[2::3]


def build_groups(text, keys):
    spectrum = parse_group(text, "Spectrum", keys)
    dark, mid, light = spectrum_columns(spectrum)
    neutrals = parse_group(text, "Neutrals", keys)
    charples = parse_group(text, "Charples", keys)
    additions = [key for key in parse_group(text, "Additions", keys) if key != "Julep"]
    deletions = [key for key in parse_group(text, "Deletions", keys) if key != "Cherry"]
    is_primary = parse_group(text, "IsPrimary", keys)
    # The library's secondary row leaves Turtle in the spectrum mid row.
    secondary = [key for key in parse_group(text, "IsSecondary", keys) if key != "Turtle"]
    if is_primary != list(PRIMARY + PRIMARY_LIGHT):
        die("IsPrimary does not match the Primary and Primary Light rows")
    if "Butter" in neutrals:
        die("Butter is already in Neutrals()")
    if "Turtle" not in mid:
        die("Turtle is missing from the spectrum mid row")

    groups = [
        ("Spectrum Dark", dark),
        ("Spectrum Mid", mid),
        ("Spectrum Light", light),
        ("Primary", list(PRIMARY)),
        ("Primary Light", list(PRIMARY_LIGHT)),
        ("Secondary", secondary),
        ("Charples", charples),
        ("Additions", additions),
        ("Deletions", deletions),
        ("Neutrals", neutrals + ["Butter"]),
    ]
    covered = {key for _, members in groups for key in members}
    missing = [key for key in keys if key not in covered]
    if missing:
        die(f"keys missing from swatches: {', '.join(missing)}")
    return groups


def utf16_name(name):
    encoded = name.encode("utf-16-be") + b"\x00\x00"
    return struct.pack(">H", len(encoded) // 2) + encoded


def ase_block(kind, payload):
    return struct.pack(">HI", kind, len(payload)) + payload


def encode_ase(groups, names, colors):
    blocks = []
    for group_name, members in groups:
        blocks.append(ase_block(GROUP_START, utf16_name(group_name)))
        for key in members:
            red, green, blue = colors[key]
            payload = utf16_name(names[key])
            payload += b"RGB "
            payload += struct.pack(">fff", red / 255.0, green / 255.0, blue / 255.0)
            payload += struct.pack(">H", COLOR_NORMAL)
            blocks.append(ase_block(COLOR_ENTRY, payload))
        blocks.append(ase_block(GROUP_END, b""))
    return b"ASEF" + struct.pack(">HHI", 1, 0, len(blocks)) + b"".join(blocks)


def read_ase_name(payload, offset):
    count = struct.unpack_from(">H", payload, offset)[0]
    offset += 2
    raw = payload[offset : offset + count * 2]
    if len(raw) != count * 2 or not raw.endswith(b"\x00\x00"):
        die("ASE name is not UTF-16BE and NUL terminated")
    try:
        name = raw[:-2].decode("utf-16-be")
    except UnicodeDecodeError as exc:
        die(f"ASE name is not UTF-16BE: {exc}")
    return name, offset + count * 2


def parse_ase(data):
    if len(data) < 12 or data[:4] != b"ASEF":
        die("ASE signature is not ASEF")
    major, minor, count = struct.unpack_from(">HHI", data, 4)
    if (major, minor) != (1, 0):
        die(f"ASE version is {major}.{minor}, want 1.0")
    offset = 12
    blocks = []
    for _ in range(count):
        if offset + 6 > len(data):
            die("ASE ended inside a block header")
        kind, length = struct.unpack_from(">HI", data, offset)
        offset += 6
        payload = data[offset : offset + length]
        if len(payload) != length:
            die("ASE block is truncated")
        offset += length
        blocks.append((kind, payload))
    if offset != len(data):
        die("ASE file has trailing bytes")
    return blocks


def verify(data, groups, names, colors):
    blocks = parse_ase(data)
    parsed = []
    index = 0
    while index < len(blocks):
        kind, payload = blocks[index]
        if kind != GROUP_START:
            die("ASE group does not start with a group block")
        group_name, end = read_ase_name(payload, 0)
        if end != len(payload):
            die(f"extra data in group {group_name}")
        index += 1
        swatches = []
        while index < len(blocks) and blocks[index][0] == COLOR_ENTRY:
            payload = blocks[index][1]
            swatch_name, at = read_ase_name(payload, 0)
            model = payload[at : at + 4]
            at += 4
            if model != b"RGB ":
                die(f"{swatch_name} is not an RGB swatch")
            if at + 14 != len(payload):
                die(f"{swatch_name} has a bad color record")
            red, green, blue = struct.unpack_from(">fff", payload, at)
            color_type = struct.unpack_from(">H", payload, at + 12)[0]
            if color_type != COLOR_NORMAL:
                die(f"{swatch_name} color type is {color_type}, want normal")
            swatches.append((swatch_name, (red, green, blue)))
            index += 1
        if index >= len(blocks) or blocks[index][0] != GROUP_END:
            die(f"group {group_name} is missing its end block")
        if blocks[index][1]:
            die(f"group {group_name} end block is not empty")
        parsed.append((group_name, swatches))
        index += 1

    expected = []
    for group_name, members in groups:
        swatches = []
        for key in members:
            red, green, blue = colors[key]
            floats = tuple(
                struct.unpack(">f", struct.pack(">f", channel / 255.0))[0]
                for channel in (red, green, blue)
            )
            swatches.append((names[key], floats))
        expected.append((group_name, swatches))
    if parsed != expected:
        die("reparsed ASE does not match charmtone.go")

    seen = {name for _, swatches in parsed for name, _ in swatches}
    wanted = set(names.values())
    if seen != wanted:
        missing = sorted(wanted - seen)
        extra = sorted(seen - wanted)
        die(f"swatch names diverge, missing {missing} extra {extra}")
    # Charcoal and Ash are deprecated aliases of Char and Sash.
    forbidden = seen & {"Charcoal", "Ash"}
    if forbidden:
        die(f"deprecated alias emitted: {', '.join(sorted(forbidden))}")


def report(groups, destination):
    swatches = sum(len(members) for _, members in groups)
    keys = {key for _, members in groups for key in members}
    print(f"{destination}: {len(groups)} groups, {swatches} swatches, {len(keys)} keys")
    for name, members in groups:
        print(f"  {name}: {len(members)}")


def describe_version(root):
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def output_path(explicit, version):
    if explicit:
        return Path(explicit)
    if not version:
        version = describe_version(ROOT)
    if version:
        return Path(f"charmtone-{version}.ase")
    return Path("charmtone.ase")


def generate(source, output, check):
    path = source or DEFAULT_SOURCE
    if not path.is_file():
        die(f"cannot read {path}")
    text = path.read_text(encoding="utf-8")
    keys, names, colors = load_palette(text)
    groups = build_groups(text, keys)
    for alias, _ in parse_aliases(text):
        if alias in names.values():
            die(f"deprecated alias {alias} would be emitted")
    data = encode_ase(groups, names, colors)
    verify(data, groups, names, colors)
    if check:
        report(groups, "ok")
        return
    destination = Path(output)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(data)
    try:
        verify(temporary.read_bytes(), groups, names, colors)
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    report(groups, destination)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate a CharmTone .ase swatch file")
    parser.add_argument(
        "output",
        nargs="?",
        help="output path (default: charmtone-<version>.ase)",
    )
    parser.add_argument(
        "--version",
        help="version used in the default file name, such as v0.2.0",
    )
    parser.add_argument("--check", action="store_true", help="validate without writing a file")
    parser.add_argument("--source", type=Path, help="path to charmtone.go")
    args = parser.parse_args(argv)
    destination = None if args.check else output_path(args.output, args.version)
    generate(args.source, destination, args.check)


if __name__ == "__main__":
    main()
