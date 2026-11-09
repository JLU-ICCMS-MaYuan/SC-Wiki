"""#136：GROBID健康、题录及旧引用入口必须真实到达本机服务。"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

import pytest


@pytest.mark.parametrize('url,expected', [
    ('http://127.0.0.1:8070', False), ('http://127.0.0.2:8070', False),
    ('http://LOCALHOST.:8070', False), ('http://[::1]:8070', False),
    ('https://grobid.example.org', True), ('http://grobid:8070', True),
    ('https://localhost.example.org', True), ('http://192.168.1.10:8070', True),
])
def test_only_loopback_service_bypasses_environment_proxy(url, expected):
    from backend.services.http_transport import uses_environment_proxy
    assert uses_environment_proxy(url) is expected


@pytest.mark.parametrize('entry', ['health', 'document', 'references'])
def test_loopback_grobid_is_not_sent_to_external_proxy(tmp_path, monkeypatch, entry):
    xml = b'''<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc>
      <titleStmt><title>Current paper</title></titleStmt></fileDesc></teiHeader>
      <text><back><listBibl><biblStruct xml:id="b0"><analytic><title>Source reference</title>
      </analytic><note type="raw_reference">Original reference</note></biblStruct>
      </listBibl></back></text></TEI>'''
    hits = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            hits.append(self.path)
            self.send_response(200); self.end_headers()
            self.wfile.write(b'true' if self.path.endswith('isalive') else b'fixture-version')
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            hits.append(self.path)
            self.send_response(200); self.end_headers(); self.wfile.write(xml)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    endpoint = f'http://127.0.0.1:{server.server_port}'
    monkeypatch.setenv('GROBID_URL', endpoint)
    for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        monkeypatch.setenv(key, 'http://127.0.0.1:1')
    for key in ('NO_PROXY', 'no_proxy'): monkeypatch.setenv(key, '')
    pdf = tmp_path / 'source.pdf'; pdf.write_bytes(b'%PDF-original-input')
    try:
        from backend.ingest.grobid_document import service_available, extract_document
        from backend.ingest.document_parsers import DocumentSource
        from backend.services.citation_graph import extract_references_from_pdf
        if entry == 'health':
            assert service_available() is True
            assert hits == ['/api/isalive']
        elif entry == 'document':
            result = extract_document(DocumentSource(pdf, 'file'), tmp_path / 'grobid')
            assert result['status'] == 'succeeded'
            assert result['metadata']['title'] == 'Current paper'
            assert len(result['references']) == 1
            assert hits == ['/api/version', '/api/processFulltextDocument']
        else:
            result = extract_references_from_pdf(pdf)
            assert result['status'] == 'succeeded'
            assert len(result['references']) == 1
            assert hits == ['/api/processFulltextDocument?consolidateCitations=0']
    finally:
        server.shutdown(); server.server_close()
