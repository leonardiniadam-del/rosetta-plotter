from rosetta.flatten import flatten
from rosetta.issues import MESSAGES, pdf_text_issue, scan_document, scan_shapes
from rosetta.svgdoc import normalize
from tests import samples


def _codes(issues):
    return {issue.code: issue.count for issue in issues}


def test_document_scan_counts_text_image_clip_but_not_defs():
    doc = normalize(samples.WITH_PROBLEMS)
    assert _codes(scan_document(doc.root, doc.source)) == {"text": 1, "image": 1, "clip": 1}


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
    assert codes["fill_only"] == 2  # white background rect + green circle


def test_empty_is_blocking():
    issues = scan_shapes([])
    assert len(issues) == 1
    assert issues[0].code == "empty" and issues[0].blocking


def test_pdf_text_issue_and_plain_messages():
    assert pdf_text_issue().code == "pdf_text"
    for message in MESSAGES.values():
        assert message.endswith(".")
