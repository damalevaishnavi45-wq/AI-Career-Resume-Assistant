import logging
import os
import shutil
import tempfile

from django.shortcuts import redirect, render
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required

from .ai_service import analyze_resume_text, generate_interview_questions, _is_resource_exhausted_error
from .forms import ResumeForm
from .job_matching import calculate_job_matches
from .models import Resume
from .resume_parser import extract_text_from_pdf


logger = logging.getLogger(__name__)


@login_required(login_url='login')
def home(request):
    return render(request, 'home.html')


@login_required(login_url='login')
def upload_resume(request):
    if request.method == 'POST':
        form = ResumeForm(request.POST, request.FILES)
        if form.is_valid():
            resume = form.save()
            # Ensure the saved file is closed so external readers can open it reliably on Windows.
            try:
                resume.resume_file.close()
            except Exception:
                pass
            # Extract text from the saved PDF using the production extractor.
            # Create an independent copy of the saved file and pass that
            # stable path to the extractor so PdfReader reads a fully
            # independent file handle (avoids reading the original upload handle).
            saved_path = getattr(resume.resume_file, 'path', None)
            extracted_text = ''
            if saved_path and os.path.exists(saved_path) and os.path.getsize(saved_path) > 0:
                tmp = None
                try:
                    tmp_f = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                    tmp = tmp_f.name
                    tmp_f.close()
                    shutil.copyfile(saved_path, tmp)
                    extracted_text = extract_text_from_pdf(tmp)
                finally:
                    try:
                        if tmp and os.path.exists(tmp):
                            os.unlink(tmp)
                    except Exception:
                        pass

            resume.extracted_text = extracted_text or ''
            resume.save(update_fields=['extracted_text'])

            if not extracted_text or not extracted_text.strip():
                form.add_error(
                    'resume_file',
                    'We could not read any text from that PDF. Please upload a readable PDF with text content.'
                )
                return render(request, 'upload_resume.html', {'form': form})

            try:
                analysis = analyze_resume_text(extracted_text)
                request.session[f'resume_analysis_{resume.id}'] = analysis
                request.session['latest_resume_id'] = resume.id
            except Exception:
                logger.exception('Resume analysis failed for resume_id=%s', resume.id)
                request.session[f'resume_error_{resume.id}'] = (
                    'We could not analyze your resume right now. Please try again later.'
                )

            return redirect('resume_result', resume_id=resume.id)
    else:
        form = ResumeForm()

    return render(request, 'upload_resume.html', {'form': form})


@login_required(login_url='login')
def resume_result(request, resume_id):
    resume = Resume.objects.get(id=resume_id)
    analysis = request.session.get(f'resume_analysis_{resume_id}')
    error_message = request.session.pop(f'resume_error_{resume_id}', None)

    if not analysis and not error_message:
        error_message = 'Resume analysis is not available for this file. Please upload a new PDF and try again.'

    return render(
        request,
        'resume_result.html',
        {'resume': resume, 'analysis': analysis, 'error_message': error_message},
    )


@login_required(login_url='login')
def job_matching(request):
    latest_resume_id = request.session.get('latest_resume_id')
    if not latest_resume_id:
        return render(
            request,
            'job_matching.html',
            {'message': 'Please upload and analyze your resume first to see job matches.'},
        )

    analysis = request.session.get(f'resume_analysis_{latest_resume_id}')
    if not analysis:
        return render(
            request,
            'job_matching.html',
            {'message': 'Please upload and analyze your resume first to see job matches.'},
        )

    matches = calculate_job_matches(analysis)
    return render(
        request,
        'job_matching.html',
        {'analysis': analysis, 'matches': matches, 'resume_id': latest_resume_id},
    )


@login_required(login_url='login')
def interview_prep(request):
    roles = [
        'Python Developer',
        'Full Stack Developer',
        'Web Developer',
        'Software Developer',
        'Data Analyst',
        'AI/ML Developer',
    ]

    latest_resume_id = request.session.get('latest_resume_id')
    resume = None
    resume_text = ''
    if latest_resume_id:
        try:
            resume = Resume.objects.get(id=latest_resume_id)
            resume_text = resume.extracted_text or ''
        except Resume.DoesNotExist:
            resume = None

    generated = None
    error_message = None

    if request.method == 'POST':
        role = request.POST.get('role')
        use_resume = bool(request.POST.get('use_resume'))
        skills = None
        if use_resume and resume_text:
            # try to fetch skills from stored analysis
            analysis = request.session.get(f'resume_analysis_{latest_resume_id}')
            skills = analysis.get('skills') if analysis else None

        try:
            generated = generate_interview_questions(role=role, resume_skills=skills)
            request.session['last_interview_prep'] = generated
            if generated and generated.get('source') == 'fallback':
                error_message = 'The AI service is temporarily unavailable, so a starter interview practice set is shown below.'
        except Exception:
            logger.exception('Interview prep generation failed for role=%s', role)
            error_message = 'Could not generate interview questions right now. Please try again later.'

    return render(request, 'interview_prep.html', {
        'roles': roles,
        'resume': resume,
        'generated': generated,
        'error_message': error_message,
    })


@login_required(login_url='login')
def career_guidance(request):
    roles = [
        'Python Developer',
        'Full Stack Developer',
        'Web Developer',
        'Software Developer',
        'Data Analyst',
        'AI/ML Developer',
        'Generative AI Developer',
    ]

    latest_resume_id = request.session.get('latest_resume_id')
    resume = None
    resume_text = ''
    if latest_resume_id:
        try:
            resume = Resume.objects.get(id=latest_resume_id)
            resume_text = resume.extracted_text or ''
        except Resume.DoesNotExist:
            resume = None

    guidance = None
    error_message = None

    if request.method == 'POST':
        goal = request.POST.get('goal')
        use_resume = bool(request.POST.get('use_resume'))
        skills = None
        if use_resume and resume_text:
            analysis = request.session.get(f'resume_analysis_{latest_resume_id}')
            skills = analysis.get('skills') if analysis else None

        try:
            from .ai_service import generate_career_guidance

            guidance = generate_career_guidance(goal=goal, resume_skills=skills or resume_text)
            request.session['last_career_guidance'] = guidance
        except Exception:
            logger.exception('Career guidance generation failed for goal=%s', goal)
            error_message = 'Could not generate career guidance right now. Please try again later.'

    return render(request, 'career_guidance.html', {
        'roles': roles,
        'resume': resume,
        'guidance': guidance,
        'error_message': error_message,
    })


def login_view(request):
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            error = 'Invalid username or password.'

    return render(request, 'login.html', {'error_message': error})


def register_view(request):
    error = None
    User = get_user_model()
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')

        if not username or not password:
            error = 'Username and password are required.'
        elif password != password2:
            error = 'Passwords do not match.'
        elif User.objects.filter(username=username).exists():
            error = 'Username is already taken.'
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            user.save()
            # auto-login after registration
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                return redirect('home')

    return render(request, 'register.html', {'error_message': error})


def logout_view(request):
    logout(request)
    return redirect('login')
