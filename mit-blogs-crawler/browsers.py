"""Two actual browser backends; no requests-only fallback."""
import os
import socket
import tempfile
from contextlib import contextmanager
from urllib.parse import unquote, urlsplit

USER_AGENT = "MITBlogsCourseCrawler/1.0"


@contextmanager
def browser_backend(engine, executable=None, headed=False):
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if engine == "playwright":
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            options = {"headless": not headed, "args": ["--no-sandbox"]}
            if executable:
                options["executable_path"] = executable
            if proxy:
                parsed = urlsplit(proxy)
                options["proxy"] = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port or 80}", "bypass": "localhost,127.0.0.1"}
                if parsed.username:
                    options["proxy"].update(username=unquote(parsed.username), password=unquote(parsed.password or ""))
            browser = p.chromium.launch(**options)
            try:
                page = browser.new_page(user_agent=USER_AGENT)
                class PlaywrightBrowser:
                    def get(self, url):
                        response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                        if not response or not response.ok:
                            raise RuntimeError(f"HTTP {response.status if response else 'unknown'} at {url}")
                        page.wait_for_function("document.readyState !== 'loading'")
                        return page.content(), page.locator("body").inner_text()
                yield PlaywrightBrowser()
            finally:
                browser.close()
    else:
        from DrissionPage import ChromiumOptions, ChromiumPage
        # DrissionPage's local DevTools connection must not use the outbound proxy.
        for name in ("NO_PROXY", "no_proxy"):
            os.environ[name] = ",".join(filter(None, [os.environ.get(name), "localhost", "127.0.0.1"]))
        with tempfile.TemporaryDirectory(prefix="mit-blogs-chrome-") as profile:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            options = ChromiumOptions().set_user_data_path(profile).set_local_port(port).headless(not headed)
            options.set_argument("--no-sandbox")
            options.set_user_agent(USER_AGENT)
            if executable:
                options.set_browser_path(executable)
            if proxy:
                parsed = urlsplit(proxy)
                if parsed.username or parsed.password:
                    raise RuntimeError("DrissionPage requires a browser-compatible proxy without embedded authentication")
                options.set_proxy(proxy)
            page = ChromiumPage(options)
            try:
                class DrissionBrowser:
                    def get(self, url):
                        page.listen.start(targets=True, is_regex=False, method=True, res_type="Document")
                        try:
                            if not page.get(url, retry=0, timeout=45):
                                raise RuntimeError(f"Navigation failed at {url}")
                            packet = page.listen.wait(timeout=10)
                            if not packet or packet.is_failed:
                                raise RuntimeError(f"No successful document response at {url}")
                            if packet.response.status >= 400:
                                raise RuntimeError(f"HTTP {packet.response.status} at {url}")
                            return page.html, page.run_js("return document.body.innerText;")
                        finally:
                            page.listen.stop()
                yield DrissionBrowser()
            finally:
                page.quit()
