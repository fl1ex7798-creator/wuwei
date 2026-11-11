"""Exercise both real browser engines against a local synthetic article, not MIT."""
import http.server
import os
import shutil
import threading
from pathlib import Path

from browsers import browser_backend
from parser import BASE, extract_article


def main():
    html = (Path(__file__).parent / 'fixtures' / 'article.html').read_bytes()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        executable = os.environ.get('CHROME_PATH') or shutil.which('chromium') or shutil.which('google-chrome')
        for engine in ['playwright', 'drissionpage']:
            with browser_backend(engine, executable) as browser:
                document, _ = browser.get(f'http://127.0.0.1:{server.server_port}/')
                row = extract_article(document, BASE + 'entry/example/')
                assert row['Title'] == 'A title, with commas'
                print(engine, 'browser navigation and extraction passed', flush=True)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
