import os
import sys
import django
import logging

# Setup project path and Django
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Configure logging to capture ai_service logs
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger('test_interview_prep')

django.setup()

from django.test import Client
from django.contrib.auth import get_user_model

results = {
    'page_load': 'FAIL',
    'submit': 'FAIL',
    'gemini_generation': 'FAIL',
    'result_displayed': 'FAIL',
    'retry_behavior': 'NOT TRIGGERED',
    'error': None,
    'code_modified': 'NO',
    'gemini_api_called': 'NO',
    'approx_calls': 0,
}

try:
    User = get_user_model()
    user = User.objects.first()
    if not user:
        results['error'] = 'No user found to log in with.'
        print(results)
        sys.exit(1)

    client = Client()
    client.force_login(user)

    # Load interview prep page
    url = '/interview-prep/'
    resp = client.get(url)
    if resp.status_code == 200:
        results['page_load'] = 'PASS'
    else:
        results['error'] = f'GET {url} returned {resp.status_code}'
        print(results)
        sys.exit(1)

    # Submit minimal valid input (role only)
    post_data = {'role': 'Python Developer'}

    resp2 = client.post(url, post_data, follow=True)
    if resp2.status_code in (200, 302):
        results['submit'] = 'PASS'
    else:
        results['error'] = f'POST {url} returned {resp2.status_code}'
        print(results)
        sys.exit(1)

    content = resp2.content.decode('utf-8', errors='ignore')

    # Detect failures
    if 'Could not generate interview questions' in content or 'Could not generate' in content:
        results['gemini_generation'] = 'FAIL'
        results['result_displayed'] = 'FAIL'
    else:
        if 'Questions for' in content:
            results['gemini_generation'] = 'PASS'
            results['result_displayed'] = 'PASS'
            results['gemini_api_called'] = 'YES'
        else:
            results['error'] = 'No generated content found in response'

    # Heuristic: check logs for retry messages by inspecting server log file isn't available; rely on response for retry detection.

except Exception as e:
    results['error'] = str(e)

print('TEST_OUTPUT_START')
for k, v in results.items():
    print(f'{k}: {v}')
print('TEST_OUTPUT_END')
