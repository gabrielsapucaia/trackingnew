#!/usr/bin/env python3
"""
Servidor HTTP simples com suporte a POST para salvar arquivos JSON.
"""

import http.server
import socketserver
import json
import os
from urllib.parse import urlparse

PORT = 8888
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_POST(self):
        """Handle POST requests for saving files."""
        parsed_path = urlparse(self.path)

        if parsed_path.path == '/save_areas':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)

            try:
                # Parse JSON data
                data = json.loads(post_data.decode('utf-8'))

                # Save to file
                filepath = os.path.join(DIRECTORY, 'areas_carregamento.json')
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                # Send success response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = {'success': True, 'message': 'Arquivo salvo com sucesso'}
                self.wfile.write(json.dumps(response).encode('utf-8'))

                print(f"[SAVE] areas_carregamento.json salvo com sucesso")

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = {'success': False, 'message': str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))
                print(f"[ERROR] Erro ao salvar: {e}")
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

if __name__ == '__main__':
    with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
        print(f"Servidor iniciado em http://localhost:{PORT}")
        print(f"Diretório: {DIRECTORY}")
        print(f"Endpoints:")
        print(f"  GET  /* - Arquivos estáticos")
        print(f"  POST /save_areas - Salvar areas_carregamento.json")
        print()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor encerrado.")
