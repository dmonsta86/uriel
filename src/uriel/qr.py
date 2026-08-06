"""Small standard-library QR encoder used by Uriel certificates.

This module intentionally supports one conservative profile: QR version 5,
error correction level L, byte mode, and all eight masks.  That is sufficient
for Uriel's compact ``URIEL-BLESSING-v1:<sha256>`` payload while avoiding a
runtime dependency.  It is not a general-purpose QR library.
"""
from __future__ import annotations

import html
from typing import List, Optional, Sequence, Tuple

_VERSION = 5
_SIZE = 17 + 4 * _VERSION  # 37
_DATA_CODEWORDS = 108
_ECC_CODEWORDS = 26
_MAX_BYTES = 106


def _append_bits(bits: List[int], value: int, length: int) -> None:
    if value < 0 or value >> length:
        raise ValueError("value does not fit requested bit length")
    for shift in reversed(range(length)):
        bits.append((value >> shift) & 1)


def _gf_multiply(x: int, y: int) -> int:
    result = 0
    while y:
        if y & 1:
            result ^= x
        y >>= 1
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    return result & 0xFF


def _rs_divisor(degree: int) -> List[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for index in range(degree):
            result[index] = _gf_multiply(result[index], root)
            if index + 1 < degree:
                result[index] ^= result[index + 1]
        root = _gf_multiply(root, 0x02)
    return result


def _rs_remainder(data: Sequence[int], divisor: Sequence[int]) -> List[int]:
    result = [0] * len(divisor)
    for value in data:
        factor = value ^ result[0]
        result = result[1:] + [0]
        for index, coefficient in enumerate(divisor):
            result[index] ^= _gf_multiply(coefficient, factor)
    return result


def _codewords(payload: str) -> List[int]:
    raw = payload.encode("utf-8")
    if len(raw) > _MAX_BYTES:
        raise ValueError("Uriel QR payload is too long for version 5-L")
    bits: List[int] = []
    _append_bits(bits, 0x4, 4)  # byte mode
    _append_bits(bits, len(raw), 8)
    for value in raw:
        _append_bits(bits, value, 8)
    capacity = _DATA_CODEWORDS * 8
    bits.extend([0] * min(4, capacity - len(bits)))
    bits.extend([0] * ((-len(bits)) % 8))
    data = []
    for index in range(0, len(bits), 8):
        value = 0
        for bit in bits[index : index + 8]:
            value = (value << 1) | bit
        data.append(value)
    pad = (0xEC, 0x11)
    index = 0
    while len(data) < _DATA_CODEWORDS:
        data.append(pad[index & 1])
        index += 1
    divisor = _rs_divisor(_ECC_CODEWORDS)
    return data + _rs_remainder(data, divisor)


def _set_function(
    modules: List[List[Optional[bool]]],
    function: List[List[bool]],
    x: int,
    y: int,
    dark: bool,
) -> None:
    if 0 <= x < _SIZE and 0 <= y < _SIZE:
        modules[y][x] = dark
        function[y][x] = True


def _finder(
    modules: List[List[Optional[bool]]],
    function: List[List[bool]],
    center_x: int,
    center_y: int,
) -> None:
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            distance = max(abs(dx), abs(dy))
            _set_function(
                modules,
                function,
                center_x + dx,
                center_y + dy,
                distance != 2 and distance != 4,
            )


def _alignment(
    modules: List[List[Optional[bool]]],
    function: List[List[bool]],
    center_x: int,
    center_y: int,
) -> None:
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            _set_function(
                modules,
                function,
                center_x + dx,
                center_y + dy,
                max(abs(dx), abs(dy)) != 1,
            )


def _format_bits(mask: int) -> int:
    # Error-correction level L has format bits 01.
    data = (1 << 3) | mask
    remainder = data
    for _ in range(10):
        remainder = (remainder << 1) ^ ((remainder >> 9) * 0x537)
    return ((data << 10) | remainder) ^ 0x5412


def _draw_format(
    modules: List[List[Optional[bool]]],
    function: List[List[bool]],
    mask: int,
) -> None:
    bits = _format_bits(mask)

    def bit(index: int) -> bool:
        return ((bits >> index) & 1) != 0

    for index in range(6):
        _set_function(modules, function, 8, index, bit(index))
    _set_function(modules, function, 8, 7, bit(6))
    _set_function(modules, function, 8, 8, bit(7))
    _set_function(modules, function, 7, 8, bit(8))
    for index in range(9, 15):
        _set_function(modules, function, 14 - index, 8, bit(index))

    for index in range(8):
        _set_function(modules, function, _SIZE - 1 - index, 8, bit(index))
    for index in range(8, 15):
        _set_function(modules, function, 8, _SIZE - 15 + index, bit(index))
    _set_function(modules, function, 8, _SIZE - 8, True)


def _base_matrix() -> Tuple[List[List[Optional[bool]]], List[List[bool]]]:
    modules: List[List[Optional[bool]]] = [[None] * _SIZE for _ in range(_SIZE)]
    function = [[False] * _SIZE for _ in range(_SIZE)]
    for index in range(_SIZE):
        _set_function(modules, function, 6, index, index % 2 == 0)
        _set_function(modules, function, index, 6, index % 2 == 0)
    _finder(modules, function, 3, 3)
    _finder(modules, function, _SIZE - 4, 3)
    _finder(modules, function, 3, _SIZE - 4)
    _alignment(modules, function, 30, 30)
    _draw_format(modules, function, 0)  # reserve locations; redrawn after masking
    return modules, function


def _mask_bit(mask: int, x: int, y: int) -> bool:
    if mask == 0:
        return (x + y) % 2 == 0
    if mask == 1:
        return y % 2 == 0
    if mask == 2:
        return x % 3 == 0
    if mask == 3:
        return (x + y) % 3 == 0
    if mask == 4:
        return (x // 3 + y // 2) % 2 == 0
    if mask == 5:
        return (x * y) % 2 + (x * y) % 3 == 0
    if mask == 6:
        return ((x * y) % 2 + (x * y) % 3) % 2 == 0
    if mask == 7:
        return ((x + y) % 2 + (x * y) % 3) % 2 == 0
    raise ValueError("mask must be 0 through 7")


def _draw_data(
    base: Sequence[Sequence[Optional[bool]]],
    function: Sequence[Sequence[bool]],
    data: Sequence[int],
    mask: int,
) -> List[List[bool]]:
    modules: List[List[bool]] = [
        [bool(value) if value is not None else False for value in row] for row in base
    ]
    bits: List[int] = []
    for value in data:
        _append_bits(bits, value, 8)
    bit_index = 0
    right = _SIZE - 1
    while right >= 1:
        if right == 6:
            right = 5
        upward = ((right + 1) & 2) == 0
        for vertical in range(_SIZE):
            y = _SIZE - 1 - vertical if upward else vertical
            for offset in range(2):
                x = right - offset
                if not function[y][x]:
                    value = bits[bit_index] != 0 if bit_index < len(bits) else False
                    bit_index += 1
                    modules[y][x] = value ^ _mask_bit(mask, x, y)
        right -= 2
    mutable: List[List[Optional[bool]]] = [[value for value in row] for row in modules]
    mutable_function = [list(row) for row in function]
    _draw_format(mutable, mutable_function, mask)
    return [[bool(value) for value in row] for row in mutable]


def _penalty(modules: Sequence[Sequence[bool]]) -> int:
    score = 0
    # Runs in rows and columns.
    for axis in range(2):
        for outer in range(_SIZE):
            run_color = False
            run_length = 0
            for inner in range(_SIZE):
                value = modules[outer][inner] if axis == 0 else modules[inner][outer]
                if inner == 0 or value != run_color:
                    run_color = value
                    run_length = 1
                else:
                    run_length += 1
                    if run_length == 5:
                        score += 3
                    elif run_length > 5:
                        score += 1
    # 2x2 blocks.
    for y in range(_SIZE - 1):
        for x in range(_SIZE - 1):
            value = modules[y][x]
            if modules[y][x + 1] == value and modules[y + 1][x] == value and modules[y + 1][x + 1] == value:
                score += 3
    # Finder-like patterns with four white modules on either side.
    pattern = (True, False, True, True, True, False, True)
    for axis in range(2):
        for outer in range(_SIZE):
            line = [modules[outer][inner] if axis == 0 else modules[inner][outer] for inner in range(_SIZE)]
            for index in range(_SIZE - 6):
                if tuple(line[index : index + 7]) == pattern:
                    before = index >= 4 and not any(line[index - 4 : index])
                    after = index + 11 <= _SIZE and not any(line[index + 7 : index + 11])
                    if before or after:
                        score += 40
    dark = sum(1 for row in modules for value in row if value)
    total = _SIZE * _SIZE
    score += (abs(dark * 20 - total * 10) // total) * 10
    return score


def qr_matrix(payload: str) -> List[List[bool]]:
    """Return a decodable version 5-L QR matrix for ``payload``."""

    data = _codewords(payload)
    base, function = _base_matrix()
    candidates = [_draw_data(base, function, data, mask) for mask in range(8)]
    return min(candidates, key=_penalty)


def qr_svg(payload: str, *, scale: int = 10, border: int = 4, title: str = "Uriel verification QR") -> str:
    if scale < 1 or border < 0:
        raise ValueError("invalid QR scale or border")
    matrix = qr_matrix(payload)
    dimension = (_SIZE + border * 2) * scale
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {0} {0}" width="{0}" height="{0}" role="img" aria-label="{1}">'.format(
            dimension, html.escape(title, quote=True)
        ),
        "<title>{0}</title>".format(html.escape(title)),
        '<rect width="100%" height="100%" fill="white"/>',
        '<path fill="black" d="',
    ]
    commands: List[str] = []
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                px = (x + border) * scale
                py = (y + border) * scale
                commands.append("M{0},{1}h{2}v{2}h-{2}z".format(px, py, scale))
    parts.append("".join(commands))
    parts.extend(['"/>', "</svg>"])
    return "".join(parts) + "\n"
