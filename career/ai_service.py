import json
import logging
import os
from pathlib import Path
import time

from dotenv import load_dotenv
try:
    from google import genai
except Exception:
    genai = None
    logger = logging.getLogger(__name__)
    logger.warning('google.genai library not available; Gemini calls will be disabled during checks')


logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
logger.info("GEMINI_API_KEY loaded: %s", bool(GEMINI_API_KEY))


def _summarize_exception(exception):
    if exception is None:
        return 'unknown error'
    text = str(exception)
    if len(text) > 220:
        return text[:220] + '...'
    return text


def _is_resource_exhausted_error(exception):
    """Check if an exception is a 429 RESOURCE_EXHAUSTED Gemini API error."""
    try:
        if genai and hasattr(genai, 'errors') and isinstance(exception, genai.errors.ClientError):
            if hasattr(exception, 'status_code') and exception.status_code == 429:
                return True
    except Exception:
        pass

    status_code = getattr(exception, 'status_code', None)
    if status_code == 429:
        return True

    message = str(exception).lower()
    return 'resource_exhausted' in message or 'quota' in message and 'exceeded' in message


def _get_retry_delay(exception):
    """Extract retry delay from a Gemini error when provided, else use a safe default."""
    try:
        retry_after = getattr(exception, 'retry_after', None)
        if retry_after is not None:
            try:
                return max(1, min(int(float(retry_after)), 10))
            except (TypeError, ValueError):
                pass

        retry_after = getattr(exception, 'retry_after_seconds', None)
        if retry_after is not None:
            try:
                return max(1, min(int(float(retry_after)), 10))
            except (TypeError, ValueError):
                pass

        response = getattr(exception, 'response', None)
        if response is not None:
            headers = getattr(response, 'headers', {})
            if isinstance(headers, dict):
                retry_after = headers.get('Retry-After') or headers.get('retry-after')
                if retry_after is not None:
                    try:
                        return max(1, min(int(float(retry_after)), 10))
                    except (TypeError, ValueError):
                        pass

        if hasattr(exception, 'response_data'):
            response_data = exception.response_data
            if isinstance(response_data, dict):
                error_data = response_data.get('error', {})
                if isinstance(error_data, dict):
                    retry_after = error_data.get('retry_after') or error_data.get('retryAfter')
                    if retry_after is not None:
                        try:
                            return max(1, min(int(float(retry_after)), 10))
                        except (TypeError, ValueError):
                            pass

        return 2
    except Exception:
        return 2


def _is_retryable_error(exception):
    if exception is None:
        return False

    if isinstance(exception, (TimeoutError, ConnectionError, OSError)):
        return True

    if genai and hasattr(genai, 'errors') and isinstance(exception, genai.errors.ServerError):
        return True

    status_code = getattr(exception, 'status_code', None)
    if status_code in {408, 429, 500, 502, 503, 504}:
        return True

    response = getattr(exception, 'response', None)
    if response is not None:
        try:
            code = getattr(response, 'status_code', None)
            if code in {408, 429, 500, 502, 503, 504}:
                return True
        except Exception:
            pass

    message = str(exception).lower()
    retry_tokens = [
        'temporarily unavailable', 'service unavailable', 'timeout', 'rate limit', '429', '503', '500', '502', '504',
        'resource_exhausted', 'temporary outage', 'transient', 'try again in a few moments', 'temporarily down'
    ]
    return any(token in message for token in retry_tokens)


def _is_non_retryable_error(exception):
    if exception is None:
        return False

    status_code = getattr(exception, 'status_code', None)
    if status_code in {400, 401, 403, 404}:
        return True

    if genai and hasattr(genai, 'errors') and isinstance(exception, genai.errors.ClientError):
        if status_code in {400, 401, 403, 404}:
            return True

    message = str(exception).lower()
    if 'invalid api key' in message or 'api key' in message and 'invalid' in message:
        return True
    if 'unsupported model' in message or 'model not found' in message or 'not found' in message and 'model' in message:
        return True
    if 'malformed' in message or 'invalid request' in message:
        return True
    if 'quota' in message and 'exceeded' in message:
        return False
    return False


