from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import PyPDF2
import io
import os
import json
import re
import urllib.parse
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

# Configure the Generative AI API key (ideally via an environment variable)
genai.configure(api_key="AIzaSyAn_9wz5q5etT5_Bgm_aEh4HgMXuzIrrUI")


@app.route('/chat', methods=['POST'])
def chat():
    """
    Receives a user message, adds a job-assistant context, and returns a generated response.
    """
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'status': 'error', 'message': 'No message provided'}), 400

    user_message = data['message']

    # Job-assistant context prompt
    job_context = (
        "You are a professional job assistant. Provide helpful, concise, and professional advice about "
        "job searching, resume writing, interview preparation, career development, and workplace skills. "
        "Tailor your responses to be constructive and supportive.\n\nUser's query:\n"
    )
    full_prompt = job_context + user_message

    try:
        # Initialize the model with gemini-1.5-flash
        model = genai.GenerativeModel(model_name="gemini-2.0-flash")
        
        # Generate response
        response = model.generate_content(full_prompt)
        
        # Check if response was blocked
        if response.prompt_feedback.block_reason:
            return jsonify({
                'status': 'error',
                'message': "The response was blocked due to content safety restrictions."
            }), 400
            
        return jsonify({
            'status': 'success',
            'message': response.text
        })
    except Exception as e:
        print("Error generating response:", str(e))
        return jsonify({
            'status': 'error',
            'message': "Error generating response. Please try again."
        }), 500


# --------------------- Helper Functions --------------------- #
def load_json_file(file_name):
    """
    Loads a JSON file from the same directory.
    """
    file_path = os.path.join(os.path.dirname(__file__), file_name)
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_jobs():
    """
    Loads job listings from 'jobs.json'.
    """
    return load_json_file("jobs.json")


def extract_skills_from_pdf(file_stream):
    """
    Extracts skills from a PDF file-like object.
    
    Args:
        file_stream (BytesIO): In-memory file stream of the PDF.
        
    Returns:
        list: A list of skill strings.
    """
    skills = []
    reader = PyPDF2.PdfReader(file_stream)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    lines = text.splitlines()
    skills_section_found = False

    for line in lines:
        line = line.strip()
        # Identify the skills section (case-insensitive)
        if 'skills' in line.lower():
            skills_section_found = True
            continue

        if skills_section_found and line:
            # Expecting skills to be comma-separated
            skills.extend([skill.strip() for skill in line.split(',') if skill.strip()])

        # Stop if an empty line is found after the skills section starts
        if skills_section_found and not line:
            break

    return skills


def tokenize(text):
    """
    Tokenizes text into lowercase alphanumeric tokens.
    """
    tokens = re.findall(r'\b\w+\b', text.lower())
    return tokens


def generate_job_search_url(skills):
    """
    Generates a Google job search URL based on the list of skills.
    
    Args:
        skills (list): List of skills extracted from the resume.
        
    Returns:
        dict: Contains the job search URL, a flag for an apply button, and job types.
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
    
    # Determine if any extracted skill is technical
    is_technical = any(skill.lower() in technical_keywords for skill in skills)
    
    # Base URL for Google search
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
    """
    Accepts a PDF file upload, extracts skills, compares them against job listings,
    and returns recommended jobs along with a generated job search URL.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']

    # Read the uploaded file into memory (as a BytesIO stream)
    file_stream = io.BytesIO(file.read())

    # Extract skills from the PDF
    skills_text = extract_skills_from_pdf(file_stream)

    extracted_tokens = set()
    for skill in skills_text:
        extracted_tokens.update(tokenize(skill))

    # Load job listings from jobs.json
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

        # Determine matching tokens between extracted skills and job description tokens
        matched_tokens = extracted_tokens.intersection(job_tokens)

        if matched_tokens:
            # Calculate match percentage based on token overlap
            match_percentage = round((len(matched_tokens) / len(job_tokens)) * 100, 2)
            recommended_jobs.append({
                "job": job,
                "match_percentage": match_percentage,
                "matched_tokens": list(matched_tokens)
            })

    # Sort jobs by descending match percentage
    recommended_jobs.sort(key=lambda x: x['match_percentage'], reverse=True)

    # Generate a job search URL based on the extracted skills
    job_search_info = generate_job_search_url(skills_text)

    return jsonify({
        'jobs': recommended_jobs,
        'job_search_url': job_search_info['job_search_url'],
        'show_apply_button': job_search_info['apply_button']
    })


@app.route('/')
def index():
    """
    Serves the main index page.
    """
    return send_file('dashboard.html')


@app.route('/<page>')
def render_page(page):
    """
    Serves specific pages if they are allowed.
    """
    # Define a set of allowed pages (without the .html extension)
    allowed_pages = {'resume', 'learn', 'chat'}
    if page in allowed_pages:
        return send_file(f'{page}.html')
    return "Page not found", 404


if __name__ == '__main__':
    app.run(debug=True)
