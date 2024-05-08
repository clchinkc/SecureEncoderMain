from flask import Flask, request, jsonify, send_from_directory, make_response, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
from dotenv import load_dotenv
import logging
import json

from encoder_decoder import encode_base64, decode_base64, encode_hex, decode_hex, encode_utf8, decode_utf8, encode_latin1, decode_latin1, encode_ascii, decode_ascii, encode_url, decode_url
from encryption_decryption import ensure_aes_key, aes_encrypt, aes_decrypt, ensure_rsa_public_key, ensure_rsa_private_key, rsa_encrypt, rsa_decrypt

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
CORS(app)  # Enable CORS for all domains
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'keys')
app.config['ALLOWED_EXTENSIONS'] = {'pem'}
app.secret_key = os.urandom(24)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/upload_key', methods=['POST'])
def upload_key():
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        return jsonify({'message': 'File uploaded successfully', 'filename': filename}), 200
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/files', methods=['GET'])
def list_files():
    files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if os.path.isfile(os.path.join(app.config['UPLOAD_FOLDER'], f))]
    return jsonify(files)

@app.route('/download_key/<filename>')
def download_key(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404


@app.route('/process_text', methods=['POST'])
def process_text():
    data = request.get_json()
    session['text'] = data['text']
    session['operation'] = data['operation']
    session['action'] = data['action']

    operations = {
        'encode': {
            'base64': encode_base64,
            'hex': lambda x: encode_hex(x).hex(),
            'utf8': lambda x: encode_utf8(x).hex(),
            'latin1': lambda x: encode_latin1(x).hex(),
            'ascii': encode_ascii,
            'url': encode_url,
            'aes': lambda x: aes_encrypt(x, ensure_aes_key(os.path.join(app.config['UPLOAD_FOLDER'], "aes_key.pem"))).hex(),
            'rsa': lambda x: rsa_encrypt(x, ensure_rsa_public_key(os.path.join(app.config['UPLOAD_FOLDER'], "rsa_public_key.pem"))).hex(),
        },
        'decode': {
            'base64': decode_base64,
            'hex': lambda x: decode_hex(x),
            'utf8': lambda x: decode_utf8(bytes.fromhex(x)),
            'latin1': lambda x: decode_latin1(bytes.fromhex(x)),
            'ascii': decode_ascii,
            'url': decode_url,
            'aes': lambda x: aes_decrypt(bytes.fromhex(x), ensure_aes_key(os.path.join(app.config['UPLOAD_FOLDER'], "aes_key.pem"))).decode('utf-8'),
            'rsa': lambda x: rsa_decrypt(bytes.fromhex(x), ensure_rsa_private_key(os.path.join(app.config['UPLOAD_FOLDER'], "rsa_private_key.pem"))),
        }
    }

    try:
        operation_func = operations[session['action']][session['operation']]
        result = operation_func(session['text'])
        session['result'] = result
        return jsonify({'result': result})
    except KeyError as e:
        logging.error(f"Operation or action not found: {e}")
        return jsonify({'error': 'Invalid operation or action'}), 400
    except Exception as e:
        logging.error(f"Error processing text: {e}")
        return jsonify({'error': str(e)}), 500

@app.after_request
def apply_security_headers(response):
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; object-src 'none';"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

@app.after_request
def add_session_to_response(response):
    response.set_cookie('files', json.dumps(session.get('files', [])))
    response.set_cookie('result', session.get('result', ''))
    response.set_cookie('operation', session.get('operation', ''))
    response.set_cookie('action', session.get('action', ''))
    response.set_cookie('text', session.get('text', ''))
    return response

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('FLASK_PORT', '5000')))
