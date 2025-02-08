from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import PyPDF2
import os
import json
import re  
import urllib.parse
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

# Configure the API key (ideally load this from an environment variable)
genai.configure(api_key="AIzaSyBADqoFQCnC5njtkGrEciTyzSug9hRck9A")

# Option 1: Directly call generate_text when needed
# Option 2: If you prefer a model instance, you might consider wrapping it—but here we use generate_text directly.

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'status': 'error', 'message': 'No message provided'}), 400

    user_message = data['message']

    # Customize prompt for job-related context
    job_context = (
        "You are a professional job assistant. Provide helpful, concise, and professional advice about "
        "job searching, resume writing, interview preparation, career development, and workplace skills. "
        "Tailor your responses to be constructive and supportive.\n\nUser's query:\n"
    )

    full_prompt = job_context + user_message

    try:
        # Generate a response using the updated generate_text method
        response = genai.generate_text(
            model="gemini-1.5-flash",
            prompt=full_prompt
            # You can include additional parameters such as temperature or max_output_tokens if needed.
        )

        return jsonify({
            'status': 'success',
            'message': response.result  # Use the proper attribute from the response object
        })
    except Exception as e:
        # Log the exception for debugging
        print("Error generating response:", e)
        return jsonify({
            'status': 'error',
            'message': "Error generating response. Please try again."
        }), 500

# The rest of your endpoints remain unchanged

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
    # You might want to consolidate duplicate '/' routes.
    return send_file('index.html')

@app.route('/<page>')
def render_page(page):
    if page in ['resume', 'learn', 'chat']:
        return send_file(f'{page}.html')
    return "Page not found", 404

def generate_job_search_url(skills):
    """
    Generate job search URL based on skills.
    
    Args:
        skills (list): List of skills extracted from the resume
    
    Returns:
        dict: Job search details
    """
    # Technical skill keywords
    technical_keywords = [
        'javascript', 'node.js', 'react', 'mongodb', 'python', 'java', 
        'c', 'c++', 'html', 'css', 'backend', 'frontend', 'fullstack', 
        'web development', 'programming', 'software', 'devops', 'sql'
    ]
    
    # Non-technical skill keywords
    non_technical_keywords = [
        'management', 'sales', 'marketing', 'hr', 'customer service', 
        'administrative', 'communication', 'creative', 'business'
    ]
    
    # Check skill types
    is_technical = any(skill.lower() in technical_keywords for skill in skills)
    
    # Prepare search parameters
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

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
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
        
    app.run(debug=True)
