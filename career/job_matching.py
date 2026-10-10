"""Simple local job matching based on resume skill analysis."""

JOB_ROLES = [
    {
        'job_role': 'Python Developer',
        'skills': ['Python', 'SQL', 'Django', 'Flask', 'REST APIs', 'Git'],
        'recommendation_prefix': 'Your current skills align well with Python-based development work.'
    },
    {
        'job_role': 'Full Stack Developer',
        'skills': ['HTML', 'CSS', 'JavaScript', 'React', 'Django', 'SQL', 'Git'],
        'recommendation_prefix': 'You have a strong foundation for full-stack product work.'
    },
    {
        'job_role': 'Web Developer',
        'skills': ['HTML', 'CSS', 'JavaScript', 'Bootstrap', 'React', 'Django'],
        'recommendation_prefix': 'Your basics are suitable for modern web development projects.'
    },
    {
        'job_role': 'Software Developer',
        'skills': ['Python', 'JavaScript', 'Problem Solving', 'SQL', 'Git'],
        'recommendation_prefix': 'You have a solid general software foundation for entry-level roles.'
    },
    {
        'job_role': 'Junior Data Analyst',
        'skills': ['Python', 'SQL', 'Excel', 'Power BI', 'Pandas', 'Data Analysis'],
        'recommendation_prefix': 'Your profile supports junior data and reporting responsibilities.'
    },
    {
        'job_role': 'AI/ML Intern',
        'skills': ['Python', 'Machine Learning', 'Generative AI', 'APIs', 'Data Analysis'],
        'recommendation_prefix': 'You are positioned well for entry-level AI and ML learning tasks.'
    },
    {
        'job_role': 'Generative AI Intern',
        'skills': ['Python', 'Generative AI', 'APIs', 'Machine Learning', 'Prompt Engineering'],
        'recommendation_prefix': 'Your profile is a good match for generative AI experimentation and learning.'
    },
]


def normalize_skill(skill):
    if not skill:
        return ''
    return str(skill).strip().lower()


def generate_recommendation(match_percentage, missing_skills):
    missing_list = missing_skills[:2]
    if match_percentage >= 80:
        if missing_list:
            return (
                f"Your current skills align well with this role. Strengthen {', '.join(missing_list)} "
                "for better preparation."
            )
        return 'Your current skills align very well with this role.'

    if match_percentage >= 60:
        if missing_list:
            return (
                f"This role is a good fit with some room to improve. Focus on {', '.join(missing_list)} "
                "to become more competitive."
            )
        return 'This role is a good fit and you are already close to a strong profile.'

    if match_percentage >= 40:
        if missing_list:
            return (
                f"You have a promising base for this role. Build skills in {', '.join(missing_list)} "
                "to improve your match."
            )
        return 'You have a basic foundation for this role and can continue improving.'

    if missing_list:
        return (
            f"This role may need additional preparation. Strengthening {', '.join(missing_list)} "
            "would help you become more competitive."
        )
    return 'This role is a stretch match right now, but your current profile shows potential.'


def calculate_job_matches(analysis):
    if not analysis:
        return []

    raw_skills = analysis.get('skills') or []
    if isinstance(raw_skills, str):
        raw_skills = [raw_skills]
    if not isinstance(raw_skills, list):
        return []

    resume_skills = {
        normalize_skill(skill)
        for skill in raw_skills
        if str(skill).strip()
    }

    if not resume_skills:
        return []

    results = []

    for role in JOB_ROLES:
        role_skills = role.get('skills') or []
        if not role_skills:
            continue

        matching_skills = []
        missing_skills = []

        for skill in role_skills:
            if normalize_skill(skill) in resume_skills:
                matching_skills.append(skill)
            else:
                missing_skills.append(skill)

        if not matching_skills:
            continue

        match_percentage = round((len(matching_skills) / len(role_skills)) * 100)

        results.append({
            'job_role': role['job_role'],
            'match_percentage': min(max(match_percentage, 0), 100),
            'matching_skills': matching_skills,
            'skills_to_improve': missing_skills,
            'recommendation': generate_recommendation(match_percentage, missing_skills),
        })

    results.sort(key=lambda item: (-item['match_percentage'], -len(item['matching_skills']), item['job_role']))
    return results
