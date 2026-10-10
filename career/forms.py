from django import forms

from .models import Resume

MAX_RESUME_SIZE = 5 * 1024 * 1024


class ResumeForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ['resume_file']

    def clean_resume_file(self):
        resume_file = self.cleaned_data.get('resume_file')

        if not resume_file:
            raise forms.ValidationError('Please select a PDF resume to upload.')

        if not resume_file.name.lower().endswith('.pdf'):
            raise forms.ValidationError('Please upload a PDF file.')

        if resume_file.size > MAX_RESUME_SIZE:
            raise forms.ValidationError('Please upload a PDF smaller than 5 MB.')

        file_header = resume_file.read(5)
        resume_file.seek(0)

        if file_header and file_header[:4] != b'%PDF':
            raise forms.ValidationError('The selected file does not look like a valid PDF.')

        return resume_file
