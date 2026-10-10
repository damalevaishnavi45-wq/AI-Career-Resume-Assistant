import os
import django
import sys
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
# Ensure project root is on sys.path so Django can import the backend settings
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()

result = {
    'page_load': 'FAIL',
    'submit': 'FAIL',
    'gemini_generation': 'FAIL',
    'result_displayed': 'FAIL',
    'retry_behavior': 'NOT TRIGGERED',
    'errors': [],
    'code_modified': 'NO',
    'gemini_called': 'NO',
    'cost': '₹0'
}

try:
    c = Client()
    user = User.objects.first()
    if not user:
        result['errors'].append('No user accounts found in DB')
        print(result)
        sys.exit(1)

    # Force login as the existing user (no password needed)
    c.force_login(user)

    # 1. Load the interview prep page
    url = reverse('interview_prep')
    resp = c.get(url)
    if resp.status_code == 200:
        result['page_load'] = 'PASS'
    else:
        result['errors'].append(f'Interview page GET returned {resp.status_code}')

    # 2. Submit minimal valid input
    post_data = {'role': 'Python Developer'}
    resp2 = c.post(url, post_data, follow=True)
    if resp2.status_code in (200, 302):
        result['submit'] = 'PASS'
    else:
        result['errors'].append(f'Interview page POST returned {resp2.status_code}')

    content = resp2.content.decode('utf-8', errors='ignore')

    # 3. Check for indications of Gemini call or generation
    if 'Could not generate interview questions' in content or 'Could not generate' in content:
        result['gemini_generation'] = 'FAIL'
        result['result_displayed'] = 'FAIL'
    else:
        # If generated content present, template shows "Questions for"
        if 'Questions for' in content or 'Questions for' in content:
            result['gemini_generation'] = 'PASS'
            result['result_displayed'] = 'PASS'
            result['gemini_called'] = 'YES'
        else:
            # Likely a configuration/runtime error due to missing Gemini
            if 'Gemini API key is missing' in content or 'Gemini' in content:
                result['gemini_generation'] = 'FAIL'
                result['errors'].append('Gemini not configured')
            else:
                # Could be that generation returned nothing
                result['gemini_generation'] = 'FAIL'
                result['errors'].append('No generated content found in response')

    print('Interview Preparation Functional Test Results:')
    for k, v in result.items():
        if k == 'errors' and v:
            print(f'- {k}:')
            for e in v:
                print(f'  - {e}')
        else:
            print(f'- {k}: {v}')

except Exception as e:
    print('Exception during test run:', str(e))
    raise
