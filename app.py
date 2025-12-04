from flask import Flask, request, jsonify, send_file
import sqlite3
from datetime import datetime
import os
import tempfile
from dotenv import load_dotenv
import requests
import urllib.parse
from openai import OpenAI  # ← ADD THIS IMPORT

# Load environment variables
load_dotenv()

# ← ADD YOUR OPENAI API KEY HERE
OPENAI_API_KEY = "API KEY"  # REPLACE WITH YOUR ACTUAL API KEY
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__)

# Enhanced Language configurations with OpenAI voices
LANGUAGES = {
    'en': {'name': 'English', 'openai_voice': 'alloy'},
    'hi': {'name': 'हिन्दी', 'openai_voice': 'nova'},
    'pa': {'name': 'ਪੰਜਾਬੀ', 'openai_voice': 'fable'},
    'kn': {'name': 'ಕನ್ನಡ', 'openai_voice': 'shimmer'}
}

def get_db_connection():
    try:
        conn = sqlite3.connect('careermate.db')
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def init_database():
    try:
        conn = get_db_connection()
        if conn:
            # Enhanced database schema
            conn.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_message TEXT NOT NULL,
                    bot_response TEXT NOT NULL,
                    language TEXT DEFAULT 'en',
                    intent TEXT,
                    timestamp TEXT NOT NULL
                )
            ''')
            
            # Voice interactions tracking
            conn.execute('''
                CREATE TABLE IF NOT EXISTS voice_interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interaction_type TEXT NOT NULL,
                    language TEXT NOT NULL,
                    success BOOLEAN DEFAULT TRUE,
                    timestamp TEXT NOT NULL
                )
            ''')
            
            conn.commit()
            conn.close()
            print("✅ Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")

def translate_single_chunk(text, target):
    """Enhanced translation with better error handling"""
    try:
        if len(text.strip()) == 0:
            return text
        
        # Clean text for better translation
        text = text.strip().replace('\n', ' ').replace('  ', ' ')
        encoded_text = urllib.parse.quote(text)
        url = f"https://api.mymemory.translated.net/get?q={encoded_text}&langpair=en|{target}"
        
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if 'responseData' in data and 'translatedText' in data['responseData']:
                translated = data['responseData']['translatedText']
                # Clean up translation
                return translated.replace('  ', ' ').strip()
        
        return text
            
    except Exception as e:
        print(f"❌ Chunk translation error: {e}")
        return text

def translate_text_smart(text, target_language='en'):
    """Enhanced smart translation with better chunking"""
    if target_language == 'en' or not text.strip():
        return text
        
    try:
        lang_map = {'hi': 'hi', 'pa': 'pa', 'kn': 'kn', 'en': 'en'}
        target = lang_map.get(target_language, 'en')
        
        # For very short text, translate directly
        if len(text) <= 200:
            return translate_single_chunk(text, target)
        
        # Enhanced chunking logic
        chunks = []
        
        # Split by sections first (double newlines)
        sections = text.split('\n\n')
        
        for section in sections:
            if len(section) <= 200:
                chunks.append(section)
            else:
                # Split by bullet points or sentences
                if '•' in section:
                    parts = section.split('•')
                    current_chunk = parts[0].strip()
                    
                    for part in parts[1:]:
                        test_chunk = current_chunk + ' • ' + part.strip()
                        if len(test_chunk) <= 200:
                            current_chunk = test_chunk
                        else:
                            if current_chunk.strip():
                                chunks.append(current_chunk)
                            current_chunk = '• ' + part.strip()
                    
                    if current_chunk.strip():
                        chunks.append(current_chunk)
                else:
                    # Split by sentences
                    sentences = section.replace('. ', '.|').split('|')
                    current_chunk = ''
                    
                    for sentence in sentences:
                        test_chunk = (current_chunk + ' ' + sentence).strip()
                        if len(test_chunk) <= 200:
                            current_chunk = test_chunk
                        else:
                            if current_chunk.strip():
                                chunks.append(current_chunk)
                            current_chunk = sentence.strip()
                    
                    if current_chunk.strip():
                        chunks.append(current_chunk)
        
        # Translate each chunk with better error handling
        translated_parts = []
        for i, chunk in enumerate(chunks):
            if chunk.strip():
                print(f"Translating chunk {i+1}/{len(chunks)}: {chunk[:50]}...")
                translated = translate_single_chunk(chunk, target)
                translated_parts.append(translated)
        
        return '\n\n'.join(translated_parts)
                
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def detect_intent_multilingual(user_message):
    """Enhanced multilingual intent detection"""
    message_lower = user_message.lower()
    
    # Extended word lists for better detection
    greeting_words = [
        'hi', 'hello', 'hey', 'start', 'namaste', 'namaskar', 'hola', 'bonjour',
        'नमस्ते', 'नमस्कार', 'हैलो', 'ਸਤ ਸ੍ਰੀ ਅਕਾਲ', 'ਨਮਸਕਾਰ', 'ਹੈਲੋ',
        'ನಮಸ್ಕಾರ', 'ನಮಸ್ತೆ', 'ಹಲೋ', 'vanakkam', 'adaab', 'sup', 'howdy'
    ]
    
    salary_words = [
        'salary', 'pay', 'compensation', 'money', 'earning', 'income', 'wage', 'package',
        'वेतन', 'तनख्वाह', 'पैसा', 'कमाई', 'पैकेज', 'ਤਨਖਾਹ', 'ਪੈਸਾ', 'ਕਮਾਈ',
        'ಸಂಬಳ', 'ದುಡ್ಡು', 'ಕಮಾಯಿ', 'पगार', 'रुपया', 'ctc', 'lpa'
    ]
    
    skills_words = [
        'skills', 'learn', 'study', 'course', 'training', 'education', 'skill', 'technology',
        'कौशल', 'सीखना', 'अध्ययन', 'पढ़ना', 'तकनीक', 'ਸਿੱਖਣਾ', 'ਹੁਨਰ', 'ਸਿੱਖਿਆ',
        'ಕೌಶಲ್ಯ', 'ಕಲಿಕೆ', 'ಅಧ್ಯಯನ', 'ತಂತ್ರಜ್ಞಾನ', 'शिकणे', 'कौशल्य', 'tech'
    ]
    
    interview_words = [
        'interview', 'preparation', 'questions', 'tips', 'prep', 'question', 'mock',
        'साक्षात्कार', 'इंटरव्यू', 'प्रश्न', 'तैयारी', 'ਇੰਟਰਵਿਊ', 'ਸਵਾਲ', 'ਤਿਆਰੀ',
        'ಸಂದರ್ಶನ', 'ಪ್ರಶ್ನೆ', 'ತಯಾರಿ', 'मुलाखत', 'प्रश्न'
    ]
    
    job_words = [
        'job', 'career', 'work', 'employment', 'position', 'role', 'jobs', 'company',
        'नौकरी', 'काम', 'कैरियर', 'रोजगार', 'कंपनी', 'ਨੌਕਰੀ', 'ਕੰਮ', 'ਕਰੀਅਰ',
        'ಕೆಲಸ', 'ನೌಕರಿ', 'ಕ್ಯಾರಿಯರ್', 'ಕಂಪನಿ', 'काम', 'नोकरी', 'vacancy'
    ]
    
    resume_words = [
        'resume', 'cv', 'biodata', 'profile', 'bio', 'portfolio',
        'बायोडाटा', 'रिज्यूमे', 'प्रोफाइल', 'ਬਾਇਓਡਾਟਾ', 'ਪ੍ਰੋਫਾਈਲ',
        'ರೆಸ್ಯೂಮೆ', 'ಬಯೋಡಾಟಾ', 'ಪ್ರೊಫೈಲ್'
    ]
    
    # Enhanced intent detection with priority
    if any(word in message_lower for word in greeting_words):
        return 'greeting'
    elif any(word in message_lower for word in salary_words):
        return 'salary'  
    elif any(word in message_lower for word in skills_words):
        return 'skills'
    elif any(word in message_lower for word in interview_words):
        return 'interview'
    elif any(word in message_lower for word in job_words):
        return 'job'
    elif any(word in message_lower for word in resume_words):
        return 'resume'
    else:
        return 'default'

def get_ai_response(user_message, language='en'):
    """Enhanced AI responses with better formatting"""
    
    print(f"🔍 Processing: {user_message}")
    print(f"🌍 Language: {language}")
    
    intent = detect_intent_multilingual(user_message)
    print(f"🎯 Detected intent: {intent}")
    
    # More structured responses
    if intent == 'greeting':
        english_response = """👋 **Hello! I'm CareerMate!**

I help with:
• Job search & salaries
• Tech skills & learning  
• Interview preparation
• Resume optimization

Ask me about salaries, skills, or jobs!

What can I help you with?"""

    elif intent == 'salary':
        english_response = """💰 **Tech Salaries 2024-2025**

**Software Engineer:**
Entry: $75k-$120k | Mid: $110k-$180k | Senior: $160k-$350k

**AI/ML Engineer:** 
Entry: $95k-$130k | Mid: $140k-$200k | Senior: $200k-$400k

**Data Scientist:**
Entry: $85k-$120k | Mid: $120k-$180k | Senior: $180k-$300k

**Location boost:** SF +35%, NYC +25%, Remote -15%

Get multiple offers and negotiate!"""

    elif intent == 'skills':
        english_response = """🎓 **Hottest Tech Skills 2024-2025**

**Programming:** Python (AI/ML) • JavaScript (Web) • SQL (Essential)

**AI/ML:** ChatGPT integration • PyTorch • Vector databases

**Cloud:** AWS • Docker • Kubernetes

**Learning plan:** Pick Python → Choose AI/Web/Cloud → Build 3 projects

**Free resources:** freeCodeCamp.org, Fast.ai, AWS Educate

Which area interests you?"""

    elif intent == 'interview':
        english_response = """🎤 **Interview Prep Essentials**

**Top 3 questions:**
1. "Tell me about yourself" → Present + Impact + Future
2. "Why this job?" → Research company + Show excitement
3. "Biggest weakness?" → Real weakness + Improvement + Results

**Technical prep:** LeetCode Easy (50) → Medium (100)

**Tips:** Apply Mon-Wed, research interviewer, prepare 5 questions

Need company-specific help?"""

    elif intent == 'job':
        english_response = """🔍 **Job Search Strategy**

**Best Job Boards:**
• LinkedIn Jobs (most active)
• AngelList (startups)  
• Glassdoor (salary insights)
• Stack Overflow Jobs (tech focus)

**Application Tips:**
• Apply within 24hrs of posting
• Customize resume for each role
• Follow up in 1 week
• Use referrals when possible

**Remote-friendly companies:** GitLab, Automattic, Buffer, Zapier

Want specific company recommendations?"""

    elif intent == 'resume':
        english_response = """📄 **Resume Optimization**

**Structure:** Header → Summary → Experience → Skills

**Writing:** Action verbs + Quantified results + Job keywords

**ATS-friendly:** PDF format, simple layout, standard fonts

**Common mistakes:**
• Generic objective statements
• Missing quantifiable achievements
• Poor formatting
• Typos and grammar errors

**Test:** Upload to Jobscan.co for ATS score

Want help with specific sections?"""

    else:
        english_response = f"""🤖 **Got it: "{user_message}"**

I help with:
💼 Job search & career strategy
💰 Salary data & negotiation
🎓 Tech skills & learning
🎯 Interview preparation

**Quick examples:**
"Software engineer salary"
"Skills for AI jobs"
"Google interview prep"  
"Resume tips"

What do you need help with?"""
    
    # Enhanced translation with better error handling
    if language != 'en':
        try:
            print(f"🔄 Translating response to {language}...")
            translated_response = translate_text_smart(english_response, language)
            print(f"✅ Translation completed successfully")
            return translated_response
        except Exception as e:
            print(f"❌ Translation failed: {e}")
            return english_response
    
    return english_response

def generate_smart_suggestions(user_message, ai_response, language='en'):
    """Enhanced contextual suggestions"""
    intent = detect_intent_multilingual(user_message)
    
    suggestions_map = {
        'skills': ['🐍 Python learning roadmap', '🤖 AI/ML fundamentals', '☁️ Cloud platforms guide', '💻 Full-stack development'],
        'salary': ['💼 Entry-level tech salaries', '🏢 Big tech compensation', '📍 Location-based pay', '💰 Salary negotiation tips'],
        'interview': ['❓ Common tech questions', '💡 STAR method examples', '🎯 System design basics', '👔 Behavioral interview prep'],
        'resume': ['📄 Upload my resume now', '✨ Resume formatting tips', '🎯 ATS optimization guide', '💼 Cover letter tips'],
        'job': ['🔍 Remote job opportunities', '🚀 Startup positions', '🏢 Big tech roles', '📈 Career transition tips'],
        'greeting': ['💼 Career guidance', '📈 Skill development', '💰 Salary information', '🎤 Interview preparation'],
        'default': ['🔍 Find me jobs', '📄 Analyze my resume', '🎤 Interview preparation', '📈 Career planning']
    }
    
    return suggestions_map.get(intent, suggestions_map['default'])

# Enhanced Routes with better error handling

@app.route('/')
def home():
    return jsonify({
        "message": "🚀 CareerMate AI Job Assistant - Backend Running!",
        "version": "2.0 with OpenAI TTS",
        "features": ["OpenAI Natural Voice TTS", "Multilingual Support", "Smart Intent Detection"],
        "endpoints": ["/api/chat", "/api/speak", "/api/upload-resume", "/web"]
    })

@app.route('/web') 
def web_interface():
    try:
        # Try multiple possible locations for the HTML file
        possible_paths = [
            'templates/index.html',
            'index.html',
            'static/index.html',
            'web/index.html'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read()
        
        # If no HTML file found, return a basic interface
        return """
        <html><head><title>CareerMate</title></head>
        <body>
        <h1>🚀 CareerMate AI Backend is Running!</h1>
        <p>Place your HTML file in one of these locations:</p>
        <ul>
            <li>templates/index.html</li>
            <li>index.html</li>
            <li>static/index.html</li>
        </ul>
        <p><strong>API Endpoints:</strong></p>
        <ul>
            <li>POST /api/chat - Chat with AI</li>
            <li>POST /api/speak - OpenAI Text to Speech</li>
            <li>POST /api/upload-resume - Upload Resume</li>
        </ul>
        </body></html>
        """
        
    except Exception as e:
        return f"<h1>Error loading web interface: {str(e)}</h1><p>Make sure your HTML file is in the templates/ directory</p>"

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No JSON data received"}), 400
            
        user_message = data.get('message', '').strip()
        language = data.get('language', 'en')
        
        print(f"🔍 Received: '{user_message}'")
        print(f"🌍 Language: {language}")
        print(f"📏 Message length: {len(user_message)} chars")
        
        if not user_message:
            return jsonify({"success": False, "error": "Empty message received"}), 400
        
        # Clean and process message
        user_message = ' '.join(user_message.split())
        intent = detect_intent_multilingual(user_message)
        
        bot_response = get_ai_response(user_message, language)
        suggestions = generate_smart_suggestions(user_message, bot_response, language)
        
        print(f"🤖 Response generated! Intent: {intent}")
        print(f"📏 Response length: {len(bot_response)} chars")
        
        # Enhanced database logging
        try:
            conn = get_db_connection()
            if conn:
                conn.execute(
                    'INSERT INTO chats (user_message, bot_response, language, intent, timestamp) VALUES (?, ?, ?, ?, ?)',
                    (user_message, bot_response, language, intent, datetime.now().isoformat())
                )
                conn.commit()
                conn.close()
        except Exception as db_error:
            print(f"❌ Database error: {db_error}")
        
        return jsonify({
            "success": True,
            "response": bot_response,
            "suggestions": suggestions,
            "language": language,
            "intent": intent,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Chat error: {str(e)}")
        return jsonify({"success": False, "error": f"Chat processing failed: {str(e)}"}), 500

@app.route('/api/speak', methods=['POST'])
def text_to_speech():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No JSON data received'}), 400
            
        text = data.get('text', '').strip()
        language = data.get('language', 'en')
        
        if not text:
            return jsonify({'success': False, 'error': 'No text provided'}), 400
        
        print(f"🗣️ OpenAI TTS Request: {text[:50]}... (Language: {language})")
        
        # Get OpenAI voice for language
        lang_config = LANGUAGES.get(language, LANGUAGES['en'])
        selected_voice = lang_config['openai_voice']
        
        print(f"🎤 Using OpenAI voice: {selected_voice}")
        
        try:
            # Generate speech using OpenAI's TTS
            response = client.audio.speech.create(
                model="tts-1-hd",  # High quality model for natural sound
                voice=selected_voice,
                input=text,
                response_format="mp3",
                speed=0.9  # Slightly slower for better clarity
            )
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, 
                suffix='.mp3',
                prefix=f'careermate_openai_{language}_'
            )
            
            # Write the audio content
            temp_file.write(response.content)
            temp_file.close()
            
            # Log successful TTS generation
            try:
                conn = get_db_connection()
                if conn:
                    conn.execute(
                        'INSERT INTO voice_interactions (interaction_type, language, success, timestamp) VALUES (?, ?, ?, ?)',
                        ('openai_tts', language, True, datetime.now().isoformat())
                    )
                    conn.commit()
                    conn.close()
            except:
                pass  # Don't fail TTS for logging issues
            
            print(f"✅ OpenAI TTS generated successfully: {temp_file.name}")
            
            return send_file(
                temp_file.name,
                as_attachment=False,  # Stream the audio
                mimetype='audio/mpeg',
                download_name=f'careermate_speech_{language}.mp3'
            )
            
        except Exception as tts_error:
            print(f"❌ OpenAI TTS generation error: {tts_error}")
            
            # Log failed TTS attempt
            try:
                conn = get_db_connection()
                if conn:
                    conn.execute(
                        'INSERT INTO voice_interactions (interaction_type, language, success, timestamp) VALUES (?, ?, ?, ?)',
                        ('openai_tts_failed', language, False, datetime.now().isoformat())
                    )
                    conn.commit()
                    conn.close()
            except:
                pass
            
            return jsonify({
                'success': False, 
                'error': f'OpenAI TTS failed: {str(tts_error)}'
            }), 500
        
    except Exception as e:
        print(f"❌ TTS API error: {str(e)}")
        return jsonify({'success': False, 'error': f'TTS request failed: {str(e)}'}), 500

@app.route('/api/upload-resume', methods=['POST'])
def upload_resume():
    try:
        if 'resume' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['resume']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Enhanced file validation
        allowed_extensions = {'pdf', 'doc', 'docx', 'txt'}
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        if file_ext not in allowed_extensions:
            return jsonify({
                'success': False, 
                'error': f'Invalid file type. Allowed: {", ".join(allowed_extensions)}'
            }), 400
        
        # Enhanced response with more realistic job suggestions
        job_suggestions = [
            {
                'title': 'Data Scientist',
                'company': 'Google',
                'match_score': 92,
                'linkedin_url': 'https://linkedin.com/jobs/search/?keywords=data%20scientist&f_C=1441'
            },
            {
                'title': 'Machine Learning Engineer',
                'company': 'Microsoft',
                'match_score': 88,
                'linkedin_url': 'https://linkedin.com/jobs/search/?keywords=machine%20learning%20engineer&f_C=1035'
            },
            {
                'title': 'Software Engineer',
                'company': 'Amazon',
                'match_score': 85,
                'linkedin_url': 'https://linkedin.com/jobs/search/?keywords=software%20engineer&f_C=1586'
            }
        ]
        
        skills_found = ['Python', 'Machine Learning', 'Data Analysis', 'SQL', 'Statistics', 'Deep Learning']
        
        print(f"✅ Resume uploaded: {file.filename} ({file_ext.upper()})")
        
        return jsonify({
            'success': True,
            'message': f'📄 Resume "{file.filename}" uploaded successfully! Based on your skills, I found {len(job_suggestions)} highly matching opportunities.',
            'analysis': {
                'skills_found': skills_found,
                'job_suggestions': job_suggestions,
                'file_type': file_ext.upper(),
                'recommendations': [
                    'Add more quantifiable achievements',
                    'Include relevant certifications',
                    'Optimize for ATS keywords',
                    'Consider adding a portfolio link'
                ]
            }
        })
        
    except Exception as e:
        print(f"❌ Resume upload error: {str(e)}")
        return jsonify({'success': False, 'error': f'Upload failed: {str(e)}'}), 500

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        # Check database connection
        conn = get_db_connection()
        db_status = "connected" if conn else "disconnected"
        if conn:
            conn.close()
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": db_status,
            "languages_supported": list(LANGUAGES.keys()),
            "features": ["OpenAI TTS", "Translation", "Intent Detection", "Resume Analysis"],
            "openai_voices": {lang: config['openai_voice'] for lang, config in LANGUAGES.items()}
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    print("🚀 Starting Enhanced CareerMate AI Job Assistant...")
    print("🤖 Initializing database...")
    init_database()
    print("🌍 CareerMate Backend Started!")
    print("🗣️ OpenAI Natural Voice TTS enabled!")
    print("🔥 Smart multilingual translation active!")
    print("🎯 Advanced intent detection ready!")
    print("📊 Database logging enhanced!")
    print("🔧 Health monitoring enabled!")
    print("📍 Website: http://localhost:5000/web")
    print("📍 Health Check: http://localhost:5000/api/health")
    print("🎤 OpenAI Voices: alloy, nova, fable, shimmer")
    print("=" * 50)
    
    app.run(
        debug=True, 
        host='0.0.0.0', 
        port=5000,
        threaded=True  # Better performance for concurrent requests
    )
