from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from . import ai_service
from .forms import ResumeForm
from .job_matching import calculate_job_matches


class GeminiInterviewGenerationTests(TestCase):
    def _fake_genai(self, generate_content_side_effect=None):
        class FakeClientError(Exception):
            def __init__(self, message='bad request', status_code=None):
                super().__init__(message)
                self.status_code = status_code

        class FakeServerError(Exception):
            pass

        client = MagicMock()
        client.models.generate_content.side_effect = generate_content_side_effect

        fake_genai = SimpleNamespace(
            Client=MagicMock(return_value=client),
            errors=SimpleNamespace(
                ClientError=FakeClientError,
                ServerError=FakeServerError,
            ),
        )
        return fake_genai, client

    @patch.object(ai_service, 'GEMINI_API_KEY', 'test-key')
    @patch.object(ai_service, 'GEMINI_MODEL', 'gemini-3.5-flash')
    @patch.object(ai_service, 'genai')
    def test_uses_supported_gemini_model_name(self, fake_genai):
        response = SimpleNamespace(text='{"summary":"Strong Python candidate","skills":["Python","Django"],"skill_gaps":[],"strengths":[],"improvements":[],"career_suggestions":[],"resume_score":88}')
        fake_genai.Client.return_value.models.generate_content.return_value = response
        fake_genai.errors = SimpleNamespace(
            ClientError=type('ClientError', (Exception,), {}),
            ServerError=type('ServerError', (Exception,), {}),
        )

        ai_service.analyze_resume_text('Python developer with Django and SQL experience.')

        self.assertEqual(fake_genai.Client.return_value.models.generate_content.call_args.kwargs['model'], 'gemini-3.5-flash')

    @patch.object(ai_service, 'GEMINI_API_KEY', 'test-key')
    @patch.object(ai_service, 'GEMINI_MODEL', 'gemini-3.5-flash')
    @patch.object(ai_service, 'genai')
    def test_generates_interview_questions_successfully(self, fake_genai):
        response = SimpleNamespace(text='{"role":"Python Developer","categories":{"Technical":[{"question":"What is Python?","guidance":"Explain clearly.","key_points":["syntax","logic"]}],"Project":[{"question":"Tell me about a project.","guidance":"Show impact.","key_points":["role","result"]}],"HR":[{"question":"Why do you want this role?","guidance":"Be honest.","key_points":["motivation","learning"]}]}}')
        fake_genai.Client.return_value.models.generate_content.return_value = response
        fake_genai.errors = SimpleNamespace(
            ClientError=type('ClientError', (Exception,), {'__init__': lambda self, message='x', status_code=None: setattr(self, 'status_code', status_code) or Exception.__init__(self, message)}),
            ServerError=type('ServerError', (Exception,), {}),
        )

        result = ai_service.generate_interview_questions('Python Developer', ['Python', 'Django'])

        self.assertEqual(result['role'], 'Python Developer')
        self.assertIn('Technical', result['categories'])
        self.assertEqual(result['categories']['Technical'][0]['question'], 'What is Python?')

    @patch.object(ai_service, 'GEMINI_API_KEY', 'test-key')
    @patch.object(ai_service, 'GEMINI_MODEL', 'gemini-3.5-flash')
    @patch.object(ai_service, 'genai')
    def test_retries_transient_failure_then_succeeds(self, fake_genai):
        response = SimpleNamespace(text='{"role":"Python Developer","categories":{"Technical":[{"question":"Explain lists.","guidance":"Keep it concise.","key_points":["list operations"]}],"Project":[],"HR":[]}}')
        fake_genai.Client.return_value.models.generate_content.side_effect = [
            RuntimeError('temporary outage'),
            response,
        ]
        fake_genai.errors = SimpleNamespace(
            ClientError=type('ClientError', (Exception,), {}),
            ServerError=type('ServerError', (Exception,), {}),
        )

        result = ai_service.generate_interview_questions('Python Developer')

        self.assertEqual(result['role'], 'Python Developer')
        self.assertEqual(fake_genai.Client.return_value.models.generate_content.call_count, 2)

    @patch.object(ai_service, 'GEMINI_API_KEY', 'test-key')
    @patch.object(ai_service, 'GEMINI_MODEL', 'gemini-3.5-flash')
    @patch.object(ai_service, 'genai')
    def test_returns_fallback_when_retries_are_exhausted(self, fake_genai):
        class FakeServerError(Exception):
            pass

        fake_genai.Client.return_value.models.generate_content.side_effect = [
            FakeServerError('server down'),
            FakeServerError('server down'),
            FakeServerError('server down'),
        ]
        fake_genai.errors = SimpleNamespace(
            ClientError=type('ClientError', (Exception,), {}),
            ServerError=FakeServerError,
        )

        result = ai_service.generate_interview_questions('Data Analyst')

        self.assertEqual(result['role'], 'Data Analyst')
        self.assertIn('Technical', result['categories'])
        self.assertTrue(result.get('source') == 'fallback' or 'fallback' in str(result.get('source', '')))

    @patch.object(ai_service, 'GEMINI_API_KEY', 'test-key')
    @patch.object(ai_service, 'GEMINI_MODEL', 'gemini-3.5-flash')
    @patch.object(ai_service, 'genai')
    def test_raises_for_authentication_or_quota_errors(self, fake_genai):
        class FakeClientError(Exception):
            status_code = 401

        fake_genai.Client.return_value.models.generate_content.side_effect = FakeClientError('invalid key')
        fake_genai.errors = SimpleNamespace(
            ClientError=FakeClientError,
            ServerError=type('ServerError', (Exception,), {}),
        )

        with self.assertRaises(RuntimeError):
            ai_service.generate_interview_questions('AI/ML Developer')

    @patch.object(ai_service, 'GEMINI_API_KEY', 'test-key')
    @patch.object(ai_service, 'GEMINI_MODEL', 'gemini-3.5-flash')
    @patch.object(ai_service, 'genai')
    def test_raises_for_empty_response(self, fake_genai):
        response = SimpleNamespace(text='')
        fake_genai.Client.return_value.models.generate_content.return_value = response
        fake_genai.errors = SimpleNamespace(
            ClientError=type('ClientError', (Exception,), {}),
            ServerError=type('ServerError', (Exception,), {}),
        )

        with self.assertRaises(ValueError):
            ai_service.generate_interview_questions('Software Developer')


