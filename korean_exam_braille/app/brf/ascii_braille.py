"""BRF ASCII ↔ 유니코드 점자 변환.

표준 Braille ASCII(6점, 64셀) 대응표를 사용한다.
참고: https://en.wikipedia.org/wiki/Braille_ASCII
"""

from __future__ import annotations

# index = Unicode U+2800 + i 에 대응하는 ASCII 문자 (소문자 기준)
BRAILLE_ASCII_TABLE = (
    " a1b'k2l@cif/msp\"e3h9o6r^djg>ntq,*5<-u8v.%[$+x!&;:4\\0z7(_?w]#y)="
)

assert len(BRAILLE_ASCII_TABLE) == 64

FORM_FEED = "\x0c"
LINE_ENDING_CHARS = frozenset({"\n", "\r"})

_ASCII_TO_DOTS: dict[str, int] = {}
_DOTS_TO_ASCII: dict[int, str] = {}

for _dots, _ch in enumerate(BRAILLE_ASCII_TABLE):
    _ASCII_TO_DOTS[_ch] = _dots
    _DOTS_TO_ASCII[_dots] = _ch
    upper = _ch.upper()
    if upper != _ch and upper not in _ASCII_TO_DOTS:
        _ASCII_TO_DOTS[upper] = _dots

# 국내 BRF에서 초성 ㄱ(⠈, @)을 백틱(`)으로 쓰는 관례가 있음
_ASCII_ALIASES: dict[str, str] = {
    "`": "@",
}
for _alias, _canonical in _ASCII_ALIASES.items():
    _ASCII_TO_DOTS[_alias] = _ASCII_TO_DOTS[_canonical]


def normalize_brf_ascii(text: str) -> str:
    """국내 BRF 확장 문자를 표준 Braille ASCII로 정규화."""
    return "".join(_ASCII_ALIASES.get(ch, ch) for ch in text)


def is_braille_ascii_char(ch: str) -> bool:
    if len(ch) != 1:
        return False
    return ch in _ASCII_TO_DOTS


def ascii_char_to_dots(ch: str) -> int:
    """ASCII 한 글자를 6점 비트마스크(dot1=bit0 … dot6=bit5)로 변환."""
    if ch not in _ASCII_TO_DOTS:
        raise ValueError(f"unsupported BRF ASCII character: {ch!r}")
    return _ASCII_TO_DOTS[ch]


def dots_to_ascii_char(dots: int) -> str:
    dots &= 0x3F
    return _DOTS_TO_ASCII[dots]


def ascii_char_to_unicode(ch: str) -> str:
    return chr(0x2800 + ascii_char_to_dots(ch))


def unicode_char_to_ascii(ch: str) -> str:
    code = ord(ch)
    if 0x2800 <= code <= 0x283F:
        return dots_to_ascii_char(code - 0x2800)
    if 0x2840 <= code <= 0x28FF:
        # 8점 셀은 하위 6점만 BRF ASCII로 사상
        return dots_to_ascii_char((code - 0x2800) & 0x3F)
    raise ValueError(f"not a braille unicode character: {ch!r}")


def ascii_to_unicode(text: str, *, unknown: str = "�") -> str:
    """BRF ASCII 문자열을 유니코드 점자로 변환. 개행·폼피드는 보존."""
    out: list[str] = []
    for ch in text:
        if ch in LINE_ENDING_CHARS or ch == FORM_FEED:
            out.append(ch)
        elif ch in _ASCII_TO_DOTS:
            out.append(ascii_char_to_unicode(ch))
        else:
            out.append(unknown)
    return "".join(out)


def unicode_to_ascii(text: str, *, unknown: str = "?") -> str:
    """유니코드 점자를 BRF ASCII로 변환. 개행·폼피드는 보존."""
    out: list[str] = []
    for ch in text:
        if ch in LINE_ENDING_CHARS or ch == FORM_FEED:
            out.append(ch)
        elif 0x2800 <= ord(ch) <= 0x28FF:
            out.append(unicode_char_to_ascii(ch))
        elif ch in _ASCII_TO_DOTS:
            # 이미 ASCII인 경우 소문자 정규화
            dots = _ASCII_TO_DOTS[ch]
            out.append(_DOTS_TO_ASCII[dots])
        else:
            out.append(unknown)
    return "".join(out)


def roundtrip_ok(text: str) -> bool:
    """지원 ASCII만 포함한 문자열이 왕복 변환에서 보존되는지 확인."""
    uni = ascii_to_unicode(text, unknown="\0")
    if "\0" in uni:
        return False
    back = unicode_to_ascii(uni)
    normalized = "".join(
        _DOTS_TO_ASCII[_ASCII_TO_DOTS[ch]] if ch in _ASCII_TO_DOTS else ch for ch in text
    )
    return back == normalized
