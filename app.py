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

# In-memory store: session_id -> { 'input_dir': path, 'output_dir': path, 'processor': InvoiceProcessor }
_sessions = {}


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
    stamp_template = request.files.get('stamp_template')

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

    if stamp_template and stamp_template.filename:
        stamp_name = secure_filename(stamp_template.filename)
        ext = os.path.splitext(stamp_name)[1].lower()
        if ext not in {'.png', '.jpg', '.jpeg'}:
            return jsonify({'error': 'Stamp template must be a PNG or JPG image.'}), 400

    input_dir = tempfile.mkdtemp()
    output_dir = tempfile.mkdtemp()
    stamp_template_path = None

    try:
        for f in pdf_files:
            safe_name = secure_filename(f.filename)
            f.save(os.path.join(input_dir, safe_name))


        if stamp_template and stamp_template.filename:
            stamp_name = secure_filename(stamp_template.filename)
            ext = os.path.splitext(stamp_name)[1].lower()
            stamp_template_path = os.path.join(input_dir, f"stamp_template{ext}")
            stamp_template.save(stamp_template_path)

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
            preview=True,
            stamp_template_path=stamp_template_path
        )
        processor.process_invoices()

        session_id = str(uuid.uuid4())
        _sessions[session_id] = {
            'input_dir': input_dir,
            'output_dir': output_dir,
            'processor': processor
        }

        return jsonify({
            'session_id': session_id,
            'processed': [
                {
                    'original': r['original_path'].name,
                    'renamed': r['filename'],
                    'vendor': r.get('vendor', ''),
                    'invoice_number': r.get('invoice_number', ''),
                    'hotel_code': r.get('used_hotel_code', hotel_code),
                    'placement': r.get('approval_block_placement', 'mid-middle'),
                    'ai_placement': r.get('ai_approval_block_placement', 'mid-middle'),
                    'thumbnail_base64': r.get('preview_thumbnail_base64'),
                }
                for r in processor.processed_files
            ],
            'failed': [
                {'file': r['file'].name, 'error': r['error']}
                for r in processor.failed_files
            ]
        })

    except Exception as e:
        shutil.rmtree(input_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)
        return jsonify({'error': str(e)}), 500


@app.route('/finalize', methods=['POST'])
def finalize_invoices():
    try:
        data = request.json
        session_id = data.get('session_id')
        placements = data.get('placements', {})
        click_points = data.get('click_points', {})
        apply_annotations = data.get('apply_annotations', True)

        if not session_id or session_id not in _sessions:
            return jsonify({'error': 'Invalid or expired session.'}), 400

        session = _sessions.pop(session_id)
        input_dir = session['input_dir']
        output_dir = session['output_dir']
        processor = session['processor']

        for file_info in processor.processed_files:
            original_path = file_info['original_path']
            new_path = file_info['new_path']
            point = click_points.get(original_path.name)

            # Override placement if provided
            placement = placements.get(original_path.name, file_info.get('approval_block_placement', 'mid-middle'))
            file_info['approval_block_placement'] = placement

            # If user clicked in preview, place block at that exact normalized point.
            if isinstance(point, dict) and 'x' in point and 'y' in point:
                file_info['approval_block_point'] = {
                    'x': point.get('x'),
                    'y': point.get('y'),
                }
            else:
                file_info.pop('approval_block_point', None)

            # Add approval block or copy renamed file without annotation
            if apply_annotations:
                processor._add_approval_block(original_path, new_path, file_info)
            else:
                shutil.copy2(original_path, new_path)

        # Zip processed files
        _, zip_path = tempfile.mkstemp(suffix='.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for pdf in Path(output_dir).glob('*.pdf'):
                zf.write(pdf, pdf.name)

        token = str(uuid.uuid4())
        _downloads[token] = zip_path

        shutil.rmtree(input_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)

        return jsonify({'download_token': token})

    except Exception as e:
        if 'input_dir' in locals():
            shutil.rmtree(input_dir, ignore_errors=True)
        if 'output_dir' in locals():
            shutil.rmtree(output_dir, ignore_errors=True)
        return jsonify({'error': str(e)}), 500


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
    port = int(os.environ.get('PORT', 6458))
    app.run(debug=False, host='0.0.0.0', port=port)
