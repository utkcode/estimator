"""Main Flask application"""
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os
import csv
import io
from werkzeug.utils import secure_filename
from datetime import datetime
import google.generativeai as genai

from config import PROJECTS_FOLDER, SCOPE_CONFIG_FOLDER, ALLOWED_EXTENSIONS
from database import init_db, get_db_connection
from llm_service import process_llm1, process_llm2, get_available_model

app = Flask(__name__)
CORS(app)

# Initialize database
init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_scope_config_path():
    """Get the path to the scope config file"""
    if not os.path.exists(SCOPE_CONFIG_FOLDER):
        return None
    for ext in ['xlsx', 'xls', 'csv']:
        files = [f for f in os.listdir(SCOPE_CONFIG_FOLDER) if f.endswith(f'.{ext}')]
        if files:
            return os.path.join(SCOPE_CONFIG_FOLDER, files[0])
    return None

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/test-models', methods=['GET'])
def test_models():
    """Test and list available Gemini models"""
    try:
        models = genai.list_models()
        available_models = []
        for model in models:
            if 'generateContent' in model.supported_generation_methods:
                model_name = model.name.replace('models/', '')
                available_models.append({
                    'name': model_name,
                    'full_name': model.name,
                    'methods': list(model.supported_generation_methods)
                })
        
        try:
            model_name = get_available_model()
            return jsonify({
                'available_models': available_models,
                'selected_model': model_name,
                'status': 'success'
            })
        except Exception as e:
            return jsonify({
                'available_models': available_models,
                'error': str(e),
                'status': 'warning'
            }), 200
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error',
            'message': 'Could not list models. Check your API key.'
        }), 500

@app.route('/api/projects', methods=['GET'])
def get_projects():
    """Get all projects"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM projects ORDER BY created_at DESC')
    rows = cursor.fetchall()
    
    projects = []
    for row in rows:
        project = {
            'id': row['id'],
            'name': row['name'],
            'created_at': row['created_at'],
            'document_file': row['document_file'],
            'status': row['status']
        }
        if row['error']:
            project['error'] = row['error']
        projects.append(project)
    
    conn.close()
    return jsonify(projects)

@app.route('/api/projects', methods=['POST'])
def create_project():
    """Create a new project"""
    try:
        data = request.form
        project_name = data.get('project_name')
        if not project_name:
            return jsonify({'error': 'Project name is required'}), 400
        
        scope_config_path = get_scope_config_path()
        if not scope_config_path:
            return jsonify({'error': 'Scope config file is required. Please upload it first.'}), 400
        
        if 'file' not in request.files:
            return jsonify({'error': 'Document file is required'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400
        
        project_id = f"project_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        project_path = os.path.join(PROJECTS_FOLDER, project_id)
        os.makedirs(project_path, exist_ok=True)
        
        filename = secure_filename(file.filename)
        file_path = os.path.join(project_path, filename)
        file.save(file_path)
        
        created_at = datetime.now().isoformat()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO projects (id, name, created_at, document_file, status, file_path)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (project_id, project_name, created_at, filename, 'processing', file_path))
        
        conn.commit()
        conn.close()
        
        try:
            products_features = process_llm1(file_path)
            final_results = process_llm2(products_features, scope_config_path)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            for result in final_results:
                cursor.execute('''
                    INSERT INTO results (project_id, product, features, size, hours)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    project_id,
                    result.get('product', ''),
                    result.get('features', ''),
                    result.get('size', ''),
                    str(result.get('hours', '')) if result.get('hours') is not None else ''
                ))
            
            cursor.execute('UPDATE projects SET status = ? WHERE id = ?', ('completed', project_id))
            conn.commit()
            conn.close()
            
            project_info = {
                'id': project_id,
                'name': project_name,
                'created_at': created_at,
                'document_file': filename,
                'status': 'completed',
                'results': final_results
            }
            
        except Exception as e:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE projects SET status = ?, error = ? WHERE id = ?', ('error', str(e), project_id))
            conn.commit()
            conn.close()
            return jsonify({'error': f'Processing failed: {str(e)}'}), 500
        
        return jsonify(project_info), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects/<project_id>', methods=['GET'])
def get_project(project_id):
    """Get a specific project"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return jsonify({'error': 'Project not found'}), 404
    
    project_info = {
        'id': row['id'],
        'name': row['name'],
        'created_at': row['created_at'],
        'document_file': row['document_file'],
        'status': row['status']
    }
    
    if row['error']:
        project_info['error'] = row['error']
    
    cursor.execute('SELECT product, features, size, hours FROM results WHERE project_id = ?', (project_id,))
    result_rows = cursor.fetchall()
    
    results = []
    for result_row in result_rows:
        result = {
            'product': result_row['product'],
            'features': result_row['features'],
            'size': result_row['size'],
            'hours': result_row['hours'] if result_row['hours'] else None
        }
        results.append(result)
    
    if results:
        project_info['results'] = results
    
    conn.close()
    return jsonify(project_info)

@app.route('/api/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT file_path FROM projects WHERE id = ?', (project_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'error': 'Project not found'}), 404
        
        if row['file_path'] and os.path.exists(row['file_path']):
            try:
                os.remove(row['file_path'])
            except:
                pass
        
        cursor.execute('DELETE FROM projects WHERE id = ?', (project_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'message': 'Project deleted successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects/<project_id>/download-csv', methods=['GET'])
def download_project_csv(project_id):
    """Download project results as CSV"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT name FROM projects WHERE id = ?', (project_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'error': 'Project not found'}), 404
        
        project_name = row['name']
        
        cursor.execute('SELECT product, features, size, hours FROM results WHERE project_id = ?', (project_id,))
        result_rows = cursor.fetchall()
        
        if not result_rows:
            conn.close()
            return jsonify({'error': 'No results available for this project'}), 404
        
        results = []
        for result_row in result_rows:
            results.append({
                'product': result_row['product'],
                'features': result_row['features'],
                'size': result_row['size'],
                'hours': result_row['hours']
            })
        
        conn.close()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Product', 'Features', 'Size', 'Hours'])
        
        for item in results:
            writer.writerow([
                item.get('product', ''),
                item.get('features', ''),
                item.get('size', ''),
                item.get('hours', '')
            ])
        
        filename = f"{project_name}_results.csv"
        output.seek(0)
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scope-config', methods=['GET'])
def get_scope_config():
    """Check if scope config exists"""
    scope_config_path = get_scope_config_path()
    if scope_config_path:
        filename = os.path.basename(scope_config_path)
        return jsonify({'exists': True, 'filename': filename})
    return jsonify({'exists': False})

@app.route('/api/scope-config', methods=['POST'])
def upload_scope_config():
    """Upload scope config file"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if os.path.exists(SCOPE_CONFIG_FOLDER):
            for f in os.listdir(SCOPE_CONFIG_FOLDER):
                os.remove(os.path.join(SCOPE_CONFIG_FOLDER, f))
        
        filename = secure_filename(file.filename)
        file_path = os.path.join(SCOPE_CONFIG_FOLDER, filename)
        file.save(file_path)
        
        return jsonify({'message': 'Scope config uploaded successfully', 'filename': filename}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scope-config', methods=['DELETE'])
def delete_scope_config():
    """Delete scope config file"""
    try:
        scope_config_path = get_scope_config_path()
        if not scope_config_path:
            return jsonify({'error': 'No scope config file found'}), 404
        
        os.remove(scope_config_path)
        return jsonify({'message': 'Scope config deleted successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
