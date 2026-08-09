"""된소리 ㄲ·로마자 모드·괄호·별표."""

from korean_exam_braille.app.braille.translator import hangul_text_to_ascii
from korean_exam_braille.app.brf.reverse_translator import reverse_translate_line as r


def test_kk_via_tensed_gieul():
    assert r(",`<.o") == "까지"
    assert r(",@<.o") == "까지"
    assert r(".),`<.ocz") == "전까지는"
    assert r(",ir,`<.o") == "때까지"


def test_kk_via_tensed_ga_abbrev():
    # 된소리표 + 가약자($) → 까
    assert r(",$<.o") == "까지"
    assert r(",$") == "까"


def test_roman_acronym_each_capital():
    assert r("0,e,x,w") == "EXW"
    assert r("0,f,o,b") == "FOB"
    assert r("0,c,i,f") == "CIF"
    assert r("0,d,d,p") == "DDP"


def test_roman_end_sign_before_hangul():
    """로마 뒤 한글 앞에는 종료표(4/⠲). 끝만 로마면 생략."""
    assert hangul_text_to_ascii("FOB") == "0,f,o,b"
    assert hangul_text_to_ascii("FOB LA항") == "0,f,o,b ,l,a4j7"
    assert hangul_text_to_ascii("EXW또는") == "0,e,x,w4,iucz"
    assert hangul_text_to_ascii("EXW와") == "0,e,x,w4v"
    assert hangul_text_to_ascii("FOB 조건") == "0,f,o,b4 .u`)"
    assert r("0,f,o,b ,l,a4j7") == "FOB LA항"
    assert r("0,e,x,w4,iucz") == "EXW또는"
    assert r(hangul_text_to_ascii("제시하며, ‘FOB LA항’")) == "제시하며, ‘FOB LA항’"


def test_roman_word_caps_double_comma():
    assert r("0,,exw") == "EXW"


def test_roman_particle_after_acronym():
    assert r("0,e,x,wv") == "EXW와"
    assert r("0,e,x,w4v") == "EXW와"
    assert r("0,d,d,pcz") == "DDP는"
    assert "Fob." not in r("0,f,o,bcz")
    assert r("0,f,o,bcz") == "FOB는"
    assert r("0,f,o,b4cz") == "FOB는"


def test_roman_phrase_with_parens():
    a = hangul_text_to_ascii("EXW(Ex Works)")
    assert r(a) == "EXW(Ex Works)"
    a2 = hangul_text_to_ascii("FOB(Free On Board)")
    assert r(a2) == "FOB(Free On Board)"
    a3 = hangul_text_to_ascii("CIF(Cost, Insurance and Freight)")
    assert r(a3) == "CIF(Cost, Insurance and Freight)"


def test_legacy_hyphen_parens_in_roman():
    # 구관례: 괄호를 '-' 로 쓴 경우
    assert r("0,e,x,w-0,ex 0,works-") == "EXW(Ex Works)"


def test_asterisk_and_circled_c():
    assert r("99") == "※"
    assert hangul_text_to_ascii("*") in ("99", "*")
    assert hangul_text_to_ascii("통관* 비용").find("99") >= 0
    assert "※" in r(hangul_text_to_ascii("통관* 비용")) or "*" in r(
        hangul_text_to_ascii("통관* 비용")
    )
    assert r("7c7") == "ⓒ"
    assert "ⓒ" in r(hangul_text_to_ascii("ⓒ 분담하는"))
