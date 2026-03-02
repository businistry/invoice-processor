#!/usr/bin/env python3
import os
import tempfile
import zipfile
import shutil
import uuid
from pathlib import Path

from flask import Flask, request, jsonify, send_file, render_template, after_this_request
from werkzeug.utils import secure_filename

from main import InvoiceProcessor

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload

# In-memory store: token -> zip file path
_downloads = {}


@app.route('/')
def index():
    return render_template(
        'index.html',
        has_openai_key=bool(os.environ.get('OPENAI_API_KEY')),
        has_anthropic_key=bool(os.environ.get('ANTHROPIC_API_KEY')),
    )


@app.route('/process', methods=['POST'])
def process_invoices():
    model = request.form.get('model', 'gpt-4o')
    hotel_code = request.form.get('hotel_code', 'STLMO').strip().upper()
    auto_detect = request.form.get('auto_detect', 'false') == 'true'
    api_key = request.form.get('api_key', '').strip() or None

    # Fall back to environment variable
    if not api_key:
        env_var = 'OPENAI_API_KEY' if model.startswith('gpt') else 'ANTHROPIC_API_KEY'
        api_key = os.environ.get(env_var)

    if not api_key:
        env_var = 'OPENAI_API_KEY' if model.startswith('gpt') else 'ANTHROPIC_API_KEY'
        return jsonify({'error': f'No API key provided. Set {env_var} or enter one in the form.'}), 400

    files = request.files.getlist('files')
    pdf_files = [f for f in files if f.filename and f.filename.lower().endswith('.pdf')]

    if not pdf_files:
        return jsonify({'error': 'No PDF files found in upload.'}), 400

    input_dir = tempfile.mkdtemp()
    output_dir = tempfile.mkdtemp()

    try:
        for f in pdf_files:
            safe_name = secure_filename(f.filename)
            f.save(os.path.join(input_dir, safe_name))

        gl_path = Path(__file__).parent / 'GL Codes2026.csv'
        processor = InvoiceProcessor(
            input_dir=input_dir,
            output_dir=output_dir,
            model=model,
            api_key=api_key,
            hotel_code=hotel_code,
            max_workers=4,
            auto_detect_hotel=auto_detect,
            gl_codes_path=str(gl_path),
        )
        processor.process_invoices()

        # Zip processed files
        _, zip_path = tempfile.mkstemp(suffix='.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for pdf in Path(output_dir).glob('*.pdf'):
                zf.write(pdf, pdf.name)

        token = str(uuid.uuid4())
        _downloads[token] = zip_path

        return jsonify({
            'processed': [
                {
                    'original': r['original_path'].name,
                    'renamed': r['filename'],
                    'vendor': r.get('vendor', ''),
                    'invoice_number': r.get('invoice_number', ''),
                    'hotel_code': r.get('used_hotel_code', hotel_code),
                }
                for r in processor.processed_files
            ],
            'failed': [
                {'file': r['file'].name, 'error': r['error']}
                for r in processor.failed_files
            ],
            'download_token': token,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        shutil.rmtree(input_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)


@app.route('/download/<token>')
def download_zip(token):
    zip_path = _downloads.pop(token, None)
    if not zip_path or not os.path.exists(zip_path):
        return 'Download not found or already used.', 404

    @after_this_request
    def cleanup(response):
        try:
            os.unlink(zip_path)
        except Exception:
            pass
        return response

    return send_file(
        zip_path,
        mimetype='application/zip',
        as_attachment=True,
        download_name='processed_invoices.zip',
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
