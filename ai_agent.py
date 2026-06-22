import os
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", 8080))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"idobetz AI Agent Running!")
    def do_POST(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"success":true}')
    def log_message(self, format, *args):
        pass

print("Starting on port " + str(PORT))
HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
