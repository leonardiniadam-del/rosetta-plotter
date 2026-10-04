from rosetta.flatten import flatten, flatten_with_report
from rosetta.issues import MESSAGES, pdf_text_issue, scan_document, scan_shapes, scan_skipped
from rosetta.svgdoc import normalize
from tests import samples

SVG_OPEN = (b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            b'width="100mm" height="100mm" viewBox="0 0 100 100">')
LINE = b'<line x2="10" stroke="black"/>'


def _codes(issues):
    return {issue.code: issue.count for issue in issues}


def test_text_and_images_come_from_what_ems_skipped():
    report = flatten_with_report(normalize(samples.WITH_PROBLEMS))
    assert _codes(scan_skipped(report.skipped)) == {"text": 1, "image": 1}


def test_text_reached_through_use_is_reported():
    raw = SVG_OPEN + b'<defs><text id="t">Hi</text></defs><use xlink:href="#t"/>' + LINE + b"</svg>"
    assert "text" in _codes(scan_skipped(flatten_with_report(normalize(raw)).skipped))


def test_hidden_text_is_not_reported():
    raw = SVG_OPEN + b'<text display="none">Hi</text>' + LINE + b"</svg>"
    assert scan_skipped(flatten_with_report(normalize(raw)).skipped) == []


def test_other_unsupported_elements_are_reported():
    raw = SVG_OPEN + b'<svg x="0" y="0" width="5" height="5">' + LINE + b"</svg>" + LINE + b"</svg>"
    assert _codes(scan_skipped(flatten_with_report(normalize(raw)).skipped)) == {"unsupported": 1}


def test_document_scan_counts_clips_outside_defs():
    doc = normalize(samples.WITH_PROBLEMS)
    assert _codes(scan_document(doc.root, doc.source)) == {"clip": 1}


def test_clip_path_none_is_not_a_clip():
    doc = normalize(SVG_OPEN + b'<g clip-path="none">' + LINE + b"</g></svg>")
    assert scan_document(doc.root, doc.source) == []


def test_clip_not_reported_for_pdf_sources():
    doc = normalize(samples.WITH_PROBLEMS, source_hint="pdf")
    assert "clip" not in _codes(scan_document(doc.root, doc.source))


def test_affinity_clip_rule_is_not_a_clip():
    doc = normalize(samples.AFFINITY_EXPORT)
    assert scan_document(doc.root, doc.source) == []


def test_clip_set_through_css_is_detected():
    raw = (b'<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" viewBox="0 0 10 10">'
           b'<style>.m{clip-path:url(#c)}</style><g class="m"><line x2="10" stroke="black"/></g></svg>')
    doc = normalize(raw)
    assert _codes(scan_document(doc.root, doc.source)) == {"clip": 1}


def test_shape_scan_counts_fill_only_and_white():
    shapes = flatten(normalize(samples.WITH_PROBLEMS))
    codes = _codes(scan_shapes(shapes))
    assert codes["white"] == 1
    assert codes["fill_only"] == 1  # green circle; the white background counts as white only


def test_near_white_counts_as_white():
    raw = SVG_OPEN + b'<rect width="100" height="100" fill="#fefefe"/>' + LINE + b"</svg>"
    codes = _codes(scan_shapes(flatten(normalize(raw))))
    assert codes == {"white": 1}


def test_clean_file_has_no_shape_issues():
    assert scan_shapes(flatten(normalize(samples.INKSCAPE_MM))) == []


def test_empty_is_blocking():
    issues = scan_shapes([])
    assert len(issues) == 1
    assert issues[0].code == "empty" and issues[0].blocking


def test_pdf_text_issue_and_plain_messages():
    assert pdf_text_issue().code == "pdf_text"
    for message in MESSAGES.values():
        assert message.endswith(".")
