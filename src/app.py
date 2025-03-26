from flask import Flask, request, jsonify, send_file
import os
import requests
import json
import time
import pandas as pd
import re
import openai
from flask_cors import CORS
import tempfile



# Mathpix API credentials
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MATHPIX_API_KEY = os.getenv("MATHPIX_API_KEY")
MATHPIX_APP_ID = os.getenv("MATHPIX_APP_ID")

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

openai.api_key = OPENAI_API_KEY

# List of Question Categories
question_categories = [ 
    "Answer the following correctly", "Evaluate the following", "Simplify the following expr.", "Choose the ODD one Out",
    "Numerical/application based", "Very Short Answer Questions", "True or False", "CBQ with sub questions", "LAT with sub questions",
    "LAT Questions", "SAT Questions (3 Marks)", "SAT Questions (2 Marks)", "Dialogues completion", "Sentence completion", "Rearrange the following words",
    "Identifying the following", "Sentence Transformation", "Sentence reordering", "Editing and Omission", "Error correction", "Joining Sentences", "Fill in the Blanks",
    "Passage based questions", "Composition writing", "Short Answer Type (3 marks)", "Short Answer Type (2 marks)", "Extract based question", "Choose the correct answers", 
    "Locating and Plotting on map", "Extract based on Map Survey", "Assertion & Reasons Type",
    "Mark Questions", "2 Marks Question", "5 Mark Question", "4 Mark Question", "3 Mark Question", "1 Mark Question", "Match the following Questions",
    "Multiple Choice Question", "Describe Questions", "Direct Question"
]

def poll_status(pdf_id, headers, poll_interval=10, max_polls=8):
    url = f"https://api.mathpix.com/v3/pdf/{pdf_id}.json"
    for poll_count in range(max_polls):
        print(f"Polling attempt {poll_count + 1} for PDF ID {pdf_id}")
        response = requests.get(url, headers=headers)
        status_data = response.json()
        print("Polling Status:", status_data)
        if status_data.get("status") == "completed":
            return status_data
        time.sleep(poll_interval)
    return None

def process_with_mathpix(file):
    options = {
        "conversion_formats": {"docx": True, "tex.zip": True},
        "math_inline_delimiters": ["$", "$"],
        "rm_spaces": True
    }

    r = requests.post("https://api.mathpix.com/v3/pdf",
        headers={
            "app_id": MATHPIX_APP_ID,
            "app_key": MATHPIX_API_KEY
        },
        data={
            "options_json": json.dumps(options)
        },
        files={
            "file": (file.filename, file.stream, file.content_type)
        }
    )

    API_resp = r.json()
    pdf_id = API_resp.get("pdf_id")
    if not pdf_id:
        return None

    headers = {
        "app_key": MATHPIX_API_KEY,
        "app_id": MATHPIX_APP_ID
    }

    status_data = poll_status(pdf_id, headers)
    if not status_data:
        return None

    url = f"https://api.mathpix.com/v3/pdf/{pdf_id}.mmd"
    response = requests.get(url, headers=headers)
    mmd_content = response.text

    mmd_content = mmd_content.replace("{", "").replace("}", "").replace("\section*", "")

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    temp_file.write(mmd_content.encode('utf-8'))
    temp_file.close()

    return temp_file.name