def _call_gemini_with_retry(callable_obj, *, context='Gemini request'):
    """Retry transient Gemini failures and return None when the service stays unavailable."""
    max_attempts = 3
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            return callable_obj()
        except Exception as exc:
            last_exception = exc
            if _is_retryable_error(exc) and attempt < max_attempts:
                delay = _get_retry_delay(exc)
                logger.warning(
                    'Gemini API %s failed on attempt %d/%d; retrying in %d seconds. Error: %s',
                    context,
                    attempt,
                    max_attempts,
                    delay,
                    _summarize_exception(exc),
                )
                time.sleep(delay)
                continue

            if _is_retryable_error(exc):
                logger.warning(
                    'Gemini API %s failed after %d attempts; service is temporarily unavailable.',
                    context,
                    max_attempts,
                )
                return None

            logger.warning(
                'Gemini API %s failed on attempt %d/%d with a non-retryable error: %s',
                context,
                attempt,
                max_attempts,
                _summarize_exception(exc),
            )
            raise

    if last_exception is not None and _is_retryable_error(last_exception):
        logger.warning('Gemini API %s exhausted retries after %d attempts.', context, max_attempts)
        return None

    return None


def is_openai_configured():
    """Return True when the Gemini API key and genai library are available."""
    return bool(GEMINI_API_KEY and genai)


def analyze_resume_text(extracted_text):
    """Use Gemini to review the text from a resume and return beginner-friendly analysis."""
    if not extracted_text or not extracted_text.strip():
        raise ValueError('No readable text was found in the uploaded PDF.')

    if not is_openai_configured():
        raise RuntimeError('Gemini API key is missing. Add GEMINI_API_KEY to your .env file.')

    client = genai.Client(api_key=GEMINI_API_KEY)

    json_schema = '''{
      "summary": "short summary of the resume",
      "skills": ["skill 1", "skill 2"],
      "skill_gaps": ["missing skill 1", "missing skill 2"],
      "strengths": ["strength 1", "strength 2"],
      "improvements": ["improvement 1", "improvement 2"],
      "career_suggestions": ["role 1", "role 2"],
      "resume_score": 85
    }'''

    prompt = (
        "Analyze this resume for a student job seeker.\n"
        "Return valid JSON only with these keys:\n"
        f"{json_schema}\n\n"
        "Keep the language simple, helpful, and beginner-friendly.\n"
        "Focus on realistic student career advice and improvement suggestions.\n"
        "Resume text:\n"
        f"{extracted_text[:15000]}"
    )

    try:
        response = _call_gemini_with_retry(
            lambda: client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            ),
            context='resume analysis',
        )
        if response is None:
            raise RuntimeError('The resume analysis service is temporarily unavailable. Please try again in a few moments.')
    except RuntimeError:
        raise
    except Exception as exc:
        if _is_non_retryable_error(exc):
            raise RuntimeError('The Gemini API configuration is invalid or unavailable. Please check your API key and model settings.') from exc
        logger.exception('Gemini API request failed while analyzing resume.')
        raise

    content = getattr(response, 'text', None)
    if not content:
        raise ValueError('The AI response was empty.')

    try:
        analysis = json.loads(content)
    except json.JSONDecodeError:
        cleaned = content.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.strip('`')
            if cleaned.lower().startswith('json'):
                cleaned = cleaned[4:].lstrip()
        try:
            analysis = json.loads(cleaned)
        except json.JSONDecodeError:
            raise ValueError('The AI response was not valid JSON.')

    normalized = {
        'summary': analysis.get('summary') or 'No summary available.',
        'skills': analysis.get('skills') or [],
        'skill_gaps': analysis.get('skill_gaps') or [],
        'strengths': analysis.get('strengths') or [],
        'improvements': analysis.get('improvements') or [],
        'career_suggestions': analysis.get('career_suggestions') or [],
        'resume_score': int(analysis.get('resume_score', 0) or 0),
    }

    if normalized['resume_score'] < 0:
        normalized['resume_score'] = 0
    if normalized['resume_score'] > 100:
        normalized['resume_score'] = 100

    return normalized


