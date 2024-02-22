import math
import ctypes
from io import BytesIO
from PIL import Image, ImageFont, ImageDraw
import pypdfium2.raw as pdfium_c
from pypdfium2 import PdfDocument
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.serialization.pkcs7 import load_der_pkcs7_certificates
from base64 import b64encode

from zipfile import ZipFile


def get_png(page):
    width  = math.ceil(pdfium_c.FPDF_GetPageWidthF(page))
    height = math.ceil(pdfium_c.FPDF_GetPageHeightF(page))

    use_alpha = pdfium_c.FPDFPage_HasTransparency(page)
    bitmap = pdfium_c.FPDFBitmap_Create(width, height, int(use_alpha))
    
    pdfium_c.FPDFBitmap_FillRect(bitmap, 0, 0, width, height, 0xFFFFFFFF)

    # Store common rendering arguments
    render_args = (
        bitmap,  # the bitmap
        page,    # the page
        # positions and sizes are to be given in pixels and may exceed the bitmap
        0,       # left start position
        0,       # top start position
        width,   # horizontal size
        height,  # vertical size
        0,       # rotation (as constant, not in degrees!)
        pdfium_c.FPDF_LCD_TEXT | pdfium_c.FPDF_ANNOT,  # rendering flags, combined with binary or
    )

    # Render the page
    pdfium_c.FPDF_RenderPageBitmap(*render_args)

    # Get a pointer to the first item of the buffer
    buffer_ptr = pdfium_c.FPDFBitmap_GetBuffer(bitmap)
    # Re-interpret the pointer to encompass the whole buffer
    buffer_ptr = ctypes.cast(buffer_ptr, ctypes.POINTER(ctypes.c_ubyte * (width * height * 4)))

    # Create a PIL image from the buffer contents
    img = Image.frombuffer("RGBA", (width, height), buffer_ptr.contents, "raw", "BGRA", 0, 1)
    #img.save('f.png')
    #pdfium_c.FPDFBitmap_Destroy(bitmap)
    return img
    
def get_images(data: bytes):
    pdf = PdfDocument(data)

    # Check page count to make sure it was loaded correctly
    page_count = pdfium_c.FPDF_GetPageCount(pdf)
    assert page_count >= 1

    images = list()
    for num in range(page_count):
        page = pdfium_c.FPDF_LoadPage(pdf, num)
        img = get_png(page)
        images.append(img)
        
    # Free resources
    pdfium_c.FPDF_ClosePage(page)
    return images


def sign_info(sign: bytes):
    cert=load_der_pkcs7_certificates(sign)[0]
    common_name = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value    
    surname=cert.subject.get_attributes_for_oid(NameOID.SURNAME)
    if len(surname)>0:
        given_name=cert.subject.get_attributes_for_oid(NameOID.GIVEN_NAME)
        common_name = f'{surname[0].value} {given_name[0].value}'
    
    result = dict(
        serial_number=format(cert.serial_number, 'X'),
        signature_algorithm=cert.signature_algorithm_oid._name,
        name=common_name,        
        begin=cert.not_valid_before.strftime("%d.%m.%Y %H:%M"),
        end=cert.not_valid_after.strftime("%d.%m.%Y %H:%M"),
    )
    return result

def read_zip(data: bytes):
    certs = list()
    pdf = None
    with BytesIO(data) as f:
        with ZipFile(f) as zipfile:
            for filename in zipfile.namelist():
                ext = filename.split('.')[-1].lower()
                if ext not in ['pdf', 'p7s']:
                    continue
                with zipfile.open(filename, 'r') as myfile:
                    data = myfile.read()                
                if ext=='pdf':
                    pdf = data
                elif ext=='p7s':
                    certs.append(sign_info(data))
    return pdf, certs


def draw_stamp(img:Image, x, y, data, stamp_height, stamp_width): 
   font = ImageFont.truetype("arial.ttf")
   
   draw = ImageDraw.Draw(img)
   draw.text((x+5, y+1), "ДОКУМЕНТ ПОДПИСАН ЭЛЕКТРОННОЙ ПОДПИСЬЮ", font=font, fill="blue")
   
   font_serial = ImageFont.truetype("arial.ttf", size=12)
   draw.text((x+10,y+12), data['serial_number'], font=font_serial, fill="blue");
   
   draw.text((x+5,y+25), "Владелец:", font=font, fill="blue")
   draw.text((x+80,y+25), data['name'], font=font, fill="blue")
   
   draw.text((x+5,y+35), "Действителен:", font=font, fill="blue")
   draw.text((x+80,y+35), f"c {data['begin']} по {data['end']}", font=font, fill="blue")
   
   draw.text((x+5,y+45), "Алгоритм:", font=font, fill="blue")
   
   font = ImageFont.truetype("arial.ttf", size=7)
   draw.text((x+80,y+47), data['signature_algorithm'], font=font, fill="blue")
   
   draw.rectangle(((x, y), (x+stamp_width, y+stamp_height)),  width = 2, outline ="blue")
   



def draw_stamps(img:Image, certs: list, stamp_height=60, stamp_width=265):
    count_certs = len(certs)
    cols = math.trunc(img.width/(stamp_width+5))
    rows = math.trunc(count_certs/cols)+(0 if count_certs%cols==0  else 1)

    start_y = img.height-10-(stamp_height+5)*(rows+1)
    
    i=0
    for r in range(1, rows+1):
       for c in range(1, cols+1):
           if (i>count_certs-1):
                break
           x=50+(stamp_width+5)*(c-1)
           y=start_y+(stamp_height+5)*r
           draw_stamp(img, x, y, certs[i], stamp_height, stamp_width)
           i +=1

def get_html(images, name='', width=210, height=297, portret=True):
    pages = []
    for img in images:
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        str_base64 = b64encode(buffered.getvalue()).decode()
        page = f'<img src="data:image/png;base64,{str_base64}" style="width: 100%;">'
        pages.append(page)
    
    orientation = 'portrait' if portret else 'landscape' 
    
    html = f"""<!DOCTYPE html>
    <html>
    <head>
        <title>{name}</title>
        <style>
        @page {{
          size: A4 {orientation};
          margin: 0;
        }}
        @media print {{
          html, body {{
            width: {width}mm;
            height: {height}mm;
          }}
          }} 
        </style>
         <script type="text/javascript">window.onload =()=>window.print();</script>        
    </head>
    <body>
    {''.join(pages)}
    </body>
    </html>
    """
    return html
   
                    
def test(filepath):
    with open("приказ_о_привлечении_Габдрахманову_ТГ.zip", 'rb') as f:
        data = f.read()
        pdf, certs = read_zip(data)
    
    images = get_images(pdf)
    draw_stamps(images[-1], certs)
    html = get_html(images)
    with open('1.html', 'wt') as f:
        f.write(html)


   
if __name__=='__main__':
    test("Газета.pdf")