def parse_questions(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    questions = []
    lines = content.split('\n')
    current_question = ""
    question_number = 1
    
    for line in lines:
        if line.strip():
            if re.match(r'^\(?\s*([0-9]+)\s*[\).]', line, re.IGNORECASE):
                if current_question:
                    questions.append({
                        'text': current_question.strip(),
                        'number': question_number
                    })
                    question_number += 1
                current_question = line.strip()
            else:
                current_question += "\n" + line.strip()
    
    if current_question:
        questions.append({
            'text': current_question.strip(),
            'number': question_number
        })
    
    return questions

def parse_solutions(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    solutions = []
    lines = content.split('\n')
    current_solution = ""
    solution_number = 1
    
    for line in lines:
        if line.strip():
            if re.match(r'^\(?\s*([0-9]+)\s*[\).]', line, re.IGNORECASE):
                if current_solution:
                    solutions.append({
                        'text': current_solution.strip(),
                        'number': solution_number
                    })
                    solution_number += 1
                current_solution = line.strip()
            else:
                current_solution += "\n" + line.strip()
    
    if current_solution:
        solutions.append({
            'text': current_solution.strip(),
            'number': solution_number
        })
    
    return solutions

def process_descriptive_questions(questions, solutions):
    descriptive_data = []
    solution_dict = {sol['number']: sol['text'] for sol in solutions}

    for question in questions:
        solution = solution_dict.get(question['number'], '')
        question_text = question['text'].strip()
        question_text = re.sub(r'\s+', ' ', question_text)
        
        if not re.findall(r'[a-d]\) [^\n]+', question_text):
            descriptive_data.append({
                'Question Label': f'Q{question["number"]}',
                'Question Category': 'Descriptive',
                'Cognitive Skills': '',
                'Question Source': '',
                'Question Appears in': 'Pre/Post-Worksheet/Test',
                'Level of Difficulty': '',
                'Question': question_text,
                'Marks': 1,
                'Display Answer': solution.strip(),
                'Answer Type': '',
                'Answer Weightage': '',
                'Answer Content': '',  
                'Answer Explanation': solution.strip()  
            })
    
    return descriptive_data

def process_objective_questions(questions, solutions):
    objective_data = []
    solution_dict = {sol['number']: sol['text'] for sol in solutions}

    for question in questions:
        solution = solution_dict.get(question['number'], '')
        question_text = re.sub(r'[a-d]\) [^\n]+', '', question['text']).strip()
        options = re.findall(r'[a-d]\) [^\n]+', question['text'])

        if len(options) == 4:
            objective_data.append({
                'Question Label': f'Q{question["number"]}',
                'Question Category': '',
                'Cognitive Skills': '',
                'Question Source': '',
                'Question Appears in': 'Pre/Post-Worksheet/Test',
                'Level of Difficulty': '',
                'Question': question_text,
                'Marks': 1,
                'Answer Type1': 'Options',
                'Answer Content1': options[0] if len(options) > 0 else '',
                'Correct Answer1': 'No',
                'Answer Weightage1': 0,
                'Answer Type2': 'Options',
                'Answer Content2': options[1] if len(options) > 1 else '',
                'Correct Answer2': 'No',
                'Answer Weightage2': 0,
                'Answer Type3': 'Options',
                'Answer Content3': options[2] if len(options) > 2 else '',
                'Correct Answer3': 'No',
                'Answer Weightage3': 0,
                'Answer Type4': 'Options',
                'Answer Content4': options[3] if len(options) > 3 else '',
                'Correct Answer4': 'No',
                'Answer Weightage4': 0,
                'Answer Explanation': solution
            })
    
    return objective_data

def process_subjective_questions(questions, solutions):
    subjective_data = []
    solution_dict = {sol['number']: sol['text'] for sol in solutions}

    for question in questions:
        question_text = re.sub(r'[a-d]\) [^\n]+', '', question['text']).strip()
        solution = solution_dict.get(question['number'], '')
        
        if re.search(r'_{2,}', question_text): 
            subjective_data.append({
                'Question Label': f'Q{question["number"]}',
                'Question Category': 'Fill in the Blanks',
                'Cognitive Skills': '',
                'Question Source': '',
                'Question Appears in': 'Pre/Post-Worksheet/Test',
                'Level of Difficulty': '',
                'Question': question_text,
                'Marks': 1,
                'answer_type': ' ',  
                'answer_content': solution if solution else '',  
                'answer_display': 'yes',  
                'answer_weightage': 1,  
                'answer_option': '',  
                'answer_explanation': solution if solution else '' 
            })
    
    return subjective_data

def extract_correct_answer(explanation):
    if not explanation or not isinstance(explanation, str):
        return None
    
    match = re.search(r'[\(\s]([a-d])[\)\s]', explanation, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return None

def mark_correct_answers(objective_df):
    for index, row in objective_df.iterrows():
        correct_answer = extract_correct_answer(row['Answer Explanation'])
        
        for i in range(1, 5):
            answer_content = row[f'Answer Content{i}']
            if pd.isna(answer_content):
                objective_df.at[index, f'Correct Answer{i}'] = 'No'
                objective_df.at[index, f'Answer Weightage{i}'] = 0
            elif correct_answer and answer_content.startswith(f"{correct_answer})"):
                objective_df.at[index, f'Correct Answer{i}'] = 'Yes'
                objective_df.at[index, f'Answer Weightage{i}'] = row['Marks'] if not pd.isna(row['Marks']) else 0
            else:
                objective_df.at[index, f'Correct Answer{i}'] = 'No'
                objective_df.at[index, f'Answer Weightage{i}'] = 0
    
    return objective_df

def process_files_to_excel(questions_file, solutions_file, output_excel_path):
    questions = parse_questions(questions_file)
    solutions = parse_solutions(solutions_file)
    
    objective_data = process_objective_questions(questions, solutions)
    subjective_data = process_subjective_questions(questions, solutions)
    descriptive_data = process_descriptive_questions(questions, solutions)
    
    objective_df = pd.DataFrame(objective_data)
    subjective_df = pd.DataFrame(subjective_data)
    descriptive_df = pd.DataFrame(descriptive_data)
    
    objective_df = mark_correct_answers(objective_df)
    
    with pd.ExcelWriter(output_excel_path, engine='openpyxl') as writer:
        objective_df.to_excel(writer, sheet_name='Objective', index=False)
        subjective_df.to_excel(writer, sheet_name='Subjective', index=False)
        descriptive_df.to_excel(writer, sheet_name='Descriptive', index=False)
    
    print(f"Excel file created successfully at: {output_excel_path}")

def get_objective_details(question_content):
    prompt = f"""
    Based on the following question content, provide the following details:
    1. Question Category: {question_categories}
    2. Cognitive Skills: Remembering/Analyzing/Applying/Evaluating/Learning/Understanding
    3. Question Source: NCERT/NON-NCERT/Oswaal/Selina
    4. Level of Difficulty: Less/Moderate/Highly
    5. Marks: 1

    Question Content: {question_content}
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that categorizes questions."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=150
    )
    
    return response.choices[0].message['content'].strip()

def get_subjective_details(question_content):
    prompt = f"""
    Based on the following question content, provide the following details:
    1. Question Category: {question_categories}
    2. Cognitive Skills: Remembering/Analyzing/Applying/Evaluating/Learning/Understanding
    3. Question Source: NCERT/NON-NCERT/Oswaal/Selina
    4. Level of Difficulty: Easy/Medium/Hard
    5. Marks: 1
    6. answer_type: Words/Numbers/Alpha Numeric/Equations

    Question Content: {question_content}
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that categorizes questions."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=150
    )
    
    return response.choices[0].message['content'].strip()

def get_descriptive_details(question_content):
    prompt = f"""
    Based on the following question content, provide:
    1. Question Category: {question_categories}
    2. Cognitive Skills: Remembering/Analyzing/Applying/Evaluating/Learning/Understanding
    3. Question Source: NCERT/NON-NCERT/Oswaal/Selina
    4. Level of Difficulty: Less/Moderate/Highly
    5. Marks: 1-6
    6. Answer Type: Equation/Phrases
    7. Answer Content: Rubrics with marks in format "'Rubric' ('Mark allotted')"

    Question Content: {question_content}
    """
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that categorizes questions."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=300
    )
    
    return response.choices[0].message['content'].strip()

def process_excel_file_with_gpt(input_path, output_path):
    xls = pd.ExcelFile(input_path)
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        for sheet_name in xls.sheet_names:
            df = xls.parse(sheet_name)

            if 'Objective' in sheet_name:
                required_columns = ['Question Category', 'Cognitive Skills', 'Question Source', 
                                  'Level of Difficulty', 'Marks', 'Answer Type']
            elif 'Subjective' in sheet_name:
                required_columns = ['Question Category', 'Cognitive Skills', 'Question Source', 
                                  'Level of Difficulty', 'Marks', 'answer_type']
            elif 'Descriptive' in sheet_name:
                required_columns = ['Question Category', 'Cognitive Skills', 'Question Source', 
                                  'Level of Difficulty', 'Marks', 'Answer Type', 'Answer Content']
            else:
                continue

            for col in required_columns:
                if col not in df.columns:
                    if col == 'Marks':
                        df[col] = pd.NA
                    else:
                        df[col] = ""

            if 'Marks' in df.columns:
                df['Marks'] = pd.to_numeric(df['Marks'], errors='coerce')
            
            for index, row in df.iterrows():
                question_content = str(row['Question']) if 'Question' in row else ""

                if not question_content.strip():
                    continue

                try:
                    if 'Objective' in sheet_name:
                        details = get_objective_details(question_content)
                    elif 'Subjective' in sheet_name:
                        details = get_subjective_details(question_content)
                    elif 'Descriptive' in sheet_name:
                        details = get_descriptive_details(question_content)
                    
                    print(f"GPT Response for question {index + 1}: {details}")
                    
                    key_value_pairs = []
                    answer_content = []
                    
                    for line in details.split('\n'):
                        line = line.strip()
                        if ": " in line:
                            value = line.split(": ", 1)[-1].strip()
                            key_value_pairs.append(value)
                        elif line and ("Answer Content:" not in line):
                            clean_line = line.strip(" -\"'")
                            clean_line = re.sub(r'\(\d+ Mark[s]?\)', '', clean_line).strip()
                            if clean_line:
                                answer_content.append(clean_line)
                    
                    if 'Descriptive' in sheet_name:
                        details_list = key_value_pairs + answer_content
                    else:
                        details_list = key_value_pairs
                    
                    print(f"Parsed Details: {details_list}")

                    for i, col in enumerate(required_columns):
                        if i < len(details_list):
                            if col == 'Marks':
                                try:
                                    df.at[index, col] = float(details_list[i])
                                except (ValueError, TypeError):
                                    df.at[index, col] = pd.NA
                            else:
                                df.at[index, col] = str(details_list[i]).strip('"\'')
                        else:
                            df.at[index, col] = pd.NA if col == 'Marks' else ""
                    
                except Exception as e:
                    print(f"Error processing question {index + 1}: {e}")
                    continue

            df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    print(f"Successfully saved to {output_path}")

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'questionPaper' not in request.files or 'answerSheet' not in request.files:
        return jsonify({'error': 'Missing files'}), 400

    question_paper = request.files['questionPaper']
    answer_sheet = request.files['answerSheet']

    if question_paper.filename == '' or answer_sheet.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    print("Processing files with Mathpix...")
    question_txt_path = process_with_mathpix(question_paper)
    answer_txt_path = process_with_mathpix(answer_sheet)

    if not question_txt_path or not answer_txt_path:
        return jsonify({'error': 'Failed to process files with Mathpix'}), 500

    print("Generating intermediate Excel file...")
    intermediate_excel_path = "intermediate_output.xlsx"
    process_files_to_excel(question_txt_path, answer_txt_path, intermediate_excel_path)

    print("Processing Excel file with GPT...")
    final_excel_path = "final_output.xlsx"
    process_excel_file_with_gpt(intermediate_excel_path, final_excel_path)

    print("Sending final Excel file to the user...")

   # Return the final Excel file to the user
    print("Sending final Excel file to the user...")
    return send_file(
        final_excel_path,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='final_output.xlsx'
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
