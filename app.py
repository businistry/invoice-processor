#!/usr/bin/env python3
import os
import uuid
import json
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
from main import InvoiceProcessor

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_for_testing')
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['PROCESSED_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'processed_invoices')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create necessary folders if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

# Session tracking for processing
SESSION_RESULTS = {}

@app.route('/')
def index():
    """Render the main dashboard page"""
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """Handle file uploads and processing"""
    if request.method == 'POST':
        # Check if any file was uploaded
        if 'invoices' not in request.files:
            flash('No file selected')
            return redirect(request.url)
            
        files = request.files.getlist('invoices')
        
        # Check if the file list is empty
        if not files or files[0].filename == '':
            flash('No file selected')
            return redirect(request.url)
            
        # Get form parameters
        hotel_code = request.form.get('hotel_code', 'STLMO')
        auto_detect = 'auto_detect' in request.form
        preview_mode = 'preview_mode' in request.form
        model = request.form.get('model', 'gpt-4o')
        
        # Create unique session ID for this batch
        session_id = str(uuid.uuid4())
        session['current_session'] = session_id
        
        # Create a temp directory for this upload session
        upload_session_dir = os.path.join(app.config['UPLOAD_FOLDER'], session_id)
        os.makedirs(upload_session_dir, exist_ok=True)
        
        # Save uploaded files
        saved_files = []
        for file in files:
            if file and file.filename.lower().endswith('.pdf'):
                filename = secure_filename(file.filename)
                file_path = os.path.join(upload_session_dir, filename)
                file.save(file_path)
                saved_files.append(file_path)
        
        if not saved_files:
            flash('No valid PDF files uploaded')
            return redirect(request.url)
        
        # Store session info
        SESSION_RESULTS[session_id] = {
            'status': 'processing',
            'files': saved_files,
            'params': {
                'hotel_code': hotel_code,
                'auto_detect': auto_detect,
                'preview_mode': preview_mode,
                'model': model
            },
            'results': []
        }
        
        # Start processing in a background thread
        import threading
        thread = threading.Thread(target=process_files, args=(session_id, saved_files, hotel_code, auto_detect, preview_mode, model))
        thread.daemon = True
        thread.start()
        
        return redirect(url_for('processing', session_id=session_id))
        
    return render_template('upload.html')

def process_files(session_id, files, hotel_code, auto_detect, preview_mode, model):
    """Process files in background"""
    try:
        processor = InvoiceProcessor(
            input_dir=os.path.dirname(files[0]),
            output_dir=app.config['PROCESSED_FOLDER'],
            model=model,
            api_key=None,  # Will use env variables
            hotel_code=hotel_code,
            batch_size=None,
            preview=preview_mode,
            max_workers=1,  # For web UI, process sequentially to avoid overloading
            auto_detect_hotel=auto_detect
        )
        
        # Process each file individually
        results = []
        for file_path in files:
            try:
                result = processor.process_invoice(Path(file_path))
                results.append(result)
            except Exception as e:
                results.append({
                    'success': False,
                    'original_path': file_path,
                    'error': str(e)
                })
        
        # Update session results
        SESSION_RESULTS[session_id]['status'] = 'completed'
        SESSION_RESULTS[session_id]['results'] = results
    except Exception as e:
        SESSION_RESULTS[session_id]['status'] = 'failed'
        SESSION_RESULTS[session_id]['error'] = str(e)

@app.route('/processing/<session_id>')
def processing(session_id):
    """Show processing status and results"""
    if session_id not in SESSION_RESULTS:
        flash('Invalid session ID')
        return redirect(url_for('index'))
        
    return render_template('processing.html', session_id=session_id)

@app.route('/api/status/<session_id>')
def status(session_id):
    """API endpoint to get processing status"""
    if session_id not in SESSION_RESULTS:
        return jsonify({'error': 'Invalid session ID'}), 404
        
    return jsonify(SESSION_RESULTS[session_id])

@app.route('/download/<session_id>')
def download(session_id):
    """Download processed files or show results page"""
    if session_id not in SESSION_RESULTS:
        flash('Invalid session ID')
        return redirect(url_for('index'))
        
    session_data = SESSION_RESULTS[session_id]
    
    return render_template(
        'results.html', 
        session_id=session_id,
        status=session_data['status'],
        results=session_data['results'],
        preview_mode=session_data['params']['preview_mode']
    )

@app.route('/settings')
def settings():
    """Settings page"""
    return render_template('settings.html')

@app.route('/api/download/<path:filename>')
def download_file(filename):
    """Download a processed file"""
    from flask import send_from_directory
    
    directory = os.path.dirname(filename)
    filename = os.path.basename(filename)
    
    return send_from_directory(directory, filename, as_attachment=True)

@app.route('/pricing')
def pricing():
    """Pricing page"""
    return render_template('pricing.html')

@app.route('/api-docs')
def api_docs():
    """API documentation page"""
    return render_template('api_docs.html')

@app.errorhandler(413)
def too_large(e):
    """Handle error when file is too large"""
    flash('File too large. Maximum size is 16MB.')
    return redirect(url_for('upload'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)