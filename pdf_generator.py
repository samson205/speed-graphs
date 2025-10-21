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
    _title = None
    _elements = None
    _styles = None
    _doc = None

    def __init__(self, file_name: str, title: str = "Отчет"):
        self._title = title
        self._elements = []
        self._styles = getSampleStyleSheet()
        self._doc = SimpleDocTemplate(file_name, pagesize=landscape(A4),
                                      topMargin=cm, bottomMargin=cm)

    def add_title(self, text: str = None) -> None:
        title_text = text if text else self._title
        self._styles['Title'].fontName = 'Arial'
        title = Paragraph(title_text, self._styles['Title'])
        self._elements.append(title)
        self._elements.append(Spacer(1, 20))

    def add_table(self, data, style=None) -> None:
        table = Table(data)

        if style is None:
            rows_to_span = range(2, 9)
            style = [
                ('SPAN', (1, 1), (2, 1)),
                ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
                ('FONTSIZE', (0, 0), (-1, -1), 14),
                ('LEADING', (0, 0), (-1, -1), 18),

                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]
            for row in rows_to_span:
                style.append(('SPAN', (1, row), (2, row)))
            style = TableStyle(style)

        table.setStyle(style)
        self._elements.append(table)
        self._elements.append(Spacer(1, 20))

    def add_image(self, image_path: str, width: float = 11 * inch,
                  height: float = 6 * inch) -> bool:
        try:
            if os.path.exists(image_path):
                image = Image(image_path, width=width, height=height)
                image.hAlign = 'CENTER'
                self._elements.append(image)
                self._elements.append(Spacer(1, 20))
                return True
        except Exception as e:
            print(f"Произошла ошибка при добавлении изображения: {e}")
        return False

    def generate(self) -> None:
        self._doc.build(self._elements)
