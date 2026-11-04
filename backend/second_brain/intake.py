import io,json,os,subprocess,tempfile
from pathlib import Path
from PIL import Image,ImageOps
from pypdf import PdfReader
from django.conf import settings
from .privacy import redact
MAX_BYTES=10*1024*1024
class IntakeError(ValueError): pass

def ocr_image(data):
    try:
        Image.MAX_IMAGE_PIXELS=25_000_000
        im=Image.open(io.BytesIO(data)); im.verify()
        im=ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert('RGB')
        if im.width*im.height>25_000_000: raise IntakeError('Image is too large. Limit: 25 megapixels.')
        # Re-encode pixels, stripping EXIF. No original file is retained.
        with tempfile.TemporaryDirectory(prefix='second-brain-') as temp:
            path=Path(temp)/'page.png'; im.save(path)
            binary=settings.BASE_DIR/'scripts'/'ocr-local'
            if binary.exists(): command=[str(binary),str(path)]
            elif __import__('shutil').which('tesseract'): command=['tesseract',str(path),'stdout']
            else: raise IntakeError('Local OCR is not installed. Run scripts/build-ocr.sh on macOS, or install Tesseract. Paste a manual transcription instead.')
            r=subprocess.run(command,capture_output=True,timeout=45,check=True)
            if binary.exists():
                rows=json.loads(r.stdout); return '\n'.join(x['text'] for x in rows),[x['text'] for x in rows if x['confidence']<0.8]
            return r.stdout.decode(),[]
    except IntakeError: raise
    except Exception: raise IntakeError('Image extraction failed. Use a clearer image or paste a manual transcription.')

def extract(upload):
    data=upload.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES: raise IntakeError('File exceeds the 10 MB limit.')
    suffix=Path(upload.name).suffix.lower()
    if suffix in ['.png','.jpg','.jpeg','.webp']:
        text,low=ocr_image(data); method='Local OCR'
    elif suffix=='.pdf' and data.startswith(b'%PDF-'):
        try:
            pdf=PdfReader(io.BytesIO(data))
            if pdf.is_encrypted: raise IntakeError('Encrypted PDFs are not supported.')
            if len(pdf.pages)>30: raise IntakeError('PDF limit: 30 pages.')
            text='\n\n'.join(f'[Page {i+1}]\n{p.extract_text() or "[NO TEXT: scanned page requires OCR]"}' for i,p in enumerate(pdf.pages))
            low=[]; method='PDF text extraction'
            if any(not (p.extract_text() or '').strip() for p in pdf.pages):
                binary=settings.BASE_DIR/'scripts'/'ocr-local'
                if not binary.exists() and not (__import__('shutil').which('pdftoppm') and __import__('shutil').which('tesseract')):
                    raise IntakeError('Scanned PDF pages require the macOS OCR helper or Poppler and Tesseract.')
                with tempfile.TemporaryDirectory(prefix='second-brain-') as temp:
                    path=Path(temp)/'scan.pdf'; path.write_bytes(data)
                    if binary.exists():
                        result=subprocess.run([str(binary),str(path)],capture_output=True,timeout=60,check=True)
                        rows=json.loads(result.stdout)
                    else:
                        rows=[]
                        for index,page in enumerate(pdf.pages,1):
                            if (page.extract_text() or '').strip(): continue
                            prefix=Path(temp)/f'page-{index}'
                            subprocess.run(['pdftoppm','-f',str(index),'-l',str(index),'-singlefile','-scale-to','2200','-png',str(path),str(prefix)],capture_output=True,timeout=30,check=True)
                            page_text,_=ocr_image(prefix.with_suffix('.png').read_bytes())
                            rows.append({'page':index,'text':page_text,'confidence':0.0})

                texts=[]
                for i,page in enumerate(pdf.pages):
                    page_text=(page.extract_text() or '').strip()
                    if not page_text:
                        page_text='\n'.join(r['text'] for r in rows if r.get('page')==i+1)
                        low.extend(r['text'] for r in rows if r.get('page')==i+1 and r['confidence']<0.8)
                    if not page_text: raise IntakeError(f'No text found on page {i+1}. Paste a manual transcription; this page cannot be silently omitted.')
                    texts.append(f'[Page {i+1}]\n{page_text}')
                text='\n\n'.join(texts);method='PDF text + local OCR'
        except IntakeError: raise
        except Exception: raise IntakeError('Cannot read this PDF. Upload a valid text PDF or image.')
    elif suffix in ['.txt','.md']:
        try: text=data.decode('utf-8')
        except UnicodeDecodeError: raise IntakeError('Text file must use UTF-8.')
        low=[]; method='Text import'
    else: raise IntakeError('Supported formats: PDF, PNG, JPEG, WebP, TXT, MD. Audio requires a pasted, locally transcribed note.')
    if len(text)>100000: raise IntakeError('Extracted text exceeds 100,000 characters.')
    if not text.strip(): raise IntakeError('No readable text found. Paste a manual transcription.')
    clean,counts=redact(text)
    return clean,counts,method,len(low)
