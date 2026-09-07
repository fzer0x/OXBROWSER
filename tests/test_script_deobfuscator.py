import pytest
from engine.anti_bot_deobfuscator import AntiBotScriptDeobfuscator


def test_deobfuscator_normalize_hex():
    deob = AntiBotScriptDeobfuscator.get_instance()
    # \x77\x65\x62\x67\x6c -> webgl
    obfuscated = 'function check(){ return window["\\x77\\x65\\x62\\x67\\x6c"]; }'
    clean = deob.normalize_hex_literals(obfuscated)
    assert "webgl" in clean
    assert "\\x77" not in clean


def test_deobfuscator_resolve_string_arrays():
    deob = AntiBotScriptDeobfuscator.get_instance()
    obfuscated = """
    var _0x1a = ['navigator', 'webdriver', 'plugins'];
    if (window[_0x1a[0]][_0x1a[1]]) {
        throw new Error('Bot detected');
    }
    """
    resolved = deob.resolve_string_arrays(obfuscated)
    assert "'navigator'" in resolved
    assert "'webdriver'" in resolved


def test_analyze_script_probes():
    deob = AntiBotScriptDeobfuscator.get_instance()
    sample_payload = """
    var _0x9b = ['\\x6e\\x61\\x76\\x69\\x67\\x61\\x74\\x6f\\x72\\x2e\\x77\\x65\\x62\\x64\\x72\\x69\\x76\\x65\\x72', 'toDataURL'];
    function audit() {
        const a = _0x9b[0];
        const b = canvas[_0x9b[1]]();
        const gl = canvas.getContext('webgl');
        gl.getParameter(gl.UNMASKED_RENDERER_WEBGL);
    }
    """
    report = deob.analyze_script(sample_payload)
    assert report.is_analyzed is True
    assert report.total_probes_detected >= 3
    assert "navigator.webdriver" in report.detected_apis
    assert "todataurl" in report.detected_apis
    assert "unmasked_renderer_webgl" in report.detected_apis
    assert report.risk_score > 0.3
