Log in

Sign up
You said:
from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
import PyPDF2
import os
import json
import re
import urllib.parse
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

def load_json_file(file_name):
    file_path = os.path.join(os.path.dirname(__file__), file_name)
    with open(file_path, "r") as file:
        return json.load(file)

def load_jobs():
    return load_json_file("jobs.json")

def extract_skills_from_pdf(file_path):
    skills = []
    with open(file_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"

    lines = text.splitlines()
    skills_section_found = False

    for line in lines:
        line = line.strip()
        
        if 'skills' in line.lower(): 
            skills_section_found = True
            continue

        if skills_section_found and line: 
            skills.extend([skill.strip() for skill in line.split(',')])
        
        if not line and skills_section_found:
            break

    return skills  

def tokenize(text):
    tokens = re.findall(r'\b\w+\b', text.lower())
    return tokens

@app.route('/')
def home():
    return send_file('dashboard.html')

@app.route('/<page>')
def render_page(page):
    if page in ['resume', 'learn', 'chat']:
        return send_file(f'{page}.html')
    return "Page not found", 404

def generate_job_search_url(skills):
    # Generate job search URL based on skills
    technical_keywords = ['javascript', 'node.js', 'react', 'mongodb', 'python', 'java', 'c', 'c++', 'html', 'css', 'backend', 'frontend', 'fullstack', 'web development', 'programming', 'software', 'devops', 'sql']
    non_technical_keywords = ['management', 'sales', 'marketing', 'hr', 'customer service', 'administrative', 'communication', 'creative', 'business']
    
    is_technical = any(skill.lower() in technical_keywords for skill in skills)
    
    base_url = "https://www.google.com/search"
    
    if is_technical:
        job_types = [
            "fullstack developer jobs",
            "backend developer jobs", 
            "devops jobs",
            "software engineer jobs",
            "web developer jobs"
        ]
        apply_button = True
    else:
        job_types = [
            "general office jobs",
            "sales jobs", 
            "customer service jobs",
            "administrative jobs", 
            "creative jobs"
        ]
        apply_button = False
    
    search_params = {
        "q": " OR ".join(job_types),
        "udm": "8",
        "sa": "X"
    }
    
    return {
        "job_search_url": f"{base_url}?{urllib.parse.urlencode(search_params)}",
        "apply_button": apply_button,
        "job_types": job_types
    }

@app.route('/extract_skills', methods=['POST'])
def extract_skills():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    print(f"File uploaded: {file.filename}")  # Debug log
    file_path = os.path.join('uploads', file.filename)
    file.save(file_path)

    skills_text = extract_skills_from_pdf(file_path)
    
    extracted_tokens = set()
    for skill in skills_text:
        extracted_tokens.update(tokenize(skill))  

    job_listings = load_jobs()

    recommended_jobs = []
    
    for job in job_listings:
        job_tokens = set()
        
        job_tokens.update(tokenize(job.get('job_title', '')))
        job_tokens.update(tokenize(job.get('job_description', '')))
        job_tokens.update(tokenize(job.get('experience_level', '')))
        job_tokens.update(tokenize(job.get('location', '')))
        job_tokens.update(tokenize(job.get('company_name', '')))
        
        for skill in job.get('skills', []):
            job_tokens.update(tokenize(skill))
        
        matched_tokens = extracted_tokens.intersection(job_tokens)

        if matched_tokens:  
            match_percentage = round((len(matched_tokens) / len(job_tokens)) * 100, 2)  
            recommended_jobs.append({
                "job": job,
                "match_percentage": match_percentage,
                "matched_tokens": list(matched_tokens)  
            })

    recommended_jobs.sort(key=lambda x: x['match_percentage'], reverse=True)

    # Generate job search URL and apply button flag
    job_search_info = generate_job_search_url(skills_text)

    os.remove(file_path)

    return jsonify({
        'jobs': recommended_jobs,
        'job_search_url': job_search_info['job_search_url'],
        'show_apply_button': job_search_info['apply_button']
    })

if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')

genai.configure(api_key="AIzaSyBADqoFQCnC5njtkGrEciTyzSug9hRck9A")
model = genai.GenerativeModel(model_name="gemini-1.5-flash")

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message', '')
    
    # Customize prompt for job-related context
    job_context = """
    You are a professional job assistant. Provide helpful, concise, and 
    professional advice about job searching, resume writing, interview preparation, 
    career development, and workplace skills. Tailor your responses to be 
    constructive and supportive.
    
    User's query:
    """
    
    full_prompt = job_context + user_message
    
    try:
        # Generate response using Gemini
        response = model.generate_content(full_prompt)
        
        return jsonify({
            'status': 'success', 
            'message': response.text
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error', 
            'message': str(e)
        })

    app.run(debug=True)