def generate_interview_questions(role, resume_skills=None):
    """Use Gemini to generate structured interview questions for a role.

    Returns a dict with keys: role, categories where categories is a dict with
    'Technical', 'Project', 'HR' each containing a list of question objects:
    {"question": ..., "guidance": ..., "key_points": [...]}
    """
    if not role:
        raise ValueError('Role is required to generate interview questions.')

    if not is_openai_configured():
        raise RuntimeError('Gemini API key is missing. Add GEMINI_API_KEY to your .env file.')

    client = genai.Client(api_key=GEMINI_API_KEY)

    json_schema = '''{
      "role": "role name",
      "categories": {
        "Technical": [{"question":"","guidance":"","key_points":[] }],
        "Project": [{"question":"","guidance":"","key_points":[] }],
        "HR": [{"question":"","guidance":"","key_points":[] }]
      }
    }'''

    skills_text = ''
    if resume_skills:
        if isinstance(resume_skills, list):
            skills_text = ', '.join([str(s) for s in resume_skills])
        else:
            skills_text = str(resume_skills)

    prompt = f"""
Generate beginner-friendly interview questions for the role '{role}'.
Return valid JSON only with this schema:
{json_schema}

Create 4-6 Technical questions focused on core skills for this role, 2-4 Project questions that ask about past work or projects, and 3 HR/behavioral questions. For each question provide brief expected-answer guidance and 3-5 key points the candidate should mention.
Keep language simple and suitable for an entry-level student.
If resume skills are provided, tailor questions to those skills when appropriate.
Resume skills:
{skills_text}
"""

    try:
        response = _call_gemini_with_retry(
            lambda: client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            ),
            context='interview question generation',
        )
        if response is None:
            logger.warning('Falling back to starter interview questions due to a transient Gemini outage.')
            return _build_fallback_interview_questions(role, skills_text)
    except Exception as exc:
        if _is_non_retryable_error(exc):
            raise RuntimeError('Could not generate interview questions because the Gemini API key or model is invalid.') from exc
        logger.exception('Gemini API request failed while generating interview questions.')
        raise

    content = getattr(response, 'text', None)
    if not content:
        raise ValueError('The AI response was empty.')

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        cleaned = content.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.strip('`')
            if cleaned.lower().startswith('json'):
                cleaned = cleaned[4:].lstrip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            raise ValueError('The AI response was not valid JSON.')

    # Basic normalization and safety
    result = {
        'role': data.get('role') or role,
        'categories': data.get('categories') or {},
    }

    return result


def _build_fallback_interview_questions(role, skills_text=''):
    """Return a deterministic starter interview set when the Gemini service is unavailable."""
    skill_tailor = ''
    if skills_text:
        skill_tailor = f"Focus on these skills: {skills_text}."

    categories = {
        'Technical': [
            {
                'question': f'Can you walk through how you would approach a {role} task using a simple project example?',
                'guidance': 'Explain your thought process, tools you would use, and how you would validate your solution.',
                'key_points': ['Problem approach', 'Tools/stack', 'Validation', 'Trade-offs'],
            },
            {
                'question': 'What technical skills do you think are most important for this role, and why?',
                'guidance': 'Discuss practical skills, such as debugging, communication, or testing, and connect them to the job.',
                'key_points': ['Core skills', 'Why it matters', 'Real-world use', 'Continuous learning'],
            },
            {
                'question': 'How would you troubleshoot an issue when your code is not producing the expected result?',
                'guidance': 'Describe a structured debugging process, from reproducing the problem to validating the fix.',
                'key_points': ['Reproduce', 'Inspect logs', 'Isolate root cause', 'Verify fix'],
            },
        ],
        'Project': [
            {
                'question': 'Tell me about a project you have worked on or are most proud of.',
                'guidance': 'Describe the goal, your responsibilities, the challenges, and the outcome.',
                'key_points': ['Project goal', 'Your contribution', 'Challenges', 'Result'],
            },
            {
                'question': 'If you were improving a project you built before, what would you change and why?',
                'guidance': 'Show reflection, prioritization, and practical product thinking.',
                'key_points': ['What to improve', 'Why', 'Action plan', 'Trade-offs'],
            },
        ],
        'HR': [
            {
                'question': 'Why are you interested in this role and what would you like to learn?',
                'guidance': 'Be sincere, specific, and show curiosity about growth.',
                'key_points': ['Motivation', 'Learning goals', 'Alignment', 'Professional growth'],
            },
            {
                'question': 'How do you work with teammates or handle feedback during a project?',
                'guidance': 'Talk about communication, collaboration, and learning from feedback.',
                'key_points': ['Collaboration', 'Listening', 'Adaptation', 'Team impact'],
            },
        ],
    }

    if skill_tailor:
        for key in categories:
            for item in categories[key]:
                item['guidance'] = f"{item['guidance']} {skill_tailor}"

    return {'role': role, 'categories': categories, 'source': 'fallback'}


