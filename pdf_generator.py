import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('Arial-Bold', 'C:/Windows/Fonts/arialbd.ttf'))

class PDFGenerator:
    def __init__(self, file_name, title="Отчет"):
        self.filename = file_name
        self.title = title
        self.elements = []
        self.styles = getSampleStyleSheet()
        self.doc = SimpleDocTemplate(file_name, pagesize=landscape(A4), topMargin=cm, bottomMargin=cm)

    def add_title(self, text = None):
        title_text = text if text else self.title
        self.styles['Title'].fontName = 'Arial'
        title = Paragraph(title_text, self.styles['Title'])
        self.elements.append(title)
        self.elements.append(Spacer(1, 20))

    def add_table(self, data, style=None):
        table = Table(data)

        if style is None:
            style = TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),

                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ])

        table.setStyle(style)
        self.elements.append(table)
        self.elements.append(Spacer(1, 20))

    def add_image(self, image_path, width=11*inch, height=6*inch):
        try:
            if os.path.exists(image_path):
                image = Image(image_path, width=width, height=height)
                image.hAlign = 'CENTER'
                self.elements.append(image)
                self.elements.append(Spacer(1, 20))
                return True
        except Exception as e:
            print(f"Произошла ошибка при добавлении изображения: {e}")
        return False

    def generate(self):
        self.doc.build(self.elements)
