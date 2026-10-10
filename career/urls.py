from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('upload/', views.upload_resume, name='upload_resume'),
    path('resume-result/<int:resume_id>/', views.resume_result, name='resume_result'),
    path('job-matching/', views.job_matching, name='job_matching'),
    path('interview-prep/', views.interview_prep, name='interview_prep'),
    path('career-guidance/', views.career_guidance, name='career_guidance'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
]