def generate_career_guidance(goal, resume_skills=None):
    """Use Gemini to produce structured, beginner-friendly career guidance.

    Returns a dict with keys expected by the Career Guidance view/template:
    - current_skill_summary
    - recommended_career_direction
    - skills_already_strong
    - skills_to_improve
    - suggested_technologies
    - suggested_projects
    - suggested_learning_roadmap
    - entry_level_roles
    - next_steps
    """
    if not goal:
        raise ValueError('Career goal is required to generate guidance.')

    if not is_openai_configured():
        raise RuntimeError('Gemini API key is missing or client not available. Add GEMINI_API_KEY and install google.genai to use this feature.')

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Define a simple JSON schema we ask Gemini to follow.
    json_schema = '''{
      "current_skill_summary": "short summary of the student's current skills",
      "recommended_career_direction": "one-line recommended direction",
      "strong_skills": ["skill 1", "skill 2"],
      "skills_to_improve": ["skill to learn 1", "skill to learn 2"],
      "suggested_technologies": ["tech 1", "tech 2"],
      "project_ideas": ["project idea 1", "project idea 2"],
      "learning_roadmap": ["step 1", "step 2"],
      "entry_level_roles": ["role 1", "role 2"],
      "next_steps": ["step 1", "step 2"]
    }'''

    skills_text = ''
    if resume_skills:
        if isinstance(resume_skills, list):
            skills_text = ', '.join([str(s) for s in resume_skills])
        else:
            skills_text = str(resume_skills)

    prompt = (
        f"Provide practical, student-friendly career guidance for the goal '{goal}'.\n"
        "Return valid JSON only using this schema:\n"
        f"{json_schema}\n\n"
        "If resume skills/text are available, use them to tailor recommendations. Keep language simple, realistic for a final-year engineering student, and do not promise jobs or salaries.\n"
        "Resume skills/text:\n"
        f"{skills_text[:5000]}"
    )

    try:
        response = _call_gemini_with_retry(
            lambda: client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            ),
            context='career guidance generation',
        )
        if response is None:
            raise RuntimeError('Could not generate career guidance. The service is temporarily unavailable. Please try again in a few moments.')
    except RuntimeError:
        raise
    except Exception as exc:
        if _is_non_retryable_error(exc):
            raise RuntimeError('Could not generate career guidance because the Gemini API key or model is invalid.') from exc
        logger.exception('Gemini API request failed while generating career guidance.')
        raise

    content = getattr(response, 'text', None)
    if not content:
        raise ValueError('The AI response was empty.')

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        cleaned = content.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.strip('`')
            if cleaned.lower().startswith('json'):
                cleaned = cleaned[4:].lstrip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            raise ValueError('The AI response was not valid JSON.')

    # Normalize keys: accept either the 'strong_skills'/'project_ideas'/'learning_roadmap' names
    normalized = {
        'current_skill_summary': data.get('current_skill_summary') or data.get('summary') or 'No summary provided.',
        'recommended_career_direction': data.get('recommended_career_direction') or goal,
        'skills_already_strong': data.get('strong_skills') or data.get('skills_already_strong') or [],
        'skills_to_improve': data.get('skills_to_improve') or [],
        'suggested_technologies': data.get('suggested_technologies') or data.get('technologies') or [],
        'suggested_projects': data.get('project_ideas') or data.get('suggested_projects') or [],
        'suggested_learning_roadmap': data.get('learning_roadmap') or data.get('suggested_learning_roadmap') or [],
        'entry_level_roles': data.get('entry_level_roles') or data.get('entry_level_roles') or [],
        'next_steps': data.get('next_steps') or [],
    }

    return normalized