class ResumeFormTests(TestCase):
    def test_requires_a_resume_file(self):
        form = ResumeForm(data={}, files={})

        self.assertFalse(form.is_valid())
        self.assertIn('resume_file', form.errors)

    def test_rejects_non_pdf_files(self):
        form = ResumeForm(
            files={'resume_file': SimpleUploadedFile('resume.txt', b'hello world', content_type='text/plain')}
        )

        self.assertFalse(form.is_valid())
        self.assertIn('resume_file', form.errors)

    def test_rejects_large_pdf_files(self):
        large_pdf = b'%PDF-1.4\n' + (b'x' * (6 * 1024 * 1024))
        form = ResumeForm(
            files={'resume_file': SimpleUploadedFile('resume.pdf', large_pdf, content_type='application/pdf')}
        )

        self.assertFalse(form.is_valid())
        self.assertIn('resume_file', form.errors)


class JobMatchingTests(TestCase):
    def test_calculates_job_matches_from_resume_skills(self):
        analysis = {'skills': ['Python', 'SQL', 'Django', 'HTML', 'CSS', 'JavaScript']}

        matches = calculate_job_matches(analysis)

        self.assertTrue(matches)
        self.assertIn('Python Developer', [job['job_role'] for job in matches])
        self.assertIn('Full Stack Developer', [job['job_role'] for job in matches])
        self.assertGreater(matches[0]['match_percentage'], 0)

    def test_returns_empty_list_for_missing_skills(self):
        analysis = {'skills': []}

        matches = calculate_job_matches(analysis)

        self.assertEqual(matches, [])
