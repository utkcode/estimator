"""LLM processing service for Gemini API"""
import os
import json
import pandas as pd
import google.generativeai as genai

# Configure Gemini API
api_key = os.getenv('GEMINI_API_KEY', '')
if not api_key:
    print("Warning: GEMINI_API_KEY not set. LLM features will not work.")
genai.configure(api_key=api_key)

def get_available_model():
    """Get an available Gemini model"""
    model_candidates = [
        'gemini-1.5-flash',
        'gemini-1.5-flash-001',
        'gemini-1.5-flash-002',
        'gemini-1.5-pro',
        'gemini-1.5-pro-001',
        'gemini-1.5-pro-002',
        'gemini-pro',
        'gemini-2.0-flash-exp',
        'gemini-2.5-flash',
    ]
    
    try:
        models = genai.list_models()
        available_model_names = []
        
        for model in models:
            if 'generateContent' in model.supported_generation_methods:
                model_name = model.name
                if '/' in model_name:
                    model_name = model_name.split('/')[-1]
                available_model_names.append(model_name)
                
                if 'flash' in model_name.lower():
                    return model_name
        
        for model in models:
            if 'generateContent' in model.supported_generation_methods:
                model_name = model.name
                if '/' in model_name:
                    model_name = model_name.split('/')[-1]
                if 'pro' in model_name.lower() or 'gemini' in model_name.lower():
                    return model_name
        
        if available_model_names:
            return available_model_names[0]
    except Exception as e:
        pass
    
    for model_name in model_candidates:
        try:
            test_model = genai.GenerativeModel(model_name)
            return model_name
        except Exception as test_error:
            continue
    
    raise Exception(
        "No available Gemini models found. Please check your API key and ensure you have access to Gemini models. "
        "Visit https://makersuite.google.com/app/apikey to verify your API key."
    )

def read_document_content(doc_path):
    """Read document content based on file type"""
    file_ext = doc_path.rsplit('.', 1)[1].lower() if '.' in doc_path else ''
    
    if file_ext == 'txt':
        with open(doc_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    elif file_ext == 'docx':
        try:
            from docx import Document
            doc = Document(doc_path)
            return '\n'.join([paragraph.text for paragraph in doc.paragraphs])
        except ImportError:
            with open(doc_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
    elif file_ext == 'pdf':
        try:
            import PyPDF2
            with open(doc_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                return '\n'.join([page.extract_text() for page in pdf_reader.pages])
        except ImportError:
            with open(doc_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
    else:
        with open(doc_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

def process_llm1(doc_path):
    """LLM1: Extract products and features from document"""
    try:
        doc_content = read_document_content(doc_path)
        model_name = get_available_model()
        model = genai.GenerativeModel(model_name)
        
        max_doc_length = 20000
        if len(doc_content) > max_doc_length:
            doc_content = doc_content[:max_doc_length]
        
        prompt = f"""Analyze the following document and extract all products and their associated features.

Document content:
{doc_content}

Please provide the output in a structured format as a table with exactly 2 columns:
1. Product
2. Features

Format the output as a JSON array of objects, where each object has "product" and "features" keys.
Example format:
[
  {{"product": "Product Name 1", "features": "Feature 1, Feature 2, Feature 3"}},
  {{"product": "Product Name 2", "features": "Feature A, Feature B"}}
]

Only return the JSON array, no additional text."""
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
        response_text = response_text.strip()
        
        products_features = json.loads(response_text)
        return products_features
        
    except Exception as e:
        raise Exception(f"LLM1 processing error: {str(e)}")

def process_llm2(products_features, scope_config_path):
    """LLM2: Add size estimation using scope config"""
    try:
        if scope_config_path.endswith('.csv'):
            df = pd.read_csv(scope_config_path)
        else:
            df = pd.read_excel(scope_config_path)
        
        max_rows = 100
        if len(df) > max_rows:
            df_sample = df.head(max_rows)
        else:
            df_sample = df
        
        if len(df_sample.columns) > 10:
            key_cols = []
            for col in df_sample.columns:
                col_lower = str(col).lower()
                if any(keyword in col_lower for keyword in ['epic', 'feature', 'requirement', 'size', 'small', 'medium', 'large', 'dev hours', 'hours']):
                    key_cols.append(col)
            if key_cols:
                df_sample = df_sample[key_cols]
        
        scope_config_text = df_sample.to_string()
        products_text = json.dumps(products_features, indent=2)
        
        model_name = get_available_model()
        model = genai.GenerativeModel(model_name)
        
        total_prompt_size = len(products_text) + len(scope_config_text)
        if total_prompt_size > 50000:
            max_scope_length = 30000
            scope_config_text = scope_config_text[:max_scope_length] + "\n... (truncated for size)"
        
        prompt = f"""You are an estimator. Based on the products and features extracted, and the scope configuration provided, estimate the size and development hours for each product-feature combination.

Products and Features extracted:
{products_text}

Scope Configuration (sample):
{scope_config_text}

Please provide the output as a JSON array of objects with 4 columns:
1. Product
2. Features
3. Size (estimated size based on the scope config: X-Small, Small, Medium, Large, or X-Large)
4. Hours (estimated development hours based on the scope config - provide a numeric value)

Format:
[
  {{"product": "Product Name 1", "features": "Feature 1, Feature 2", "size": "Small/Medium/Large or specific size", "hours": 8}},
  {{"product": "Product Name 2", "features": "Feature A, Feature B", "size": "Medium", "hours": 12}}
]

Important: Extract the hours from the scope configuration based on the size. If the scope config shows dev hours for different sizes, match the hours to the estimated size. Return numeric values for hours.

Only return the JSON array, no additional text."""
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
        response_text = response_text.strip()
        
        results = json.loads(response_text)
        return results
        
    except Exception as e:
        raise Exception(f"LLM2 processing error: {str(e)}")

