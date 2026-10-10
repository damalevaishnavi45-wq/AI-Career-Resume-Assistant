def extract_text_from_pdf(file_path):
    """Read text from a PDF file and return it as one string.

    The PDF library import is performed lazily so the app can be checked
    in environments where `pypdf` is not installed. On failure the function
    returns an empty string.
    """
    try:
        from pypdf import PdfReader
    except Exception:
        return ""

    try:
        # Open the file as a binary stream and pass the stream to PdfReader.
        # This is slightly more robust across platforms and file paths
        # than passing the path string directly to PdfReader.
        pages_text = []
        with open(file_path, "rb") as fh:
            reader = PdfReader(fh)
            for page in reader.pages:
                try:
                    text = page.extract_text()
                except Exception:
                    text = None
                if text:
                    pages_text.append(text)

        return "\n\n".join(pages_text)
    except Exception:
        return ""

