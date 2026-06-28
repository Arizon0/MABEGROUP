"""Exportação de relatórios para Excel (openpyxl) e PDF (reportlab)."""
from __future__ import annotations

import io

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def _linhas_para_matriz(colunas: list[str], linhas: list[dict]) -> list[list]:
    return [[("" if l.get(c) is None else l.get(c)) for c in colunas] for l in linhas]


def to_excel(titulo: str, colunas: list[str], linhas: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = titulo[:31] or "Relatório"
    ws.append(colunas)
    for linha in _linhas_para_matriz(colunas, linhas):
        ws.append(linha)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def to_pdf(titulo: str, colunas: list[str], linhas: list[dict]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    estilos = getSampleStyleSheet()
    elementos = [Paragraph(titulo, estilos["Title"]), Spacer(1, 12)]

    dados = [colunas] + [
        [str(v) for v in linha] for linha in _linhas_para_matriz(colunas, linhas)
    ]
    tabela = Table(dados, repeatRows=1)
    tabela.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ])
    )
    elementos.append(tabela)
    doc.build(elementos)
    return buffer.getvalue()
