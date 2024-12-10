import io
from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
import json
import PyPDF2
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

def extract_skills_from_pdf(file):
    skills = []
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"

    lines = text.splitlines()

    for line in lines:
        line = line.strip()
        if 'skills' in line.lower():
            continue
        if line:  # If we found non-empty lines after "skills", consider them as skills
            skills.extend([skill.strip() for skill in line.split(',')])

    return skills

def tokenize(text):
    tokens = re.findall(r'\b\w+\b', text.lower())
    return tokens

def generate_job_search_url(skills):
    technical_keywords = ['javascript', 'node.js', 'react', 'mongodb', 'python', 'java', 'c', 'c++', 'html', 'css']
    non_technical_keywords = ['management', 'sales', 'marketing', 'hr', 'customer service']

    is_technical = any(skill.lower() in technical_keywords for skill in skills)
    
    base_url = "https://www.google.com/search"
    job_types = [
        "fullstack developer jobs" if is_technical else "sales jobs"
    ]

    search_params = {
        "q": " OR ".join(job_types),
        "udm": "8",
        "sa": "X"
    }

    return {
        "job_search_url": f"{base_url}?{urllib.parse.urlencode(search_params)}",
        "apply_button": is_technical,
        "job_types": job_types
    }

@app.route('/extract_skills', methods=['POST'])
def extract_skills():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    # Use in-memory file processing
    file_stream = io.BytesIO(file.read())

    # Extract skills from the uploaded PDF file
    skills_text = extract_skills_from_pdf(file_stream)
    extracted_tokens = set()

    for skill in skills_text:
        extracted_tokens.update(tokenize(skill))  

    job_listings = load_jobs()
    recommended_jobs = []

    for job in job_listings:
        job_tokens = set()
        job_tokens.update(tokenize(job.get('job_title', '')))
        job_tokens.update(tokenize(job.get('job_description', '')))

        matched_tokens = extracted_tokens.intersection(job_tokens)
        if matched_tokens:
            match_percentage = round((len(matched_tokens) / len(job_tokens)) * 100, 2)
            recommended_jobs.append({
                "job": job,
                "match_percentage": match_percentage,
                "matched_tokens": list(matched_tokens)
            })

    recommended_jobs.sort(key=lambda x: x['match_percentage'], reverse=True)

    job_search_info = generate_job_search_url(skills_text)

    return jsonify({
        'jobs': recommended_jobs,
        'job_search_url': job_search_info['job_search_url'],
        'show_apply_button': job_search_info['apply_button']
    })

@app.route('/<page>')
def render_page(page):
    """Render HTML pages like resume.html, learn.html, and chat.html"""
    if page in ['resume', 'learn', 'chat']:
        return send_file(f'{page}.html')
    return "Page not found", 404

if __name__ == '__main__':
    genai.configure(api_key="AIzaSyBADqoFQCnC5njtkGrEciTyzSug9hRck9A")
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")

    app.run(debug=True)
